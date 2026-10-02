"""Content-free application logging.

Application logs must never contain document text, query text, file names,
or PII. This module enforces that structurally, not by convention:

* `log_event(event, **fields)` only accepts allowlisted field names, and only
  values that look like identifiers, reason codes or numbers. Anything else is
  replaced with "[redacted]".
* `configure_logging()` installs a filter on the root handler that rewrites
  every record not produced by `log_event` (third-party libraries, stray
  `logging.info(...)` calls) to a fixed placeholder, and reduces tracebacks
  to the exception type name.

The audit log (audit.py) is a separate, encrypted-at-rest-adjacent channel
with its own rules. It is not an application log.
"""

from __future__ import annotations

import json
import logging
import re
import sys

EVENT_LOGGER = "lexreview.events"

ALLOWED_FIELDS = frozenset(
    {
        "case_id", "doc_id", "user_id", "session_id", "status", "reason",
        "count", "pages", "chunks", "duration_ms", "bytes", "kind", "role",
        "action", "outcome", "seq", "backend", "phase", "error_type",
    }
)

_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:\-]{1,80}$")
_REDACTED = "[redacted]"


def _clean(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str) and _SAFE_VALUE.match(value):
        return value
    return _REDACTED


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    if not _SAFE_VALUE.match(event):
        event = "invalid_event_name"
    payload = {"event": event}
    for key, value in fields.items():
        if key in ALLOWED_FIELDS:
            payload[key] = _clean(value)
        else:
            payload.setdefault("dropped_fields", 0)
            payload["dropped_fields"] += 1
    logging.getLogger(EVENT_LOGGER).log(level, json.dumps(payload, sort_keys=True), extra={"_lexreview_safe": True})


class RedactingFilter(logging.Filter):
    """Rewrites any record that did not come through log_event."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "_lexreview_safe", False):
            record.msg = "third_party_log_suppressed logger=%s"
            record.args = (record.name if _SAFE_VALUE.match(record.name) else "other",)
        if record.exc_info:
            etype = record.exc_info[0]
            record.msg = record.msg + " error_type=" + (etype.__name__ if etype else "unknown")
            record.exc_info = None
            record.exc_text = None
        record.stack_info = None
        return True


def configure_logging(level: int = logging.INFO, stream=None) -> logging.Handler:
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)
    # Uncaught exceptions: print type only, never the message or traceback.
    def _excepthook(etype, value, tb):  # noqa: ARG001
        code = getattr(value, "code", None)
        code = code if isinstance(code, str) and _SAFE_VALUE.match(code) else ""
        sys.stderr.write(f"fatal error_type={etype.__name__} {('code=' + code) if code else ''}\n")
    sys.excepthook = _excepthook
    return handler
