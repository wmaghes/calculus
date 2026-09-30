"""Split a page into citeable segments (sentences, transcript lines, table
rows, email header blocks), as (start, end) offsets into the page text."""

from __future__ import annotations

import re

MAX_SEG = 600
_PARA = re.compile(r"\n[ \t]*\n")
_LINE_UNIT = re.compile(r"^\s{0,4}(?:\d{1,3}\s{1,4}(?:Q|A)\.|(?:Q|A)\.\s|\d{1,3}\s{2,}|\[?SYNTHETIC)")
_HEADER = re.compile(r"^(From|To|Cc|Date|Subject): ")
_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def _trim(text: str, s: int, e: int) -> tuple[int, int] | None:
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return (s, e) if e > s else None


def segments(text: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    pos = 0
    paras = []
    for m in _PARA.finditer(text):
        paras.append((pos, m.start()))
        pos = m.end()
    paras.append((pos, len(text)))
    for ps, pe in paras:
        lines, ls = [], ps
        for part in text[ps:pe].split("\n"):
            lines.append((ls, ls + len(part)))
            ls += len(part) + 1
        # Email header block: consecutive "Header: value" lines form one unit.
        if lines and all(_HEADER.match(text[a:b]) for a, b in lines):
            t = _trim(text, ps, pe)
            if t:
                out.append(t)
            continue
        buf_start = None
        for a, b in lines:
            line = text[a:b]
            if "\t" in line or _LINE_UNIT.match(line) or _HEADER.match(line):
                if buf_start is not None:
                    out.extend(_sentences(text, buf_start, a))
                    buf_start = None
                t = _trim(text, a, b)
                if t:
                    out.append(t)
            elif buf_start is None:
                buf_start = a
        if buf_start is not None:
            out.extend(_sentences(text, buf_start, pe))
    return out


def _sentences(text: str, s: int, e: int) -> list[tuple[int, int]]:
    res = []
    cur = s
    for m in _SENT_END.finditer(text, s, e):
        t = _trim(text, cur, m.start())
        if t:
            res.append(t)
        cur = m.end()
    t = _trim(text, cur, e)
    if t:
        res.append(t)
    return res


def window(text: str, seg: tuple[int, int], anchor: tuple[int, int]) -> tuple[int, int]:
    """Cap an over-long segment to ~MAX_SEG chars around the anchor span,
    snapped to whitespace."""
    s, e = seg
    if e - s <= MAX_SEG:
        return seg
    half = (MAX_SEG - (anchor[1] - anchor[0])) // 2
    ns, ne = max(s, anchor[0] - half), min(e, anchor[1] + half)
    while ns > s and not text[ns - 1].isspace():
        ns -= 1
    while ne < e and not text[ne].isspace():
        ne += 1
    return _trim(text, ns, ne) or seg
