"""Ingestion: formats, page mapping, OCR, attachments, and every failure
mode ending up in the coverage report (no silent gaps)."""

import json

import pytest

from lexreview.authz import Perm
from lexreview.config import load_settings
from lexreview.ingest.sandbox import run_parser


def status(w, name):
    return w.docs[name]["status"], w.docs[name]["reason"]


EXPECTED = {
    "docs/adversarial/corrupted.pdf": "corrupted",
    "docs/adversarial/protected.pdf": "password_protected",
    "docs/adversarial/protected.docx": "password_protected",
    "docs/adversarial/zipbomb.docx": "rejected_unsafe",
    "docs/adversarial/decompression_bomb.png": "rejected_unsafe",
    "docs/adversarial/unknown.bin": "unsupported",
    "docs/adversarial/legacy.doc": "unsupported",
    "docs/scans/blank_scan_0007.pdf": "ocr_failed",
    "docs/emails/e04_copy.eml": "duplicate",
    "docs/contracts/master_services_agreement.pdf": "indexed",
    "docs/contracts/amendment_1.docx": "indexed",
    "docs/depositions/okafor_deposition_vol1.pdf": "indexed",
    "docs/depositions/lindqvist_deposition.docx": "indexed",
    "docs/logs/shipment_log_2023.xlsx": "indexed",
    "docs/scans/delivery_receipt_0412.pdf": "indexed",
    "docs/scans/bill_of_lading_88213.png": "indexed",
    "docs/large/production_vol2.pdf": "indexed",
    "docs/adversarial/injection_email.eml": "indexed",
}


@pytest.mark.parametrize("name,expected", sorted(EXPECTED.items()))
def test_file_status(ingested, name, expected):
    assert ingested.docs[name]["status"] == expected


def test_every_manifest_file_accounted_for(ingested, corpus):
    manifest = json.loads((corpus / "MANIFEST.json").read_text())
    top_level = {n for n, d in ingested.docs.items() if d["parent_id"] is None}
    assert top_level == set(manifest["files"])


def test_coverage_lists_every_gap(ingested):
    rep = ingested.app.coverage(ingested.ctx("alice", ingested.case_a))
    gaps = {g["source_name"]: g["status"] for g in rep["not_searchable"]}
    for name, st in EXPECTED.items():
        if st not in ("indexed", "indexed_low_confidence", "duplicate"):
            assert gaps.get(name) == st, name
    assert rep["documents_searchable"] + rep["documents_not_searchable"] + rep["by_status"].get("duplicate", 0) \
        == rep["documents_total_visible"]


def test_pdf_page_mapping(ingested):
    w = ingested
    ctx = w.ctx("alice", w.case_a)
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]
    assert msa["page_count"] == 8
    assert "7.2 Excursions" in w.app.view_page(ctx, msa["doc_id"], 4).text
    assert "7.2 Excursions" not in w.app.view_page(ctx, msa["doc_id"], 3).text
    dep = w.docs["docs/depositions/okafor_deposition_vol1.pdf"]
    assert "11.4 degrees" in w.app.view_page(ctx, dep["doc_id"], 7).text
    big = w.docs["docs/large/production_vol2.pdf"]
    assert big["page_count"] == 600
    assert "HPCS-000412" in w.app.view_page(ctx, big["doc_id"], 412).text


def test_ocr_scanned_pdf(ingested):
    w = ingested
    d = w.docs["docs/scans/delivery_receipt_0412.pdf"]
    pg = w.app.view_page(w.ctx("alice", w.case_a), d["doc_id"], 1)
    assert pg.ocr and pg.ocr_conf > 60
    assert "REJECTED" in pg.text and "4471" in pg.text


def test_docx_locators(ingested):
    w = ingested
    ctx = w.ctx("alice", w.case_a)
    dep = w.docs["docs/depositions/lindqvist_deposition.docx"]
    pages = [w.app.view_page(ctx, dep["doc_id"], n) for n in range(1, dep["page_count"] + 1)]
    assert all("¶" in p.locator for p in pages)
    hit = [p for p in pages if "unmonitored inbox" in p.text]
    assert len(hit) == 1 and hit[0].locator == "¶121–¶160"


def test_xlsx_locator(ingested):
    w = ingested
    x = w.docs["docs/logs/shipment_log_2023.xlsx"]
    pg = w.app.view_page(w.ctx("alice", w.case_a), x["doc_id"], 1)
    assert pg.locator.startswith("Shipments!rows 1") and "YES - high" in pg.text


def test_email_attachment_is_child_document(ingested):
    w = ingested
    parent = w.docs["docs/emails/e05.eml"]
    kids = [d for d in w.docs.values() if d["parent_id"] == parent["doc_id"]]
    assert len(kids) == 1 and kids[0]["source_name"].endswith("::attachment::recorder_4471.pdf")
    assert kids[0]["status"] == "indexed"
    assert "11.4C" in w.app.view_page(w.ctx("alice", w.case_a), kids[0]["doc_id"], 1).text


def test_html_email_script_stripped(ingested):
    w = ingested
    d = w.docs["docs/emails/e02.eml"]  # generated with an HTML alternative
    text = w.app.view_page(w.ctx("alice", w.case_a), d["doc_id"], 1).text
    assert "trailer 4410" in text


def test_too_large_file_recorded(world, corpus, monkeypatch):
    monkeypatch.setattr(world.app, "settings", load_settings().__class__(
        **{**world.app.settings.__dict__, "max_file_bytes": 100_000}))
    ctx = world.ctx("alice", world.case_a, Perm.INGEST)
    world.app.ingest(ctx, corpus / "docs" / "large")
    docs = world.app.store(ctx).list_documents(world.ctx("alice", world.case_a))
    assert [(d["status"], d["reason"]) for d in docs] == [("too_large", "file_size_limit")]


def test_page_limit_recorded(app, corpus):
    s = app.settings.__class__(**{**app.settings.__dict__, "max_pages": 100})
    r = run_parser((corpus / "docs/large/production_vol2.pdf").read_bytes(), s, app.root / "tmp")
    assert (r.status, r.reason) == ("too_large", "page_limit")


def test_parser_timeout_recorded(app, corpus):
    r = run_parser((corpus / "docs/scans/delivery_receipt_0412.pdf").read_bytes(), app.settings,
                   app.root / "tmp", timeout=1)
    assert r.status == "timeout"


def test_parser_memory_limit(app, corpus):
    # Rendering a 300 dpi page for OCR needs far more than 48 MB of address space.
    s = app.settings.__class__(**{**app.settings.__dict__, "parse_mem_bytes": 48 * 1024 * 1024})
    r = run_parser((corpus / "docs/scans/delivery_receipt_0412.pdf").read_bytes(), s, app.root / "tmp")
    assert r.status in ("parse_error", "rejected_unsafe", "ocr_failed")
    assert r.status != "indexed"


def test_parser_tmp_dirs_cleaned(ingested):
    tmp = ingested.app.root / "tmp"
    assert not tmp.exists() or list(tmp.iterdir()) == []


def test_sandbox_is_network_isolated(ingested):
    w = ingested
    meta = w.app.store(w.ctx("alice", w.case_a)).conn.execute(
        "SELECT DISTINCT json_extract(meta_json, '$.sandbox') FROM documents WHERE kind != 'duplicate'").fetchall()
    assert {m[0] for m in meta if m[0]} == {"isolated"}
