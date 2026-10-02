"""Application logs, errors and stderr must never carry document content,
queries, file names or PII."""

import io
import json
import logging
import subprocess
import sys

import pytest

from lexreview.authz import Perm
from lexreview.safelog import configure_logging, log_event


@pytest.fixture
def captured():
    buf = io.StringIO()
    old = logging.getLogger().handlers[:]
    old_hook = sys.excepthook
    configure_logging(logging.DEBUG, stream=buf)
    yield buf
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in old:
        root.addHandler(h)
    sys.excepthook = old_hook


def test_log_event_drops_unknown_fields_and_unsafe_values(captured):
    log_event("search_done", count=3, query="secret merger with Acme", doc_id="d_abc", reason="Okafor testimony")
    out = captured.getvalue()
    assert "secret merger" not in out and "Okafor" not in out
    payload = json.loads(out.split("INFO ", 1)[1])
    assert payload["count"] == 3 and payload["doc_id"] == "d_abc" and payload["reason"] == "[redacted]"
    assert payload["dropped_fields"] == 1


def test_third_party_logs_and_tracebacks_suppressed(captured):
    lg = logging.getLogger("some.parser.lib")
    lg.warning("could not parse page containing %s", "CANARY-7F3A9C-REEFER")
    try:
        raise ValueError("document text: CANARY-B81E22-OKAFOR")
    except ValueError:
        lg.exception("boom")
    out = captured.getvalue()
    assert "CANARY" not in out
    assert "third_party_log_suppressed" in out and "error_type=ValueError" in out


def test_full_ingestion_logs_are_content_free(world, corpus, labels, captured):
    ctx = world.ctx("alice", world.case_a, Perm.INGEST)
    world.app.ingest(ctx, corpus / "docs" / "emails")
    world.app.ingest(ctx, corpus / "docs" / "contracts")
    world.app.ingest(ctx, corpus / "docs" / "adversarial")
    out = captured.getvalue()
    assert "document_ingested" in out
    for needle in labels["canaries"] + ["Okafor", "Meridian", "4471", ".eml", ".pdf", "Ignore all previous"]:
        assert needle not in out, needle


def test_uncaught_exception_prints_type_only(tmp_path):
    code = ("from lexreview.safelog import configure_logging; configure_logging();"
            "raise RuntimeError('privileged: CANARY-40D5AA-SCAN')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert "CANARY" not in r.stderr and "RuntimeError" in r.stderr


def test_audit_log_has_no_content_or_filenames(ingested, labels):
    raw = (ingested.app.root / "audit" / "audit.log").read_text()
    for needle in labels["canaries"] + ["Okafor", "master_services_agreement", ".eml", "Harbor Point"]:
        assert needle not in raw, needle
