"""Phase 2: hybrid search. Cited, verified, permission-filtered results;
'not found'; recall on the labeled synthetic set."""

import json

import pytest

from lexreview.authz import Perm
from lexreview.errors import AccessDenied, NotFound
from lexreview.search.hybrid import to_fts_query

RECALL_FLOOR = 0.8   # minimum acceptable recall per labeled topic


def search(w, user, q, case=None, top_k=50):
    return w.app.search(w.ctx(user, case or w.case_a, Perm.SEARCH), q, top_k)


def test_every_result_is_cited_and_verified(ingested):
    w = ingested
    res = search(w, "alice", "temperature excursion notice within two hours")
    assert res["results"] and res["integrity_failures"] == 0
    store = w.app.store(w.ctx("alice", w.case_a))
    for h in res["results"]:
        page = store.get_page(w.ctx("alice", w.case_a), h["doc_id"], h["page_no"])
        assert page.text[h["char_start"]:h["char_end"]] == h["snippet"]
        assert h["link"] == f"/ui/cases/{w.case_a}/docs/{h['doc_id']}/pages/{h['page_no']}?hl={h['char_start']}-{h['char_end']}#hl"
        assert h["locator"] and h["band"] in ("strong", "moderate", "weak")
    assert "coverage" in res and res["coverage"]["documents_not_searchable"] >= 8
    assert res["documents_searched"] == res["coverage"]["documents_searchable"]


def test_top_hit_is_the_contract_clause(ingested):
    w = ingested
    res = search(w, "bob", "how long can product be outside 2 to 8 degrees before it is an excursion")
    top = res["results"][:3]
    assert any(h["source_name"].endswith("master_services_agreement.pdf") and h["page_no"] == 4 for h in top)


def test_ocr_and_spreadsheet_and_attachment_found(ingested):
    w = ingested
    names = {h["source_name"] for h in search(w, "alice", "trailer 4471 rejected pallets 11.4", top_k=200)["results"]}
    assert "docs/scans/delivery_receipt_0412.pdf" in names          # OCR'd scan
    assert "docs/logs/shipment_log_2023.xlsx" in names               # spreadsheet row
    assert any(n.endswith("::attachment::recorder_4471.pdf") for n in names)  # email attachment


def test_not_found(ingested):
    res = search(ingested, "alice", "zebra xylophone quantum chromodynamics")
    assert res["not_found"] and res["message"] == "Not found in the reviewed documents."
    assert res["results"] == [] and "coverage" in res


def test_unrelated_query_never_strong(ingested):
    res = search(ingested, "alice", "quarterly dividend policy for shareholders")
    assert all(h["band"] == "weak" for h in res["results"])


def test_restricted_doc_never_returned_or_counted(ingested):
    w = ingested
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    q = "Section 7.3 is amended to require notice within one hour"
    res = search(w, "bob", q, top_k=500)
    assert amend not in {h["doc_id"] for h in res["results"]}
    assert amend not in {d["doc_id"] for d in res["documents"]}
    ctx = w.ctx("bob", w.case_a)
    assert res["documents_searched"] == w.app.store(ctx).searchable_visible_count(w.ctx("bob", w.case_a, Perm.SEARCH))


def test_restricted_doc_found_with_grant(ingested):
    w = ingested
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    w.app.grant_label(w.p("alice"), w.case_a, w.users["alice"]["uid"], "aeo")
    res = search(w, "alice", "Section 7.3 is amended to require notice within one hour")
    assert amend in {h["doc_id"] for h in res["results"][:5]}


def test_cross_case_search_isolated(ingested):
    w = ingested
    a_docs = {d["doc_id"] for d in w.docs.values()}
    res = search(w, "carol", "temperature excursion trailer 4471 deposition", case=w.case_b, top_k=500)
    assert res["results"]  # case B holds the contracts
    assert not ({h["doc_id"] for h in res["results"]} & a_docs)
    assert all(h["source_name"].startswith("docs/contracts/") for h in res["results"])
    with pytest.raises(AccessDenied):
        search(w, "alice", "anything", case=w.case_b)


def test_fts_syntax_is_neutralized(ingested):
    assert to_fts_query('x" OR text:* NEAR(a b) ^col -foo') == '"text" OR "near" OR "col" OR "foo"'
    for q in ['"', "*", "NEAR(", "text:", "a AND", "((", "\\", "'; DROP TABLE chunks; --"]:
        res = search(ingested, "alice", q)
        assert isinstance(res["results"], list)


