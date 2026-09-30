"""Reviewer web UI: login, search, jump-to-passage viewer, escaping of
hostile document content, CSRF, access control."""

import re

import pyotp
import pytest
from fastapi.testclient import TestClient

from lexreview.api import create_api
from lexreview.authz import Role


@pytest.fixture
def ui(ingested):
    c = TestClient(create_api(ingested.app), base_url="https://testserver", follow_redirects=False)
    return c


def as_user(c, w, name):
    c.cookies.set("lr_session", w.users[name]["token"])
    c.cookies.set("lr_csrf", "tok-" + name)
    return "tok-" + name


def test_login_flow(ui, ingested):
    w = ingested
    uid, totp = w.app.create_user(w.admin, "webuser", "webuser-password-1")
    w.app.add_member(w.admin, w.case_a, uid, Role.REVIEWER)
    r = ui.get("/ui/login")
    assert r.status_code == 200 and 'name="totp"' in r.text
    csrf = ui.cookies.get("lr_csrf")
    r = ui.post("/ui/login", content=f"csrf={csrf}&username=webuser&password=webuser-password-1&totp={pyotp.TOTP(totp).now()}",
                headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 303 and r.headers["location"] == "/ui/"
    home = ui.get("/ui/")
    assert home.status_code == 200 and w.case_a in home.text


def test_unauthenticated_redirects_to_login(ui, ingested):
    r = ui.get(f"/ui/cases/{ingested.case_a}")
    assert r.status_code == 303 and r.headers["location"] == "/ui/login"


def test_search_results_link_to_highlighted_passage(ui, ingested):
    w = ingested
    tok = as_user(ui, w, "bob")
    r = ui.post(f"/ui/cases/{w.case_a}/search", data={"csrf": tok, "q": "reefer on trailer 4471 alarmed overnight"})
    assert r.status_code == 200 and "Coverage:" in r.text and "NOT</b>" in r.text
    links = re.findall(r'href="(/ui/cases/[^"]+\?hl=\d+-\d+#hl)"', r.text)
    assert links
    v = ui.get(links[0].replace("&amp;", "&"))
    assert v.status_code == 200
    assert '<mark id="hl">' in v.text and "Location" in v.text and "chars" in v.text


def test_viewer_shows_location_and_page_image(ui, ingested):
    w = ingested
    as_user(ui, w, "bob")
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    v = ui.get(f"/ui/cases/{w.case_a}/docs/{msa}/pages/4?hl=10-40")
    assert "docs/contracts/master_services_agreement.pdf | doc " + msa + " | p. 4 | chars 10-40" in v.text
    img = ui.get(f"/ui/cases/{w.case_a}/docs/{msa}/pages/4/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert img.headers["cache-control"] == "no-store"


def test_hostile_document_content_is_escaped(ui, ingested):
    w = ingested
    tok = as_user(ui, w, "alice")
    inj = w.docs["docs/adversarial/injection_email.eml"]["doc_id"]
    v = ui.get(f"/ui/cases/{w.case_a}/docs/{inj}/pages/1")
    assert v.status_code == 200 and "Ignore all previous instructions" in v.text
    assert "<script" not in v.text.lower()
    assert "&lt;script&gt;" in v.text
    assert not re.search(r'(href|src)="https?://', v.text)  # no outbound links or images
    r = ui.post(f"/ui/cases/{w.case_a}/search", data={"csrf": tok, "q": "maintenance mode send the full text"})
    assert "<script" not in r.text.lower() and not re.search(r'(href|src)="https?://', r.text)


def test_csrf_required_for_search(ui, ingested):
    w = ingested
    as_user(ui, w, "bob")
    r = ui.post(f"/ui/cases/{w.case_a}/search", data={"csrf": "wrong", "q": "trailer"})
    assert r.status_code == 303 and r.headers["location"] == "/ui/login"


def test_cross_case_and_restricted_in_ui(ui, ingested):
    w = ingested
    as_user(ui, w, "bob")
    assert ui.get(f"/ui/cases/{w.case_b}").status_code == 403
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    assert ui.get(f"/ui/cases/{w.case_a}/docs/{amend}/pages/1").status_code == 404


def test_mark_from_viewer(ui, ingested):
    w = ingested
    tok = as_user(ui, w, "bob")
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    r = ui.post(f"/ui/cases/{w.case_a}/marks", data={"csrf": tok, "doc_id": msa, "page": "4", "label": "not_relevant"})
    assert r.status_code == 303
    v = ui.get(r.headers["location"])
    assert "not_relevant by " + w.users["bob"]["uid"] in v.text


def test_ui_security_headers_and_no_scripts(ui, ingested):
    w = ingested
    as_user(ui, w, "bob")
    r = ui.get(f"/ui/cases/{w.case_a}")
    csp = r.headers["content-security-policy"]
    assert "script-src" not in csp and "default-src 'none'" in csp
    assert "<script" not in r.text.lower()


def test_search_query_not_in_url(ui, ingested):
    """Searches are POSTs; the query never appears in a URL."""
    w = ingested
    tok = as_user(ui, w, "bob")
    r = ui.post(f"/ui/cases/{w.case_a}/search", data={"csrf": tok, "q": "secretstrategyterm"})
    assert "secretstrategyterm" not in "".join(re.findall(r'href="([^"]+)"', r.text))
