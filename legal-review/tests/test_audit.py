"""Tamper-evident audit log."""

import json

import pytest

from lexreview.audit import Anchor, AuditLog
from lexreview.errors import AuditIntegrityError


@pytest.fixture
def log(tmp_path):
    lg = AuditLog(tmp_path / "audit.log", b"k" * 32)
    for i in range(5):
        lg.record("u_1", "view_page", "ok", case_id="c_1", target=f"d_{i}", page=i)
    return lg


def _lines(lg):
    return lg._path.read_text().splitlines()


def _write(lg, lines):
    lg._path.write_text("\n".join(lines) + "\n")


def test_verifies(log):
    assert log.verify() == 5


def test_edit_detected(log):
    lines = _lines(log)
    rec = json.loads(lines[2])
    rec["actor"] = "u_innocent"
    lines[2] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    _write(log, lines)
    with pytest.raises(AuditIntegrityError):
        log.verify()


def test_deletion_detected(log):
    lines = _lines(log)
    del lines[1]
    _write(log, lines)
    with pytest.raises(AuditIntegrityError):
        log.verify()


def test_reorder_detected(log):
    lines = _lines(log)
    lines[1], lines[2] = lines[2], lines[1]
    _write(log, lines)
    with pytest.raises(AuditIntegrityError):
        log.verify()


def test_forged_record_without_key_detected(log, tmp_path):
    forger = AuditLog(tmp_path / "other.log", b"x" * 32)
    lines = _lines(log)
    last = json.loads(lines[-1])
    body = {k: v for k, v in last.items() if k != "mac"}
    body.update(seq=6, prev=last["mac"], action="export", target="d_all")
    body["mac"] = forger._mac(last["mac"], {k: v for k, v in body.items() if k != "mac"})
    lines.append(json.dumps(body, sort_keys=True, separators=(",", ":")))
    _write(log, lines)
    with pytest.raises(AuditIntegrityError):
        log.verify()


def test_tail_truncation_detected_with_anchor(log):
    anchor = log.anchor()
    _write(log, _lines(log)[:-2])
    assert log.verify() == 3  # chain alone cannot see a clean tail cut...
    with pytest.raises(AuditIntegrityError):
        log.verify(anchor)     # ...the external anchor can.


def test_anchor_mismatch_detected(log):
    with pytest.raises(AuditIntegrityError):
        log.verify(Anchor(5, "0" * 64))


def test_unsafe_values_rejected(log):
    with pytest.raises(ValueError):
        log.record("u_1", "search", "ok", query="find everything about the secret merger")


def test_app_actions_are_audited(ingested):
    w = ingested
    doc = w.docs["docs/emails/e05.eml"]["doc_id"]
    w.app.view_page(w.ctx("bob", w.case_a), doc, 1)
    recs = list(w.app.audit.records())
    actions = {r["action"] for r in recs}
    assert {"login", "create_case", "add_member", "ingest", "ingest_document", "view_page", "set_restriction"} <= actions
    view = [r for r in recs if r["action"] == "view_page"][-1]
    assert view["actor"] == w.users["bob"]["uid"] and view["target"] == doc and view["case_id"] == w.case_a
    assert w.app.audit.verify() == len(recs)
