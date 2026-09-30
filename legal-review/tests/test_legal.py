"""Phase 5: legal-authority leads (Rule 2) with human approval of every
outbound query. All source responses are SYNTHETIC fixtures (tests/legal_fixtures.py)."""

import re
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from lexreview.api import create_api
from lexreview.authz import Perm
from lexreview.errors import AccessDenied, ConfigError
from lexreview.legal.gateway import LEGAL_HOSTS, LegalGateway, SourceUnavailable
from lexreview.legal.leads import CITATOR_NOTICE, LEAD_LABEL

from legal_fixtures import Legal

GENERIC = "carrier liability for temperature-controlled cargo damage"
ALL_SOURCES = ["courtlistener", "ecfr", "ohio_code", "mi_code", "govinfo"]


@pytest.fixture
def legal(ingested, monkeypatch):
    fx = Legal()
    monkeypatch.setattr(ingested.app, "legal_gateway", LegalGateway(transport=httpx.MockTransport(fx), enabled=True))
    return fx


def ctx(w, name, perm):
    return w.app.authorize(w.p(name), w.case_a, perm)


def propose(w, text=GENERIC, sources=("courtlistener",), juris=("ohio", "michigan"), user="dave"):
    return w.app.legal_propose(ctx(w, user, Perm.LEGAL_PROPOSE), text, list(sources), list(juris))


def approve(w, qid, user="dave", ack=False):
    return w.app.legal_decide(ctx(w, user, Perm.LEGAL_APPROVE), qid, True, ack)


def run(w, qid, user="dave"):
    return w.app.legal_run(ctx(w, user, Perm.LEGAL_PROPOSE), qid)


# ------------------------------------------------------------------ approval
def test_nothing_is_sent_without_approval(ingested, legal):
    r = propose(ingested)
    assert r["status"] == "proposed"
    with pytest.raises(AccessDenied):
        run(ingested, r["query_id"])
    assert legal.requests == []


def test_rejected_query_is_never_sent(ingested, legal):
    w = ingested
    qid = propose(w)["query_id"]
    w.app.legal_decide(ctx(w, "dave", Perm.LEGAL_APPROVE), qid, False)
    with pytest.raises(AccessDenied):
        run(w, qid)
    assert legal.requests == []


def test_reviewer_cannot_propose_or_approve(ingested, legal):
    w = ingested
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("bob"), w.case_a, Perm.LEGAL_PROPOSE)
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("bob"), w.case_a, Perm.LEGAL_APPROVE)


def test_document_text_is_blocked(ingested, legal):
    r = propose(ingested, "Meridian shall maintain product between 2 and 8 degrees Celsius")
    assert r["status"] == "blocked" and "copied from a case document" in r["reasons"][0]
    assert all(q["text"] != "Meridian shall maintain product between 2 and 8 degrees Celsius"
               for q in ingested.app.legal_queries(ctx(ingested, "dave", Perm.SEARCH)))


def test_case_names_and_numbers_need_acknowledgement(ingested, legal):
    w = ingested
    r = propose(w, "Meridian Freightways liability trailer 4471")
    assert r["status"] == "proposed" and len(r["warnings"]) == 2
    assert "Meridian Freightways LLC" in r["warnings"][0] and "4471" in " ".join(r["warnings"])
    with pytest.raises(ConfigError):
        approve(w, r["query_id"])
    assert approve(w, r["query_id"], ack=True)["status"] == "approved"


def test_approval_is_bound_to_exact_text(ingested, legal):
    w = ingested
    qid = propose(w)["query_id"]
    approve(w, qid)
    store = w.app.store(ctx(w, "dave", Perm.VIEW))
    store.conn.execute("UPDATE legal_queries SET text=? WHERE query_id=?", (GENERIC + " Harbor Point", qid))
    with pytest.raises(AccessDenied):
        run(w, qid)
    store.conn.execute("UPDATE legal_queries SET text=?, sources=? WHERE query_id=?", (GENERIC, '["courtlistener","govinfo"]', qid))
    with pytest.raises(AccessDenied):   # destinations changed after approval
        run(w, qid)
    assert legal.requests == []


