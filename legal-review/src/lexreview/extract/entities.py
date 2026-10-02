"""People and organization extraction (rule-based, per case).

People come from high-precision sources only, then are matched everywhere:
  * email From/To/Cc display names
  * honorifics (Mr./Ms./Mrs./Dr./Judge/Hon.) + capitalized name
  * "DEPOSITION OF FIRST LAST"
  * role nouns ("driver Tomas Ferreira", "Director ... Victor Lindqvist")
  * "Signed ... by First Last" / "Signed: First Last"
Once known, a person's full name is matched in every document; a surname
alone is matched only when it is unique among known people (method
"surname", shown as lower confidence).

Organizations: names ending in a corporate suffix (Inc., LLC, Corp., Co.,
Ltd., LLP, LP, PLLC, P.C.), the same name without the suffix, and defined
terms such as (the "Harbor Point").

This is recall-limited by design (no statistical NER model): people who are
never named in a high-precision position are missed. SECURITY.md R21.
"""

from __future__ import annotations

import re
from email.utils import getaddresses

_NAME = r"[A-Z][a-z'\-]{1,20}(?:\s[A-Z]\.)?\s[A-Z][a-z'\-]{1,24}"
_HONORIFIC = re.compile(r"\b(?:Mr|Ms|Mrs|Dr|Judge|Hon)\.?\s(" + r"[A-Z][a-z'\-]{1,20}(?:\s[A-Z][a-z'\-]{1,24})?" + r")")
_DEPO = re.compile(r"DEPOSITION OF ([A-Z][A-Z'\-]{1,20}\s[A-Z][A-Z'\-]{1,24})")
_ROLE = re.compile(r"\b(?:[Dd]river|[Dd]ispatcher|[Mm]anager|Director(?: of [A-Z][a-z]{1,20})?|CFO|CEO|COO|[Ww]itness|[Dd]eponent|[Cc]ounsel|[Ss]upervisor)\s(" + _NAME + r")")
_SIGNED = re.compile(r"\bSigned(?:[^.\n]{0,40}?\bby)?:?\s(" + _NAME + r")(?:,[^.\n]{0,40})?(?:\sand\s(" + _NAME + r"))?")
_SIGNED_LIST = re.compile(r"(" + _NAME + r"),\s(?:CFO|CEO|COO|Director|President|Manager)")
_SUFFIX = r"(?:Inc|LLC|L\.L\.C|Corp|Corporation|Company|Co|Ltd|LLP|LP|PLLC|P\.C)"
_ORG = re.compile(r"\b((?:[A-Z][A-Za-z&'\-]{1,24}\s){0,4}[A-Z][A-Za-z&'\-]{1,24}),?\s(" + _SUFFIX + r")\b\.?")
_DEFINED = re.compile(r"\(\s?(?:the\s)?[\"“]([A-Z][A-Za-z ]{1,40})[\"”]\s?\)")
_STOP_ORG_WORDS = {"The", "This", "Each", "Any", "Signed", "Between", "And"}


def _clean_person(name: str) -> str | None:
    name = " ".join(w.capitalize() if w.isupper() else w for w in name.split())
    parts = name.split()
    if len(parts) < 2 or any(p in _STOP_ORG_WORDS for p in parts):
        return None
    return name


def people_candidates(page_texts: list[str], email_meta: list[dict]) -> set[str]:
    names: set[str] = set()
    for meta in email_meta:
        for field in ("from", "to", "cc"):
            for disp, _addr in getaddresses([meta.get(field) or ""]):
                n = _clean_person(disp.strip().strip('"'))
                if n:
                    names.add(n)
    for text in page_texts:
        for rx in (_DEPO, _ROLE, _SIGNED_LIST):
            for m in rx.finditer(text):
                n = _clean_person(m.group(1))
                if n:
                    names.add(n)
        for m in _SIGNED.finditer(text):
            for g in m.groups():
                n = _clean_person(g) if g else None
                if n:
                    names.add(n)
        for m in _HONORIFIC.finditer(text):
            n = _clean_person(m.group(1))
            if n:
                names.add(n)
    return names


def org_candidates(page_texts: list[str]) -> dict[str, set[str]]:
    """canonical name -> aliases (including canonical)."""
    orgs: dict[str, set[str]] = {}
    for text in page_texts:
        for m in _ORG.finditer(text):
            words = m.group(1).split()
            while words and words[0] in _STOP_ORG_WORDS:
                words = words[1:]
            if not words:
                continue
            base = " ".join(words)
            canon = f"{base} {m.group(2).rstrip('.')}"
            key = _org_key(base)
            existing = next((c for c in orgs if _org_key(c) == key), None)
            canon = existing or canon
            aliases = orgs.setdefault(canon, {canon})
            if len(words) >= 2:
                aliases.add(base)
            after = text[m.end(): m.end() + 60]
            d = _DEFINED.match(after.lstrip(" ,"))
            if d:
                aliases.add(d.group(1).strip())
    return orgs


def _org_key(base: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(rf",?\s{_SUFFIX}\.?$", "", base).lower())


def find_all(text: str, needle: str) -> list[tuple[int, int]]:
    rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(needle) + r"(?![A-Za-z0-9])")
    return [m.span() for m in rx.finditer(text)]