def test_query_text_not_in_audit_but_stored_encrypted(ingested):
    w = ingested
    q = "unique query about Okafor phone call CANARY-QUERY-91"
    res = search(w, "bob", q)
    raw = (w.app.root / "audit" / "audit.log").read_text()
    assert "CANARY-QUERY-91" not in raw and "Okafor" not in raw
    rec = [r for r in w.app.audit.records() if r["action"] == "search"][-1]
    assert rec["detail"]["query_id"] == res["query_id"] and len(rec["detail"]["query_digest"]) == 32
    row = w.app.store(w.ctx("bob", w.case_a)).conn.execute(
        "SELECT query_text FROM queries WHERE query_id=?", (res["query_id"],)).fetchone()
    assert row[0] == q
    assert all(b"CANARY-QUERY-91" not in p.read_bytes() for p in w.data_root.rglob("*") if p.is_file())


def test_reviewer_marks_recorded_and_audited(ingested):
    w = ingested
    res = search(w, "bob", "cargo claim insurer denied late notice")
    h = res["results"][0]
    mid = w.app.mark(w.ctx("bob", w.case_a, Perm.MARK), h["doc_id"], h["page_no"], "relevant", res["query_id"])
    marks = w.app.store(w.ctx("bob", w.case_a)).marks_for(w.ctx("bob", w.case_a), h["doc_id"])
    assert any(m["mark_id"] == mid and m["user_id"] == w.users["bob"]["uid"] and m["label"] == "relevant" for m in marks)
    rec = [r for r in w.app.audit.records() if r["action"] == "mark"][-1]
    assert rec["target"] == h["doc_id"] and rec["detail"]["label"] == "relevant"


def test_cannot_mark_hidden_or_foreign_doc(ingested):
    w = ingested
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    with pytest.raises(NotFound):
        w.app.mark(w.ctx("bob", w.case_a, Perm.MARK), amend, 1, "relevant", None)
    ctx_b = w.ctx("carol", w.case_b)
    b_doc = w.app.store(ctx_b).list_documents(ctx_b)[0]["doc_id"]
    with pytest.raises(NotFound):
        w.app.mark(w.ctx("bob", w.case_a, Perm.MARK), b_doc, 1, "relevant", None)


def test_page_image_rendered_in_sandbox(ingested):
    w = ingested
    ctx = w.ctx("bob", w.case_a)
    scan = w.docs["docs/scans/delivery_receipt_0412.pdf"]["doc_id"]
    png = w.app.page_image(ctx, scan, 1)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert w.app.page_image(ctx, w.docs["docs/emails/e05.eml"]["doc_id"], 1) is None
    with pytest.raises(NotFound):
        w.app.page_image(ctx, w.docs["docs/contracts/amendment_1.docx"]["doc_id"], 1)


def test_vector_index_encrypted_and_per_case(ingested):
    w = ingested
    for case in (w.case_a, w.case_b):
        blob = (w.app.root / "cases" / case / "vectors.bin").read_bytes()
        assert blob.startswith(b"LXR1") and b"okafor" not in blob.lower() and b"lsa_terms" not in blob


def test_recall_on_labeled_synthetic_set(ingested, labels, capsys):
    """Recall evaluation: for each labeled instruction, how many known-relevant
    documents appear anywhere in the returned document list."""
    w = ingested
    w.app.grant_label(w.p("alice"), w.case_a, w.users["alice"]["uid"], "aeo")  # evaluate over all docs
    name = {d["doc_id"]: d["source_name"] for d in w.docs.values()}
    report = {}
    for topic, spec in labels["topics"].items():
        res = search(w, "alice", spec["instruction"], top_k=50)
        found = {name.get(d["doc_id"]) for d in res["documents"]}
        rel = set(spec["relevant"])
        report[topic] = {"found": len(rel & found), "relevant": len(rel), "returned_docs": len(found),
                         "missed": sorted(rel - found)}
    with capsys.disabled():
        print("\nRECALL REPORT " + json.dumps(report, indent=1))
    for topic, r in report.items():
        assert r["found"] / r["relevant"] >= RECALL_FLOOR, (topic, r)
