"""Date mention extraction and normalization.

Every mention keeps its exact span. Values are ranges (start, end) so
month- and year-precision dates are honest about what they say.

Flags (always shown to reviewers):
    year_inferred_from_doc_date   "April 12" in an email; year taken from the email's Date header
    year_inferred_from_context    year taken from the nearest full date in the same document
    ambiguous_day_month           e.g. 03/04/2023; read as US month/day (Ohio/Michigan practice)
    two_digit_year                e.g. 4/13/23 read as 2023
Relative expressions ("the next morning", "last Tuesday") are recorded as
UNRESOLVED and listed separately; they are never silently placed on the
timeline.

All regexes use bounded repetition only (no nested unbounded quantifiers),
so hostile text cannot cause catastrophic backtracking.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9,
    "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_M = r"(?<![A-Za-z])(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)"
_ORD = r"(?:st|nd|rd|th)?"
_YEAR = r"((?:19|20)\d{2})"

PATTERNS = [  # (name, regex) in priority order; earlier wins on overlap
    ("iso", re.compile(r"\b((?:19|20)\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])\b")),
    ("mdy_num", re.compile(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/((?:19|20)\d{2}|\d{2})\b")),
    ("month_day_year", re.compile(_M + r"\.?\s{1,3}(\d{1,2})" + _ORD + r",?\s{1,3}" + _YEAR + r"\b")),
    ("day_month_year", re.compile(r"\b(\d{1,2})" + _ORD + r"\s{1,3}" + _M + r"\.?,?\s{1,3}" + _YEAR + r"\b")),
    ("month_year", re.compile(_M + r"\.?,?\s{1,3}" + _YEAR + r"\b")),
    # No year: weakest pattern, so it may not span a line break ("in May.\n4 Q. ...").
    ("month_day", re.compile(_M + r"\.?[ \t]{1,3}(\d{1,2})" + _ORD + r"\b")),
]
_RELATIVE = re.compile(
    r"\b(yesterday|today|tomorrow|tonight|overnight|"
    r"(?:last|next|this)\s(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month|year|night|morning)|"
    r"the\s(?:next|following|previous|prior)\s(?:day|morning|evening|night|week|month))\b", re.I)


@dataclass
class DateMention:
    start: int
    end: int
    text: str
    kind: str                       # pattern name, or "relative"
    value_start: date | None = None
    value_end: date | None = None
    precision: str | None = None    # day | month | year
    flags: list[str] = field(default_factory=list)
    needs_year: bool = False
    month: int | None = None
    day: int | None = None

    @property
    def resolved(self) -> bool:
        return self.value_start is not None


def _month(tok: str) -> int:
    return _MONTHS[tok.lower().rstrip(".")]


def _mk(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[DateMention]:
    taken: list[tuple[int, int]] = []
    out: list[DateMention] = []

    def free(s: int, e: int) -> bool:
        return all(e <= a or s >= b for a, b in taken)

    for name, rx in PATTERNS:
        for m in rx.finditer(text):
            s, e = m.span()
            if not free(s, e):
                continue
            g = m.groups()
            dm = DateMention(s, e, m.group(0), name)
            if name in ("month_day_year", "month_year", "month_day") and g[0].lower() == "may" and g[0] != "May":
                continue  # lowercase "may" is almost always the verb
            if name == "iso":
                dm.value_start = _mk(int(g[0]), int(g[1]), int(g[2]))
                dm.precision = "day"
            elif name == "mdy_num":
                mo, d, y = int(g[0]), int(g[1]), g[2]
                if len(y) == 2:
                    y = 2000 + int(y)
                    dm.flags.append("two_digit_year")
                dm.value_start = _mk(int(y), mo, d)
                dm.precision = "day"
                if mo <= 12 and d <= 12 and mo != d:
                    dm.flags.append("ambiguous_day_month")
            elif name == "month_day_year":
                dm.value_start = _mk(int(g[2]), _month(g[0]), int(g[1]))
                dm.precision = "day"
            elif name == "day_month_year":
                dm.value_start = _mk(int(g[2]), _month(g[1]), int(g[0]))
                dm.precision = "day"
            elif name == "month_year":
                y, mo = int(g[1]), _month(g[0])
                dm.value_start = date(y, mo, 1)
                dm.value_end = date(y, mo, calendar.monthrange(y, mo)[1])
                dm.precision = "month"
            elif name == "month_day":
                mo, d = _month(g[0]), int(g[1])
                if not 1 <= d <= 31:
                    continue
                dm.needs_year, dm.month, dm.day, dm.precision = True, mo, d, "day"
            if dm.value_start is None and not dm.needs_year:
                continue  # e.g. February 30
            if dm.value_end is None and dm.value_start is not None:
                dm.value_end = dm.value_start
            taken.append((s, e))
            out.append(dm)
    for m in _RELATIVE.finditer(text):
        if free(*m.span()):
            out.append(DateMention(m.start(), m.end(), m.group(0), "relative"))
    return sorted(out, key=lambda d: d.start)


def resolve_years(mentions: list[DateMention], doc_date: date | None) -> None:
    """Fill in years for "April 12"-style mentions, in place.
    Anchor 1: the document's own date (email Date header) -> the year that
    puts the mention closest to it. Anchor 2: the nearest full date earlier
    in the same document (else later). No anchor -> stays unresolved."""
    full = [d for d in mentions if d.resolved and d.precision == "day"]
    for d in mentions:
        if not d.needs_year:
            continue
        cand = None
        if doc_date is not None:
            opts = [_mk(y, d.month, d.day) for y in (doc_date.year - 1, doc_date.year, doc_date.year + 1)]
            opts = [o for o in opts if o]
            if opts:
                cand = min(opts, key=lambda o: abs((o - doc_date).days))
                flag = "year_inferred_from_doc_date"
        if cand is None and full:
            before = [f for f in full if f.start < d.start]
            ref = before[-1] if before else min(full, key=lambda f: abs(f.start - d.start))
            cand = _mk(ref.value_start.year, d.month, d.day)
            flag = "year_inferred_from_context"
        if cand is not None:
            d.value_start = d.value_end = cand
            d.flags.append(flag)


def fmt(d: DateMention) -> str:
    if d.value_start is None:
        return "unresolved"
    if d.precision == "month":
        return d.value_start.strftime("%Y-%m") + " (month)"
    if d.precision == "year":
        return str(d.value_start.year) + " (year)"
    return d.value_start.isoformat()


def parse_iso(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


ONE_DAY = timedelta(days=1)