def test_sends_exact_text_only_to_approved_sources_once(ingested, legal):
    w = ingested
    qid = propose(w, sources=("courtlistener", "ohio_code"), juris=("ohio",))["query_id"]
    approve(w, qid)
    run(w, qid)
    hosts = {r.url.host for r in legal.requests}
    assert hosts <= LEGAL_HOSTS and hosts == {"www.courtlistener.com", "codes.ohio.gov"}
    searches = [r for r in legal.requests if r.url.path in ("/api/rest/v4/search/", "/search")]
    for r in searches:
        q = parse_qs(r.url.query.decode())
        assert q.get("q") == [GENERIC]
    cl = [r for r in searches if r.url.host == "www.courtlistener.com"][0]
    assert parse_qs(cl.url.query.decode())["court"] == ["ohio ohioctapp ohnd ohsd ca6"]
    n = len(legal.requests)
    with pytest.raises(AccessDenied):
        run(w, qid)                      # one approval, one send
    assert len(legal.requests) == n


# ------------------------------------------------------------------ verification
def test_only_verified_authority_is_shown(ingested, legal):
    w = ingested
    qid = propose(w, sources=ALL_SOURCES, juris=("ohio", "michigan", "federal"))["query_id"]
    approve(w, qid)
    res = run(w, qid)
    titles = {ld["title"] for ld in res["leads"]}
    assert "Fixture Freight Co. v. Example Cold Storage (FIXTURE)" in titles
    assert not any("Ghost" in t or "Mismatch" in t for t in titles)          # 404 / name mismatch at source
    assert any(t.startswith("R.C. 9999.01 | FIXTURE") for t in titles)       # verified section page
    assert not any("9999.02" in t for t in titles)
    assert any(ld["citation"] == "49 C.F.R. § 9999.1" for ld in res["leads"])
    assert not any("9999.2" in (ld["citation"] or "") for ld in res["leads"])
    st = res["source_status"]
    assert st["courtlistener"]["discarded_unverifiable"] == 2
    assert st["ohio_code"]["discarded_unverifiable"] == 1 and st["ecfr"]["discarded_unverifiable"] == 1


def test_every_lead_is_labelled(ingested, legal):
    w = ingested
    qid = propose(w, sources=("courtlistener", "ohio_code"), juris=("ohio",))["query_id"]
    approve(w, qid)
    for ld in run(w, qid)["leads"]:
        assert ld["label"] == LEAD_LABEL == "Lead for attorney verification"
        assert ld["citator_notice"] == CITATOR_NOTICE and "NOT been checked" in ld["citator_notice"]
        assert ld["jurisdiction"].startswith(("Ohio", "Michigan", "Federal"))
        assert ld["retrieved_at"] and ld["url"].startswith("https://")
    fx = [ld for ld in run_leads(w, qid) if ld["source_id"] == "900001"][0]
    assert fx["date"] == "2020-05-01" and fx["citation"] == "999 Fixture App.3d 1"
    assert fx["jurisdiction"] == "Ohio (Court of Appeals)"   # from the deciding court, not the search filter


def test_results_outside_requested_courts_are_dropped(ingested, legal):
    w = ingested
    qid = propose(w, sources=("courtlistener",), juris=("ohio",))["query_id"]
    approve(w, qid)
    leads = run(w, qid)["leads"]
    assert not any("Texas" in ld["title"] for ld in leads)
    assert not any(ld["jurisdiction"].startswith("Michigan") for ld in leads)


def run_leads(w, qid):
    return w.app.legal_leads(ctx(w, "dave", Perm.SEARCH), qid)["leads"]


def test_unreachable_sources_are_reported_not_filled(ingested, legal, monkeypatch):
    w = ingested
    monkeypatch.delenv("LEXREVIEW_GOVINFO_KEY_REF", raising=False)
    qid = propose(w, sources=("mi_code", "govinfo", "courtlistener"), juris=("michigan", "federal"))["query_id"]
    approve(w, qid)
    res = run(w, qid)
    st = res["source_status"]
    assert st["mi_code"]["unavailable"] == "http_503" and st["mi_code"]["verified"] == 0
    assert st["govinfo"]["unavailable"] == "api_key_not_configured"
    assert {ld["source"] for ld in res["leads"]} == {"courtlistener"}


def test_hostile_response_content_is_neutralized(ingested, legal):
    w = ingested
    qid = propose(w, sources=("courtlistener",), juris=("ohio", "michigan"))["query_id"]
    approve(w, qid)
    leads = run(w, qid)["leads"]
    fx = [ld for ld in leads if ld["source_id"] == "900001"][0]
    assert "<script" not in (fx["snippet"] or "") and "<mark>" not in (fx["snippet"] or "")
    trick = [ld for ld in leads if ld["source_id"] == "900004"][0]
    assert trick["url"] == "https://www.courtlistener.com/opinion/900004/"   # javascript: URL rejected
    ui = TestClient(create_api(w.app), base_url="https://testserver")
    ui.cookies.set("lr_session", w.users["dave"]["token"])
    html = ui.get(f"/ui/cases/{w.case_a}/legal/{qid}").text
    assert "javascript:" not in html and "<script" not in html.lower()
    for href in re.findall(r'href="([^"]+)"', html):
        assert href.startswith("/") or re.match(r"https://(www\.courtlistener\.com|codes\.ohio\.gov|www\.legislature\.mi\.gov|www\.ecfr\.gov|www\.govinfo\.gov)/", href)
    assert 'rel="noreferrer noopener"' in html
    assert "Lead for attorney verification" in html and "NOT been checked" in html


