"""Phase 3: extraction of dates, people, organizations and events; the
cited timeline."""

from datetime import date

import pytest

from lexreview.authz import Perm
from lexreview.citations import VerifiedQuote, verify_quote
from lexreview.errors import AccessDenied
from lexreview.extract.dates import find_dates, fmt, resolve_years
from lexreview.extract.segments import segments


def tl(w, user="alice", case=None, **kw):
    return w.app.timeline(w.ctx(user, case or w.case_a, Perm.SEARCH), **kw)


# ------------------------------------------------------------------ dates
def test_date_formats_and_flags():
    t = ("Signed April 28, 2023. Load 04/13/2023; cal 03/04/2023; old 4/13/23; ISO 2023-04-12; "
         "claim in May 2023; 13 Apr 2023; you may 5 times; Feb 30, 2023; the next morning, April 13.")
    ms = find_dates(t)
    resolve_years(ms, None)
    got = {m.text: (fmt(m), m.flags) for m in ms}
    assert got["April 28, 2023"] == ("2023-04-28", [])
    assert got["04/13/2023"] == ("2023-04-13", [])
    assert got["03/04/2023"] == ("2023-03-04", ["ambiguous_day_month"])
    assert got["4/13/23"] == ("2023-04-13", ["two_digit_year"])
    assert got["2023-04-12"][0] == "2023-04-12"
    assert got["May 2023"][0] == "2023-05 (month)"
    assert got["13 Apr 2023"][0] == "2023-04-13"
    assert got["April 13"] == ("2023-04-13", ["year_inferred_from_context"])
    assert got["the next morning"][0] == "unresolved"
    assert "may 5" not in {k.lower() for k in got}          # verb, not month
    assert got["Feb 30"][0] == "unresolved"                 # impossible date not invented


def test_year_from_email_date_picks_nearest_year():
    ms = find_dates("the shipment on December 30 was late")
    resolve_years(ms, date(2024, 1, 3))
    assert fmt(ms[0]) == "2023-12-30" and ms[0].flags == ["year_inferred_from_doc_date"]


def test_regexes_resist_pathological_input():
    import time
    hostile = ("April " * 20000) + ("1/" * 20000) + ("A " * 50000) + "Mr. " * 20000
    t0 = time.time()
    find_dates(hostile)
    segments(hostile)
    from lexreview.extract.entities import org_candidates, people_candidates
    people_candidates([hostile], [])
    org_candidates([hostile])
    assert time.time() - t0 < 10


# ------------------------------------------------------------------ entities
def test_people_and_orgs(ingested):
    w = ingested
    ents = w.app.entities(w.ctx("alice", w.case_a, Perm.SEARCH))
    people = {e["name"] for e in ents if e["kind"] == "person"}
    orgs = {e["name"] for e in ents if e["kind"] == "org"}
    assert {"Dana Okafor", "Elaine Voss", "Victor Lindqvist", "Tomas Ferreira", "Priya Raman", "Jordan Hale",
            "Jane Whitcomb"} <= people
    assert "Harbor Point" not in people                      # an org alias is not a person
    assert {"Harbor Point Cold Storage Inc", "Meridian Freightways LLC", "Calibra Testing Services Inc"} <= orgs


def test_every_mention_is_a_real_span(ingested):
    w = ingested
    ctx = w.ctx("alice", w.case_a)
    store = w.app.store(ctx)
    rows = store.conn.execute("SELECT e.name, m.doc_id, m.page_no, m.char_start, m.char_end, m.method "
                              "FROM mentions m JOIN entities e ON e.entity_id=m.entity_id").fetchall()
    assert rows
    for name, doc, page, s, e, method in rows:
        text = store.conn.execute("SELECT text FROM pages WHERE doc_id=? AND page_no=?", (doc, page)).fetchone()[0]
        span = text[s:e]
        assert span in (name, name.split()[-1]) or method == "alias", (name, span, method)


# ------------------------------------------------------------------ timeline
def test_every_timeline_entry_cites_a_verifiable_passage(ingested):
    w = ingested
    w.app.grant_label(w.p("alice"), w.case_a, w.users["alice"]["uid"], "aeo")
    ctx = w.ctx("alice", w.case_a)
    store = w.app.store(ctx)
    res = tl(w, include_rows=True)
    assert res["events"] and res["integrity_failures"] == 0
    for e in res["events"]:
        page = store.get_page(ctx, e["doc_id"], e["page_no"])
        assert page.text[e["char_start"]:e["char_end"]] == e["passage"]
        assert e["date_text"] in e["passage"]
        if len(e["passage"]) >= 12:
            assert isinstance(verify_quote(store, ctx, e["doc_id"], e["page_no"], e["passage"]), VerifiedQuote)
        assert e["link"].endswith(f"?hl={e['char_start']}-{e['char_end']}#hl")
    dates = [e["date_start"] for e in res["events"]]
    assert dates == sorted(dates)


