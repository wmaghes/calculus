"""Citation verification.

Nothing is shown to a user as a quotation unless this module has confirmed
that the quoted passage actually occurs on the cited page of the cited
document, in the stored page text, and that the requesting user may see that
document.

Matching is exact after a fixed, documented normalization that only removes
differences in *presentation*, never in wording:
    * Unicode NFKC (ligatures like "ﬁ" -> "fi", full-width forms)
    * curly quotes -> straight quotes; en/em dashes and minus -> "-"
    * soft hyphens removed; a hyphen at a line break joined ("exam-\\nple" -> "example")
    * any run of whitespace -> one space; leading/trailing whitespace ignored
Case, punctuation and word order must match exactly. A quote shorter than
MIN_QUOTE_CHARS is rejected as too weak to verify anything.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .authz import CaseAccessContext
from .casestore import CaseStore
from .errors import NotFound

MIN_QUOTE_CHARS = 12

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
    "­": None,
})


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Normalize and return, for each output char, its index in `text`."""
    out: list[str] = []
    idx: list[int] = []
    i, n = 0, len(text)
    pending_space = False
    while i < n:
        ch = text[i]
        # Hyphen at end of line followed by a letter: drop hyphen + break.
        if ch in "-‐‑­" and i + 1 < n and text[i + 1] == "\n":
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j].isalpha() and out and out[-1].isalpha():
                i = j
                continue
        if ch.isspace():
            pending_space = bool(out)
            i += 1
            continue
        norm = unicodedata.normalize("NFKC", ch).translate(_TRANSLATE)
        if norm and pending_space:
            out.append(" ")
            idx.append(i)
            pending_space = False
        for c in norm:
            out.append(c)
            idx.append(i)
        i += 1
    return "".join(out), idx


def normalize(text: str) -> str:
    return normalize_with_map(text)[0]


@dataclass(frozen=True)
class VerifiedQuote:
    doc_id: str
    page_no: int
    locator: str
    char_start: int
    char_end: int
    exact_text: str      # the passage as stored on the page
    ocr: bool
    ocr_conf: float | None


@dataclass(frozen=True)
class Rejected:
    reason: str          # quote_too_short | doc_or_page_not_found | quote_not_on_page


def verify_quote(store: CaseStore, ctx: CaseAccessContext, doc_id: str, page_no: int, quote: str) -> VerifiedQuote | Rejected:
    q = normalize(quote or "")
    if len(q) < MIN_QUOTE_CHARS:
        return Rejected("quote_too_short")
    try:
        page = store.get_page(ctx, doc_id, int(page_no))
    except (NotFound, ValueError, TypeError):
        return Rejected("doc_or_page_not_found")
    norm, index = normalize_with_map(page.text)
    pos = norm.find(q)
    if pos < 0:
        return Rejected("quote_not_on_page")
    start = index[pos]
    end = index[pos + len(q) - 1] + 1
    return VerifiedQuote(doc_id, page.page_no, page.locator, start, end, page.text[start:end], page.ocr, page.ocr_conf)
