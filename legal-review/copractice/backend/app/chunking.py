"""Paragraph-aware chunking with exact character offsets.

Target ~300-500 tokens per chunk (~1,200-2,000 characters of legal prose),
split at paragraph boundaries where possible, with a small overlap so a
holding that straddles a boundary appears whole in at least one chunk.
Invariant: chunk text == opinion_text[char_start:char_end].
"""

from __future__ import annotations

import re

TARGET = 1500
MAX = 2000   # + OVERLAP => at most ~2,200 chars (~500 tokens)
MIN = 400
OVERLAP = 200

_PARA = re.compile(r"\n\s*\n")


def _paragraphs(text: str) -> list[tuple[int, int]]:
    spans, pos = [], 0
    for m in _PARA.finditer(text):
        if text[pos:m.start()].strip():
            spans.append((pos, m.start()))
        pos = m.end()
    if text[pos:].strip():
        spans.append((pos, len(text)))
    out = []
    for s, e in spans:  # split giant paragraphs at sentence/space boundaries
        while e - s > MAX:
            cut = max(text.rfind(". ", s + TARGET // 2, s + MAX), text.rfind(" ", s + TARGET // 2, s + MAX))
            cut = cut + 1 if cut > s else s + MAX
            out.append((s, cut))
            s = cut
        out.append((s, e))
    return out


def chunk(text: str) -> list[tuple[int, int]]:
    paras = _paragraphs(text)
    chunks: list[tuple[int, int]] = []
    i = 0
    while i < len(paras):
        s, e = paras[i]
        j = i + 1
        while j < len(paras) and paras[j][1] - s <= MAX and e - s < TARGET:
            e = paras[j][1]
            j += 1
        chunks.append((s, e))
        if j >= len(paras):
            break
        # Overlap: start the next chunk up to OVERLAP chars back, on a word boundary.
        nxt = paras[j][0]
        back = max(e - OVERLAP, s + 1)
        k = text.find(" ", back, e)
        if 0 <= k < nxt and e - s > MIN:
            paras[j] = (k + 1, paras[j][1])
        i = j
    # Merge a tiny final chunk into its predecessor.
    if len(chunks) > 1 and chunks[-1][1] - chunks[-1][0] < MIN and chunks[-1][1] - chunks[-2][0] <= MAX + MIN:
        chunks[-2:] = [(chunks[-2][0], chunks[-1][1])]
    return chunks