def test_oversized_response_refused(ingested, legal):
    w = ingested
    legal.huge = True
    qid = propose(w, sources=("courtlistener",), juris=("ohio",))["query_id"]
    approve(w, qid)
    res = run(w, qid)
    assert res["source_status"]["courtlistener"]["unavailable"] == "response_too_large" and res["leads"] == []


# ------------------------------------------------------------------ gateway
def test_gateway_refuses_non_allowlisted_and_plain_http():
    gw = LegalGateway(transport=httpx.MockTransport(lambda r: httpx.Response(200)), enabled=True)
    for url in ("https://exfil.example/x", "http://www.courtlistener.com/api/", "https://courtlistener.com.evil.example/"):
        with pytest.raises(ConfigError):
            gw.get(url)


def test_gateway_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LEXREVIEW_LEGAL_SOURCES", raising=False)
    with pytest.raises(SourceUnavailable):
        LegalGateway(transport=httpx.MockTransport(lambda r: httpx.Response(200))).get("https://www.ecfr.gov/api/x")


def test_gateway_refuses_redirects():
    gw = LegalGateway(transport=httpx.MockTransport(
        lambda r: httpx.Response(302, headers={"Location": "https://exfil.example/"})), enabled=True)
    with pytest.raises(SourceUnavailable) as e:
        gw.get("https://www.ecfr.gov/api/search/v1/results")
    assert e.value.reason == "redirect_refused"


# ------------------------------------------------------------------ audit & UI
def test_legal_workflow_audited_without_query_text(ingested, legal):
    w = ingested
    text = "fixture unique legal issue phrase zyxw"
    qid = propose(w, text, sources=("courtlistener",), juris=("ohio",))["query_id"]
    approve(w, qid)
    run(w, qid)
    recs = [r for r in w.app.audit.records() if r["action"].startswith("legal_") and r.get("target") == qid]
    assert [r["action"] for r in recs] == ["legal_propose", "legal_decide", "legal_send"]
    assert recs[1]["actor"] == w.users["dave"]["uid"] and recs[1]["outcome"] == "approved"
    assert recs[2]["detail"]["sent_sha256"] == recs[1]["detail"]["approved_sha256"]
    assert "zyxw" not in (w.app.root / "audit" / "audit.log").read_text()


def test_ui_propose_approve_run(ingested, legal):
    w = ingested
    ui = TestClient(create_api(w.app), base_url="https://testserver", follow_redirects=False)
    ui.cookies.set("lr_session", w.users["dave"]["token"])
    ui.cookies.set("lr_csrf", "t")
    page = ui.post(f"/ui/cases/{w.case_a}/legal/propose",
                   data={"csrf": "t", "text": "cargo insurance claim denial late notice", "src_courtlistener": "1", "jur_ohio": "1"})
    assert "will not be sent until an attorney approves" in page.text and "Approve exact text" in page.text
    qid = re.findall(r"/legal/(lq_[0-9a-f]{16})/decide", page.text)[0]
    assert ui.post(f"/ui/cases/{w.case_a}/legal/{qid}/decide", data={"csrf": "t", "decision": "approve"}).status_code == 303
    r = ui.post(f"/ui/cases/{w.case_a}/legal/{qid}/run", data={"csrf": "t"})
    leads = ui.get(r.headers["location"]).text
    assert "Fixture Freight Co." in leads and "Lead for attorney verification" in leads
    blocked = ui.post(f"/ui/cases/{w.case_a}/legal/propose",
                      data={"csrf": "t", "text": "Meridian shall maintain product between 2 and 8 degrees", "src_courtlistener": "1", "jur_ohio": "1"})
    assert "Not saved" in blocked.text
    bob = TestClient(create_api(w.app), base_url="https://testserver")
    bob.cookies.set("lr_session", w.users["bob"]["token"])
    assert "Approve exact text" not in bob.get(f"/ui/cases/{w.case_a}/legal").text
