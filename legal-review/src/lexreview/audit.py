"""Append-only, tamper-evident audit log.

Every record is one JSON line:
    {seq, ts, actor, action, case_id, target, outcome, detail, prev, mac}
where mac = HMAC-SHA256(audit_key, prev || canonical_json(record_without_mac)).

That makes the log a hash chain: editing, deleting, inserting or reordering
any record breaks verification. The audit key is held wrapped by the KMS, so
someone who can write the file but cannot use the KMS cannot forge records.

Truncating the *tail* of the log is only detectable against an external
anchor (the last seq+mac copied somewhere the attacker cannot write, e.g. a
WORM bucket or SIEM). `anchor()` produces that value and `verify()` accepts
it. Anchoring on a schedule is a deployment requirement (SECURITY.md).

What is recorded: who, what action, which case, which document IDs, outcome,
counts and reason codes. What is never recorded: document text, file names,
query text. Queries are recorded as an HMAC digest; the query text itself is
stored encrypted inside the case store.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .errors import AuditIntegrityError

GENESIS = "0" * 64
_SAFE = re.compile(r"^[A-Za-z0-9_.:\-]{0,128}$")


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _safe_value(v):
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str) and _SAFE.match(v):
        return v
    if isinstance(v, (list, tuple)):
        return [_safe_value(x) for x in v][:1000]
    raise ValueError("audit_value_not_safe")


@dataclass(frozen=True)
class Anchor:
    seq: int
    mac: str


class AuditLog:
    def __init__(self, path: Path, key: bytes):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._key = key
        if not self._path.exists():
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)

    def _mac(self, prev: str, body: dict) -> str:
        return hmac.new(self._key, prev.encode() + _canon(body), hashlib.sha256).hexdigest()

    def digest(self, text: str) -> str:
        """Keyed digest for correlating sensitive strings (e.g. queries)
        without writing them. Keyed so short queries cannot be brute-forced
        from the log alone."""
        return hmac.new(self._key, b"digest:" + text.encode(), hashlib.sha256).hexdigest()[:32]

    def _last(self, fh) -> tuple[int, str]:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        if size == 0:
            return 0, GENESIS
        # Read back just far enough to find the last full line.
        block = min(size, 65536)
        fh.seek(size - block)
        tail = fh.read(block).rstrip(b"\n").rsplit(b"\n", 1)[-1]
        rec = json.loads(tail)
        return rec["seq"], rec["mac"]

    def record(self, actor: str, action: str, outcome: str, case_id: str | None = None,
               target: list[str] | str | None = None, **detail) -> int:
        body = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "actor": _safe_value(actor),
            "action": _safe_value(action),
            "case_id": _safe_value(case_id),
            "target": _safe_value(target),
            "outcome": _safe_value(outcome),
            "detail": {k: _safe_value(v) for k, v in sorted(detail.items())},
        }
        # O_APPEND: every write lands at the end, even with concurrent writers.
        fd = os.open(self._path, os.O_RDWR | os.O_APPEND)
        with os.fdopen(fd, "r+b") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                seq, prev = self._last(fh)
                body["seq"] = seq + 1
                body["prev"] = prev
                body["mac"] = self._mac(prev, body)
                fh.write(_canon(body) + b"\n")
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        return body["seq"]

    def anchor(self) -> Anchor:
        with open(self._path, "rb") as fh:
            seq, mac = self._last(fh)
        return Anchor(seq, mac)

    def records(self):
        with open(self._path, "rb") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)

    def verify(self, anchor: Anchor | None = None) -> int:
        """Returns the number of verified records or raises AuditIntegrityError."""
        prev, expected_seq, count = GENESIS, 1, 0
        try:
            for rec in self.records():
                mac = rec.pop("mac")
                if rec.get("seq") != expected_seq or rec.get("prev") != prev:
                    raise AuditIntegrityError("audit_chain_broken")
                if not hmac.compare_digest(mac, self._mac(prev, rec)):
                    raise AuditIntegrityError("audit_mac_invalid")
                prev, expected_seq, count = mac, expected_seq + 1, count + 1
        except (json.JSONDecodeError, KeyError) as exc:
            raise AuditIntegrityError("audit_record_malformed") from exc
        if anchor is not None:
            if count < anchor.seq:
                raise AuditIntegrityError("audit_truncated")
            recs = {r["seq"]: r for r in self.records() if r["seq"] == anchor.seq}
            if anchor.seq and recs.get(anchor.seq, {}).get("mac") != anchor.mac:
                raise AuditIntegrityError("audit_anchor_mismatch")
        return count
