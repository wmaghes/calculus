"""Source adapters for legal authority. Every adapter has two steps:

    search(query, jurisdiction)  -> candidates (from the source's own search)
    verify(candidate)            -> the candidate re-fetched BY ID from the
                                    same source and cross-checked (name /
                                    citation / section number / date), or None

Only verified candidates are ever shown. Nothing here comes from a model's
memory: titles, citations and dates are copied from the source's response.

Adapter status (see SECURITY.md R30):
    courtlistener  v4 REST API (search + clusters)     - tested with fixtures shaped on the documented API
    ecfr           eCFR search + versioner APIs        - tested with fixtures shaped on the documented API
    govinfo        govinfo search + granule summary    - tested with fixtures; needs an api.data.gov key
    ohio_code      codes.ohio.gov HTML (search + section page)      - HTML parsing NOT validated against the live site
    mi_code        legislature.mi.gov HTML (search + MCL section)   - HTML parsing NOT validated against the live site
    sec_edgar      EDGAR full-text search + filing index JSON       - tested with fixtures shaped on the public endpoints;
                                                                      SEC requires a User-Agent with contact details
    ohio_ethics    Ohio Board of Professional Conduct opinions      - HTML/URL patterns NOT validated against the live site
    mi_ethics      State Bar of Michigan ethics opinions            - HTML/URL patterns NOT validated against the live site
All must be validated live in the firm's environment before use.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass

from .gateway import LegalGateway, SourceUnavailable

JURISDICTIONS = {
    # CourtListener court ids. Verify against the live /courts/ endpoint.
    "ohio": {"label": "Ohio", "courts": ["ohio", "ohioctapp", "ohnd", "ohsd", "ca6"], "code": "ohio_code"},
    "michigan": {"label": "Michigan", "courts": ["mich", "michctapp", "mied", "miwd", "ca6"], "code": "mi_code"},
    "federal": {"label": "Federal (6th Cir. / U.S.)", "courts": ["ca6", "scotus"], "code": None},
}
# Jurisdiction shown on a case lead comes from the court that decided it,
# never from the search filter that found it.
COURT_JURISDICTION = {
    "ohio": "Ohio (Supreme Court)", "ohioctapp": "Ohio (Court of Appeals)",
    "mich": "Michigan (Supreme Court)", "michctapp": "Michigan (Court of Appeals)",
    "ohnd": "Federal (N.D. Ohio)", "ohsd": "Federal (S.D. Ohio)",
    "mied": "Federal (E.D. Mich.)", "miwd": "Federal (W.D. Mich.)",
    "ca6": "Federal (6th Cir.)", "scotus": "Federal (U.S. Supreme Court)",
}
SOURCES = ("courtlistener", "ohio_code", "mi_code", "ecfr", "govinfo", "sec_edgar", "ohio_ethics", "mi_ethics")
_TAG = re.compile(r"<[^>]{0,500}>")


@dataclass
class Candidate:
    source: str
    source_id: str
    kind: str            # case | statute | regulation
    title: str
    citation: str | None
    jurisdiction: str
    body: str | None     # court or code
    date: str | None
    url: str
    snippet: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def clean(text, limit: int = 600) -> str | None:
    """Untrusted response text -> plain text (tags removed, entities decoded,
    whitespace collapsed, length capped). The UI escapes it again."""
    if text is None:
        return None
    t = html.unescape(_TAG.sub(" ", str(text)))
    t = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", t)
    return " ".join(t.split())[:limit] or None


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ---------------------------------------------------------------- CourtListener
class CourtListener:
    name = "courtlistener"
    BASE = "https://www.courtlistener.com/api/rest/v4"

    def __init__(self, gw: LegalGateway):
        self.gw = gw

    def _headers(self) -> dict:
        tok = self.gw.secret("LEXREVIEW_COURTLISTENER_TOKEN_REF")
        return {"Authorization": f"Token {tok}"} if tok else {}

    def search(self, query: str, jurisdiction: str) -> list[Candidate]:
        j = JURISDICTIONS[jurisdiction]
        r = self.gw.get(f"{self.BASE}/search/", params={"q": query, "type": "o", "court": " ".join(j["courts"])},
                        headers=self._headers())
        if r.status_code != 200:
            raise SourceUnavailable(f"http_{r.status_code}")
        out = []
        for res in (r.json().get("results") or [])[:20]:
            cid = str(res.get("cluster_id") or "")
            if not cid.isdigit():
                continue
            court_id = str(res.get("court_id") or "")
            if court_id not in j["courts"]:
                continue  # outside the requested courts (or unknown): not shown
            cites = res.get("citation") or []
            snip = (res.get("opinions") or [{}])[0].get("snippet") if res.get("opinions") else res.get("snippet")
            out.append(Candidate(self.name, cid, "case", clean(res.get("caseName"), 300) or "",
                                 clean("; ".join(map(str, cites)), 200), COURT_JURISDICTION[court_id], clean(res.get("court"), 120),
                                 clean(res.get("dateFiled"), 10), self._url(res.get("absolute_url"), cid), clean(snip)))
        return out

    @staticmethod
    def _url(absolute_url, cid: str) -> str:
        # Never trust a URL from the response: accept only the expected shape
        # on the expected host, else build one from the verified id.
        if isinstance(absolute_url, str) and re.fullmatch(r"/opinion/\d{1,12}/[a-z0-9\-]{0,200}/", absolute_url):
            return "https://www.courtlistener.com" + absolute_url
        return f"https://www.courtlistener.com/opinion/{cid}/"

    def verify(self, c: Candidate) -> Candidate | None:
        r = self.gw.get(f"{self.BASE}/clusters/{c.source_id}/", headers=self._headers())
        if r.status_code != 200:
            return None
        d = r.json()
        if str(d.get("id")) != c.source_id or _norm(d.get("case_name")) != _norm(c.title):
            return None
        if c.date and d.get("date_filed") and str(d["date_filed"])[:10] != c.date:
            return None
        cites = ["{} {} {}".format(x.get("volume"), x.get("reporter"), x.get("page")) for x in d.get("citations") or []
                 if isinstance(x, dict)]
        if cites:
            c.citation = clean("; ".join(cites), 200)
        return c


# ---------------------------------------------------------------- eCFR
class ECFR:
    name = "ecfr"
    BASE = "https://www.ecfr.gov/api"

    def __init__(self, gw: LegalGateway):
        self.gw = gw

    def search(self, query: str, jurisdiction: str) -> list[Candidate]:
        if jurisdiction != "federal":
            return []
        r = self.gw.get(f"{self.BASE}/search/v1/results", params={"query": query, "per_page": 10})
        if r.status_code != 200:
            raise SourceUnavailable(f"http_{r.status_code}")
        out = []
        for res in (r.json().get("results") or [])[:10]:
            h = res.get("hierarchy") or {}
            t, sec = str(h.get("title") or ""), str(h.get("section") or "")
            if not (t.isdigit() and re.fullmatch(r"\d{1,4}\.\d{1,6}[a-z]?", sec)):
                continue
            out.append(Candidate(self.name, f"{t}:{sec}", "regulation",
                                 clean((res.get("headings") or {}).get("section"), 300) or f"{t} CFR {sec}",
                                 f"{t} C.F.R. § {sec}", JURISDICTIONS["federal"]["label"], "Code of Federal Regulations",
                                 clean(res.get("starts_on"), 10), f"https://www.ecfr.gov/current/title-{t}/section-{sec}",
                                 clean(res.get("full_text_excerpt"))))
        return out

    def verify(self, c: Candidate) -> Candidate | None:
        t, sec = c.source_id.split(":", 1)
        r = self.gw.get(f"{self.BASE}/versioner/v1/versions/title-{t}.json", params={"section": sec})
        if r.status_code != 200:
            return None
        versions = r.json().get("content_versions") or []
        return c if any(str(v.get("identifier")) == sec for v in versions if isinstance(v, dict)) else None


# ---------------------------------------------------------------- govinfo
class GovInfo:
    name = "govinfo"
    BASE = "https://api.govinfo.gov"

    def __init__(self, gw: LegalGateway):
        self.gw = gw

    def _key(self) -> str:
        key = self.gw.secret("LEXREVIEW_GOVINFO_KEY_REF")
        if not key:
            raise SourceUnavailable("api_key_not_configured")
        return key

    def search(self, query: str, jurisdiction: str) -> list[Candidate]:
        if jurisdiction != "federal":
            return []
        r = self.gw.get(f"{self.BASE}/search", params={"api_key": self._key()},
                        json_body={"query": f"({query}) AND collection:(USCODE)", "pageSize": 10, "offsetMark": "*"})
        if r.status_code != 200:
            raise SourceUnavailable(f"http_{r.status_code}")
        out = []
        for res in (r.json().get("results") or [])[:10]:
            pkg, gran = str(res.get("packageId") or ""), str(res.get("granuleId") or "")
            if not (re.fullmatch(r"[A-Za-z0-9\-]{1,80}", pkg) and re.fullmatch(r"[A-Za-z0-9\-]{1,120}", gran)):
                continue
            out.append(Candidate(self.name, f"{pkg}/{gran}", "statute", clean(res.get("title"), 300) or gran, None,
                                 JURISDICTIONS["federal"]["label"], "United States Code", clean(res.get("dateIssued"), 10),
                                 f"https://www.govinfo.gov/app/details/{pkg}/{gran}", None))
        return out

    def verify(self, c: Candidate) -> Candidate | None:
        pkg, gran = c.source_id.split("/", 1)
        r = self.gw.get(f"{self.BASE}/packages/{pkg}/granules/{gran}/summary", params={"api_key": self._key()})
        if r.status_code != 200:
            return None
        d = r.json()
        if str(d.get("granuleId")) != gran or _norm(d.get("title")) != _norm(c.title):
            return None
        return c


# ---------------------------------------------------------------- state codes (HTML)
class OhioCode:
    """codes.ohio.gov. HTML structure assumed; NOT validated live."""

    name = "ohio_code"
    BASE = "https://codes.ohio.gov"

    def __init__(self, gw: LegalGateway):
        self.gw = gw

    def search(self, query: str, jurisdiction: str) -> list[Candidate]:
        if jurisdiction != "ohio":
            return []
        r = self.gw.get(f"{self.BASE}/search", params={"q": query})
        if r.status_code != 200:
            raise SourceUnavailable(f"http_{r.status_code}")
        secs = list(dict.fromkeys(re.findall(r'href="/ohio-revised-code/section-(\d{1,4}\.\d{1,4})"', r.text)))[:10]
        return [Candidate(self.name, s, "statute", f"R.C. {s}", f"R.C. {s}", "Ohio", "Ohio Revised Code", None,
                          f"{self.BASE}/ohio-revised-code/section-{s}", None) for s in secs]

    def verify(self, c: Candidate) -> Candidate | None:
        r = self.gw.get(f"{self.BASE}/ohio-revised-code/section-{c.source_id}")
        if r.status_code != 200:
            return None
        m = re.search(r"<h1[^>]{0,200}>\s*Section\s+" + re.escape(c.source_id) + r"\s*\|\s*([^<]{1,300})</h1>", r.text)
        if not m:
            return None
        c.title = f"R.C. {c.source_id} | {clean(m.group(1), 250)}"
        eff = re.search(r"Effective:\s*([0-9/\-]{8,10})", r.text)
        c.date = clean(eff.group(1), 10) if eff else None
        return c


class MichiganCode:
    """legislature.mi.gov. HTML structure assumed; NOT validated live."""

    name = "mi_code"
    BASE = "https://www.legislature.mi.gov"

    def __init__(self, gw: LegalGateway):
        self.gw = gw

    def search(self, query: str, jurisdiction: str) -> list[Candidate]:
        if jurisdiction != "michigan":
            return []
        r = self.gw.get(f"{self.BASE}/Search/ExecuteSearch", params={"docTypes": "MCL", "contentFullText": query})
        if r.status_code != 200:
            raise SourceUnavailable(f"http_{r.status_code}")
        ids = list(dict.fromkeys(re.findall(r"objectName=mcl-(\d{1,4}-\d{1,5}[a-z]?)", r.text)))[:10]
        return [Candidate(self.name, i, "statute", f"MCL {i.replace('-', '.', 1)}", f"MCL {i.replace('-', '.', 1)}",
                          "Michigan", "Michigan Compiled Laws", None, f"{self.BASE}/Laws/MCL?objectName=mcl-{i}", None)
                for i in ids]

    def verify(self, c: Candidate) -> Candidate | None:
        r = self.gw.get(f"{self.BASE}/Laws/MCL", params={"objectName": f"mcl-{c.source_id}"})
        if r.status_code != 200:
            return None
        sec = c.source_id.replace("-", ".", 1)
        m = re.search(r"Section\s+" + re.escape(sec) + r"\b[^<]{0,20}</[^>]{1,10}>\s*(?:<[^>]{1,100}>\s*){0,3}([^<]{3,300})", r.text)
        if not m:
            return None
        c.title = f"MCL {sec} | {clean(m.group(1), 250)}"
        return c


# ---------------------------------------------------------------- SEC EDGAR
class SecEdgar:
    """Public company filings (facts, not legal authority). Federal only.
    SEC's fair-access policy requires a descriptive User-Agent with contact
    details: LEXREVIEW_SEC_USER_AGENT (e.g. "Firm Name it-contact@firm.example")."""

    name = "sec_edgar"

    def __init__(self, gw: LegalGateway):
        self.gw = gw

    def _headers(self) -> dict:
        import os

        ua = os.environ.get("LEXREVIEW_SEC_USER_AGENT", "")
        if not re.fullmatch(r"[A-Za-z0-9 .,&()'\-]{3,80} [\w.+-]{1,64}@[\w-]{1,63}(\.[\w-]{1,63}){1,4}", ua):
            raise SourceUnavailable("sec_user_agent_not_configured")
        return {"User-Agent": ua}

    def search(self, query: str, jurisdiction: str) -> list[Candidate]:
        if jurisdiction != "federal":
            return []
        r = self.gw.get("https://efts.sec.gov/LATEST/search-index", params={"q": query}, headers=self._headers())
        if r.status_code != 200:
            raise SourceUnavailable(f"http_{r.status_code}")
        out = []
        for hit in ((r.json().get("hits") or {}).get("hits") or [])[:10]:
            src = hit.get("_source") or {}
            _id = str(hit.get("_id") or "")
            adsh, _, fname = _id.partition(":")
            ciks = src.get("ciks") or []
            if not (re.fullmatch(r"\d{10}-\d{2}-\d{6}", adsh) and re.fullmatch(r"[A-Za-z0-9._\-]{1,120}", fname)
                    and ciks and re.fullmatch(r"\d{1,10}", str(ciks[0]))):
                continue
            cik = str(int(str(ciks[0])))
            names = src.get("display_names") or []
            out.append(Candidate(self.name, f"{cik}/{adsh}/{fname}", "filing",
                                 f"{clean(src.get('form'), 20) or 'Filing'}: {clean(names[0] if names else '', 200) or 'unknown filer'}",
                                 f"SEC accession {adsh}", "Federal (SEC filing)", "SEC EDGAR", clean(src.get("file_date"), 10),
                                 f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fname}", None))
        return out

    def verify(self, c: Candidate) -> Candidate | None:
        cik, adsh, fname = c.source_id.split("/", 2)
        r = self.gw.get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/index.json",
                        headers=self._headers())
        if r.status_code != 200:
            return None
        items = ((r.json().get("directory") or {}).get("item") or [])
        return c if any(isinstance(i, dict) and i.get("name") == fname for i in items) else None


# ---------------------------------------------------------------- bar ethics opinions (HTML, unvalidated)
class _EthicsOpinions:
    """Advisory ethics opinions. Search results are links on the official
    site; verification re-fetches the opinion URL on the same host and
    requires the opinion number in the page (HTML) or a PDF body.
    URL patterns are ASSUMED and must be validated live."""

    name = ""
    host = ""
    juris = ""
    label = ""
    body = ""
    search_path = ""
    search_param = ""
    link_re: re.Pattern = re.compile("(?!)")

    def __init__(self, gw: LegalGateway):
        self.gw = gw

    def search(self, query: str, jurisdiction: str) -> list[Candidate]:
        if jurisdiction != self.juris:
            return []
        r = self.gw.get(f"https://{self.host}{self.search_path}", params={self.search_param: query})
        if r.status_code != 200:
            raise SourceUnavailable(f"http_{r.status_code}")
        out, seen = [], set()
        for m in self.link_re.finditer(r.text):
            path, number = m.group("path"), m.group("num")
            if path in seen:
                continue
            seen.add(path)
            out.append(Candidate(self.name, path, "ethics_opinion", f"{self.label} {number}", f"{self.label} {number}",
                                 self.juris.capitalize(), self.body, None, f"https://{self.host}{path}", None))
            if len(out) >= 10:
                break
        return out

    def verify(self, c: Candidate) -> Candidate | None:
        r = self.gw.get(f"https://{self.host}{c.source_id}")
        if r.status_code != 200:
            return None
        number = c.citation.rsplit(" ", 1)[-1]
        if r.content[:5] == b"%PDF-":
            c.snippet = "PDF opinion: existence confirmed on the official site; content not parsed. Read it at the source."
            return c
        m = re.search(r"<title>([^<]{0,300})</title>", r.text)
        if number not in r.text:
            return None
        if m:
            c.title = f"{c.citation} | {clean(m.group(1), 200)}"
        return c


class OhioEthics(_EthicsOpinions):
    name, host, juris = "ohio_ethics", "www.bpc.ohio.gov", "ohio"
    label, body = "Ohio Bd. Prof. Conduct Adv. Op.", "Ohio Board of Professional Conduct"
    search_path, search_param = "/", "s"
    link_re = re.compile(r'href="https://www\.bpc\.ohio\.gov(?P<path>/[A-Za-z0-9/_\-.]{1,200}?(?P<num>\d{4}-\d{2})[A-Za-z0-9_\-.]{0,40})"')


class MichiganEthics(_EthicsOpinions):
    name, host, juris = "mi_ethics", "www.michbar.org", "michigan"
    label, body = "State Bar of Mich. Ethics Op.", "State Bar of Michigan"
    search_path, search_param = "/opinions/ethics/search", "q"
    link_re = re.compile(r'href="(?P<path>/opinions/ethics/numbered_opinions/(?P<num>(?:RI|RE|R|CI)-\d{1,4}))"')


ADAPTERS = {"courtlistener": CourtListener, "ecfr": ECFR, "govinfo": GovInfo, "ohio_code": OhioCode, "mi_code": MichiganCode,
            "sec_edgar": SecEdgar, "ohio_ethics": OhioEthics, "mi_ethics": MichiganEthics}