def test_key_events_present(ingested):
    w = ingested
    evs = tl(w, date_from=date(2023, 1, 1), date_to=date(2023, 12, 31))["events"]

    def has(d, needle, src):
        return any(e["date_start"] == d and needle in e["passage"] and e["source_name"].endswith(src) for e in evs)
    assert has("2023-01-09", "effective January 9, 2023", "master_services_agreement.pdf")
    assert has("2023-04-12", "trailer 4471", "okafor_deposition_vol1.pdf")        # wrapped transcript line
    assert has("2023-04-13", "next morning, April 13", "okafor_deposition_vol1.pdf")
    assert has("2023-04-12", "alarmed overnight on April 12", "e05.eml")
    assert has("2023-04-13", "REJECTED", "delivery_receipt_0412.pdf")             # OCR'd scan
    assert has("2023-03-13", "March 13 near Lodi", "e02.eml")
    ocr = [e for e in evs if e["source_name"].endswith("delivery_receipt_0412.pdf")]
    assert ocr and all(e["ocr"] for e in ocr)


def test_inferred_and_ambiguous_dates_are_flagged(ingested):
    evs = tl(ingested)["events"]
    lodi = next(e for e in evs if "March 13 near Lodi" in e["passage"])
    assert lodi["flags"] == ["year_inferred_from_doc_date"]
    cal = next(e for e in evs if e["date_text"] == "03/04/2023")
    assert "ambiguous_day_month" in cal["flags"]
    due = next(e for e in evs if e["date_text"] == "9/1/23")
    assert "two_digit_year" in due["flags"] and due["date_start"] == "2023-09-01"


def test_unplaced_dates_are_listed_not_guessed(ingested):
    res = tl(ingested)
    un = {(u["date_text"], u["source_name"]) for u in res["unplaced"]}
    assert ("last Tuesday", "docs/emails/e15.eml") in un
    assert ("April 12", "docs/depositions/lindqvist_deposition.docx") in un   # no year anywhere in that doc
    assert not any(e["passage"].find("last Tuesday") >= 0 and e["date_text"] == "last Tuesday" for e in res["events"])


def test_date_range_and_person_filters(ingested):
    w = ingested
    res = tl(w, date_from=date(2023, 3, 1), date_to=date(2023, 6, 30))
    assert res["events"] and all("2023-03-01" <= e["date_end"] and e["date_start"] <= "2023-06-30" for e in res["events"])
    ents = w.app.entities(w.ctx("alice", w.case_a, Perm.SEARCH))
    tomas = next(e["entity_id"] for e in ents if e["name"] == "Tomas Ferreira")
    only = tl(w, entity_id=tomas)["events"]
    assert only and all(any(x["name"] == "Tomas Ferreira" for x in e["entities"]) for e in only)


def test_table_rows_hidden_but_counted(ingested):
    w = ingested
    default = tl(w)
    full = tl(w, include_rows=True)
    assert default["hidden_table_rows"] >= 400
    assert len(full["events"]) == len(default["events"]) + default["hidden_table_rows"]
    assert any(e["source_name"].endswith(".xlsx") and "YES - high" in e["passage"] for e in full["events"])


def test_restricted_document_events_hidden(ingested):
    w = ingested
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    evs = tl(w, "bob")["events"]
    assert amend not in {e["doc_id"] for e in evs}
    assert not any("April 28, 2023" in e["passage"] for e in evs)


def test_cross_case_timeline_isolated(ingested):
    w = ingested
    a_docs = {d["doc_id"] for d in w.docs.values()}
    res = tl(w, "carol", case=w.case_b)
    assert res["events"] and not ({e["doc_id"] for e in res["events"]} & a_docs)
    with pytest.raises(AccessDenied):
        tl(w, "carol", case=w.case_a)


def test_injection_document_only_creates_events_citing_itself(ingested):
    """Text inside a hostile document cannot create or alter events that
    cite other documents: every event's passage is a span of its own doc."""
    w = ingested
    inj = {w.docs["docs/adversarial/injection_email.eml"]["doc_id"], w.docs["docs/adversarial/injection_memo.pdf"]["doc_id"]}
    for e in tl(w, include_rows=True)["events"]:
        if "Ignore all previous instructions" in e["passage"] or "exfil" in e["passage"]:
            assert e["doc_id"] in inj


def test_timeline_audited_without_content(ingested):
    w = ingested
    tl(w, "bob", date_from=date(2023, 4, 1))
    rec = [r for r in w.app.audit.records() if r["action"] == "timeline"][-1]
    assert rec["actor"] == w.users["bob"]["uid"] and rec["detail"]["date_from"] == "2023-04-01"


def test_timeline_export_watermarked(ingested, tmp_path):
    w = ingested
    path = w.app.export(w.ctx("dave", w.case_a, Perm.EXPORT), "timeline", "csv", tmp_path)
    text = path.read_text()
    assert text.startswith("CONFIDENTIAL - exported by dave") and "2023-04-13" in text and "UNPLACED" in text
