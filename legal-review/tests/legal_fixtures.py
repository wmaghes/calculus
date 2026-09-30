"""SYNTHETIC API FIXTURES - NOT REAL LEGAL AUTHORITY.

Fake responses shaped like the documented CourtListener / eCFR / govinfo
APIs and the assumed HTML of the Ohio and Michigan code sites. Every case
name, citation and section number here is invented and marked FIXTURE, so
nothing in the test suite can be mistaken for real law.
"""

import json

import httpx

CL_SEARCH = {"count": 4, "results": [
    {"cluster_id": 900001, "caseName": "Fixture Freight Co. v. Example Cold Storage (FIXTURE)",
     "citation": ["999 Fixture App.3d 1"], "dateFiled": "2020-05-01", "court": "Court of Appeals of Ohio (FIXTURE)", "court_id": "ohioctapp",
     "absolute_url": "/opinion/900001/fixture-freight-co-v-example-cold-storage/",
     "opinions": [{"snippet": "carrier liable for <mark>temperature</mark> damage <script>alert(1)</script>"}]},
    {"cluster_id": 900002, "caseName": "Nonexistent Holdings v. Ghost (FIXTURE)", "citation": ["1 Fake 1"],
     "dateFiled": "2019-01-01", "court": "X", "court_id": "ohio", "absolute_url": "/opinion/900002/ghost/", "opinions": []},
    {"cluster_id": 900003, "caseName": "Mismatch v. Name (FIXTURE)", "citation": [], "dateFiled": "2018-01-01",
     "court": "X", "court_id": "ca6", "absolute_url": "/opinion/900003/mismatch/", "opinions": []},
    {"cluster_id": 900005, "caseName": "Out Of Filter v. Texas (FIXTURE)", "citation": [], "dateFiled": "2017-01-01",
     "court": "Texas (FIXTURE)", "court_id": "tex", "absolute_url": "/opinion/900005/x/", "opinions": []},
    {"cluster_id": 900004, "caseName": "Redirect Trick v. Example (FIXTURE)", "citation": [], "dateFiled": "2021-02-02",
     "court": "Supreme Court of Michigan (FIXTURE)", "court_id": "mich", "absolute_url": "javascript:alert(document.cookie)", "opinions": []},
]}
CL_CLUSTERS = {
    "900001": {"id": 900001, "case_name": "Fixture Freight Co. v. Example Cold Storage (FIXTURE)", "date_filed": "2020-05-01",
               "citations": [{"volume": 999, "reporter": "Fixture App.3d", "page": 1}]},
    "900003": {"id": 900003, "case_name": "Completely Different Case (FIXTURE)", "date_filed": "2018-01-01", "citations": []},
    "900004": {"id": 900004, "case_name": "Redirect Trick v. Example (FIXTURE)", "date_filed": "2021-02-02", "citations": []},
}
ECFR_SEARCH = {"results": [
    {"hierarchy": {"title": "49", "section": "9999.1"}, "headings": {"section": "FIXTURE temperature records"},
     "starts_on": "2022-01-01", "full_text_excerpt": "FIXTURE text"},
    {"hierarchy": {"title": "49", "section": "9999.2"}, "headings": {"section": "FIXTURE unverifiable"}, "starts_on": "2022-01-01"},
]}
ECFR_VERSIONS = {"content_versions": [{"identifier": "9999.1", "name": "FIXTURE"}]}
OHIO_SEARCH = ('<html><a href="/ohio-revised-code/section-9999.01">x</a>'
               '<a href="/ohio-revised-code/section-9999.02">y</a></html>')
OHIO_9999_01 = ('<html><h1>Section 9999.01 | FIXTURE carrier duties (not real law)</h1>'
                '<p>Effective: 2021-01-01</p></html>')


class Legal:
    """MockTransport handler. Records every request; `mode` switches failures."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.mi_status = 503
        self.huge = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host, path = request.url.host, request.url.path
        if self.huge:
            return httpx.Response(200, content=b"x" * (3 * 1024 * 1024))
        if host == "www.courtlistener.com":
            if path == "/api/rest/v4/search/":
                return httpx.Response(200, json=CL_SEARCH)
            cid = path.rstrip("/").split("/")[-1]
            if path.startswith("/api/rest/v4/clusters/") and cid in CL_CLUSTERS:
                return httpx.Response(200, json=CL_CLUSTERS[cid])
            return httpx.Response(404, json={"detail": "Not found."})
        if host == "www.ecfr.gov":
            if path == "/api/search/v1/results":
                return httpx.Response(200, json=ECFR_SEARCH)
            if path == "/api/versioner/v1/versions/title-49.json":
                sec = request.url.params.get("section")
                return httpx.Response(200, json=ECFR_VERSIONS if sec == "9999.1" else {"content_versions": []})
        if host == "codes.ohio.gov":
            if path == "/search":
                return httpx.Response(200, text=OHIO_SEARCH)
            if path == "/ohio-revised-code/section-9999.01":
                return httpx.Response(200, text=OHIO_9999_01)
            return httpx.Response(404, text="not found")
        if host == "www.legislature.mi.gov":
            return httpx.Response(self.mi_status, text="service unavailable")
        if host == "api.govinfo.gov":
            return httpx.Response(500, text="err")
        return httpx.Response(599, text="unexpected host in fixture")


_ = json
