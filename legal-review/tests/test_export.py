"""Exports: permission-checked, watermarked, audited."""

import pytest

from lexreview.authz import Perm
from lexreview.errors import AccessDenied


def test_reviewer_cannot_export(ingested, tmp_path):
    w = ingested
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("bob"), w.case_a, Perm.EXPORT)
    # Even with a VIEW context in hand, App.export re-checks the permission.
    with pytest.raises(AccessDenied):
        w.app.export(w.ctx("bob", w.case_a), "coverage", "csv", tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert any(r["action"] == "export" and r["outcome"] == "denied" for r in w.app.audit.records())


def test_csv_export_watermarked_and_audited(ingested, tmp_path):
    w = ingested
    path = w.app.export(w.ctx("dave", w.case_a, Perm.EXPORT), "coverage", "csv", tmp_path)
    text = path.read_text()
    lines = text.splitlines()
    assert lines[0].startswith("CONFIDENTIAL - exported by dave (" + w.users["dave"]["uid"])
    assert lines[-1] == lines[0] and "UTC" in lines[0] and w.case_a in lines[0]
    assert "password_protected" in text and "ocr_failed" in text
    assert (path.stat().st_mode & 0o077) == 0
    rec = [r for r in w.app.audit.records() if r["action"] == "export" and r["outcome"] == "ok"][-1]
    assert rec["actor"] == w.users["dave"]["uid"] and len(rec["detail"]["sha256"]) == 64


def test_pdf_export_watermark_on_every_page(ingested, tmp_path):
    import pypdfium2 as pdfium

    w = ingested
    path = w.app.export(w.ctx("alice", w.case_a, Perm.EXPORT), "documents", "pdf", tmp_path)
    pdf = pdfium.PdfDocument(path.read_bytes())
    assert len(pdf) >= 1
    for page in pdf:
        assert "exported by alice" in page.get_textpage().get_text_range()


def test_csv_formula_injection_neutralized(ingested, tmp_path, monkeypatch):
    from lexreview import export as ex

    w = ingested
    monkeypatch.setattr(ex, "_rows", lambda *a: (["a"], [["=HYPERLINK(\"http://exfil.example\")"]], "s"))
    path = w.app.export(w.ctx("alice", w.case_a, Perm.EXPORT), "coverage", "csv", tmp_path)
    assert "'=HYPERLINK" in path.read_text()
