"""Hybrid retrieval: BM25 (FTS5) + semantic (per-case LSA), fused with
reciprocal rank fusion (RRF).

Guarantees, per result:
* It comes from a document the requesting user may see (restriction labels
  are applied inside both the SQL and the vector mask, before ranking).
* Its snippet is re-checked against the stored page text at the recorded
  offsets. A mismatch drops the result and counts it as an integrity failure
  (it should never happen; it would mean index/store corruption).
* It carries doc ID, page number, locator, character range and a link that
  opens the page viewer with the passage highlighted.
* It carries the coverage summary: how many documents were searched and how
  many could not be searched.

"Confidence" is a band derived from absolute evidence, never from rank
position alone and never from a model's self-assessment:
    strong    most query terms appear in the passage, AND the semantic
              similarity is clear
    moderate  a good share of terms appear, OR the semantic similarity is clear
    weak      anything else that still passed the candidate thresholds
Low-confidence OCR caps a passage at "moderate".

Recall first: `documents` rolls up EVERY qualifying candidate (not just the
top_k passages shown), because a missed document is the costly error.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass

from ..authz import CaseAccessContext, Perm
from ..casestore import CaseStore
from .embed import VectorIndex, raw_terms, tokenize

RRF_K = 60
CANDIDATES = 300
MIN_COSINE = 0.12       # semantic candidates below this are noise
CLEAR_COSINE = 0.30


def to_fts_query(text: str) -> str | None:
    """Plain English -> FTS5 query of quoted OR'd terms. User text never
    reaches FTS5 as syntax (no operators, NEAR, column filters, etc.)."""
    terms = list(dict.fromkeys(raw_terms(text)))[:32]
    if not terms:
        return None
    return " OR ".join(f'"{t}"' for t in terms)


def term_coverage(query_stems: set[str], passage: str) -> float:
    if not query_stems:
        return 0.0
    return len(query_stems & set(tokenize(passage))) / len(query_stems)


@dataclass
class Hit:
    rank: int
    doc_id: str
    source_name: str
    top_level_doc_id: str
    page_no: int
    locator: str
    char_start: int
    char_end: int
    snippet: str
    band: str
    keyword_rank: int | None
    semantic_rank: int | None
    ocr: bool
    ocr_conf: float | None
    link: str


def _band(coverage: float, cosine: float | None, ocr: bool, ocr_conf: float | None) -> str:
    clear = cosine is not None and cosine >= CLEAR_COSINE
    if coverage >= 0.5 and clear:
        band = "strong"
    elif coverage >= 0.34 or clear:
        band = "moderate"
    else:
        band = "weak"
    if ocr and (ocr_conf or 0) < 60 and band == "strong":
        band = "moderate"
    return band


def viewer_link(case_id: str, doc_id: str, page_no: int, start: int, end: int) -> str:
    return f"/ui/cases/{case_id}/docs/{doc_id}/pages/{page_no}?hl={start}-{end}#hl"


def hybrid_search(store: CaseStore, ctx: CaseAccessContext, index: VectorIndex | None, query: str,
                  top_k: int = 50) -> dict:
    ctx.require(Perm.SEARCH)
    fts_q = to_fts_query(query)
    kw = store.fts_search(ctx, fts_q, CANDIDATES) if fts_q else []
    sem = index.search(query, store.visible_chunk_ids(ctx), CANDIDATES, MIN_COSINE) if index is not None else []
    kw_rank = {cid: i + 1 for i, (cid, _) in enumerate(kw)}
    sem_rank = {cid: i + 1 for i, (cid, _) in enumerate(sem)}
    cosine = dict(sem)
    fused: dict[int, float] = {}
    for ranks in (kw_rank, sem_rank):
        for cid, r in ranks.items():
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + r)
    order = sorted(fused, key=lambda c: -fused[c])
    details = store.chunk_details(ctx, order)
    q_stems = set(tokenize(query))
    hits: list[Hit] = []
    integrity_failures = 0
    page_cache: dict[tuple[str, int], str] = {}
    for cid in order:
        d = details.get(cid)
        if d is None:  # not visible (defense in depth; filtered earlier)
            continue
        key = (d["doc_id"], d["page_no"])
        if key not in page_cache:
            page_cache[key] = store.get_page(ctx, d["doc_id"], d["page_no"]).text
        if page_cache[key][d["char_start"]:d["char_end"]] != d["text"]:
            integrity_failures += 1
            continue
        cov = term_coverage(q_stems, d["text"])
        band = _band(cov, cosine.get(cid), bool(d["ocr"]), d["ocr_conf"])
        # A keyword-only hit on a single common word (e.g. "policy") with no
        # semantic support is not evidence of relevance.
        if cid not in sem_rank and cov < 0.2 and len(q_stems) > 2:
            continue
        hits.append(Hit(
            rank=len(hits) + 1, doc_id=d["doc_id"], source_name=d["source_name"],
            top_level_doc_id=d["parent_id"] or d["doc_id"], page_no=d["page_no"], locator=d["locator"],
            char_start=d["char_start"], char_end=d["char_end"], snippet=d["text"], band=band,
            keyword_rank=kw_rank.get(cid), semantic_rank=sem_rank.get(cid), ocr=bool(d["ocr"]),
            ocr_conf=d["ocr_conf"],
            link=viewer_link(ctx.case_id, d["doc_id"], d["page_no"], d["char_start"], d["char_end"])))
    # Document-level roll-up over ALL qualifying passages (attachments roll up
    # to their parent email).
    docs: dict[str, dict] = {}
    rank_of = {"strong": 0, "moderate": 1, "weak": 2}
    for h in hits:
        e = docs.setdefault(h.top_level_doc_id, {"doc_id": h.top_level_doc_id, "best_rank": h.rank, "hits": 0,
                                                 "best_band": h.band, "best_link": h.link})
        e["hits"] += 1
        if rank_of[h.band] < rank_of[e["best_band"]]:
            e["best_band"] = h.band
    shown = hits[:top_k]
    query_id = "q_" + uuid.uuid4().hex[:16]
    store.record_query(ctx, query_id, query, len(hits))
    return {
        "query_id": query_id,
        "results": [asdict(h) for h in shown],
        "total_passages": len(hits),
        "documents": sorted(docs.values(), key=lambda e: e["best_rank"]),
        "documents_searched": store.searchable_visible_count(ctx),
        "semantic_backend": "lsa-v1" if index is not None else "unavailable",
        "integrity_failures": integrity_failures,
        "not_found": not hits,
    }


def build_index(store: CaseStore, ctx: CaseAccessContext) -> int:
    rows = store.searchable_chunks(ctx)
    idx = VectorIndex.build(rows)
    store.put_vectors(ctx, idx.to_bytes())
    return len(rows)


def load_index(store: CaseStore, ctx: CaseAccessContext) -> VectorIndex | None:
    data = store.get_vectors(ctx)
    return VectorIndex.from_bytes(data) if data else None

