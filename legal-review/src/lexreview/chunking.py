"""Page-bounded chunking with character offsets.

Chunks never span pages, so every search hit maps to exactly one
(doc_id, page) and an exact character range of that page's stored text.
"""

from __future__ import annotations

CHUNK_CHARS = 1200
OVERLAP = 200


def chunk_page(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP) -> list[tuple[int, int]]:
    """Return (start, end) offsets into `text`. Boundaries snap back to
    whitespace so words are not split."""
    n = len(text)
    if n == 0 or not text.strip():
        return []
    spans = []
    start = 0
    while start < n:
        end = min(n, start + size)
        if end < n:
            ws = text.rfind(" ", start + size // 2, end)
            nl = text.rfind("\n", start + size // 2, end)
            cut = max(ws, nl)
            if cut > start:
                end = cut
        if text[start:end].strip():
            spans.append((start, end))
        if end >= n:
            break
        nxt = max(end - overlap, start + 1)
        # Move forward to the start of the next word, but never past `end`.
        while nxt < end and not text[nxt - 1].isspace():
            nxt += 1
        while nxt < n and text[nxt].isspace():
            nxt += 1
        start = nxt
    return spans
