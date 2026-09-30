"""Hybrid search over the local public-opinion index.

  full-text:  Postgres tsvector (GIN), query terms OR-ed so an issue
              statement need not match every word; ranked by ts_rank_cd
  vector:     pgvector cosine distance (HNSW) on a LOCAL query embedding
  fusion:     reciprocal rank fusion, k = 60
  grouping:   one result per opinion (its best-fused passage), with the
              other matching passages of that opinion listed, so one long
              opinion cannot fill the whole result list
Nothing here makes a network call; the query never leaves the machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CANDIDATES = 100
RRF_K = 60
SNIPPET = 400
_WORD = re.compile(r"[A-Za-z0-9]+")


def rrf(ranked_lists: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal rank fusion: score(d) = sum over lists of 1 / (k + rank)."""
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, item in enumerate(lst, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def snippet(text: str, query: str, width: int = SNIPPET) -> tuple[str, int]:
    """A window of the chunk around the first query word; returns (snippet,
    offset of the snippet within the chunk). Plain text, no markup."""
    words = [w.lower() for w in _WORD.findall(query) if len(w) > 3]
    low = text.lower()
    hits = [low.find(w) for w in words if low.find(w) >= 0]
    start = max(0, min(hits) - width // 4) if hits else 0
    if start:
        sp = text.find(" ", start)
        start = sp + 1 if 0 <= sp < start + 40 else start
    end = min(len(text), start + width)
    if end < len(text):
        sp = text.rfind(" ", start, end)
        end = sp if sp > start else end
    return text[start:end], start


@dataclass
class Filters:
    courts: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None

    def sql(self) -> tuple[str, list]:
        where, params = [], []
        if self.courts:
            where.append("o.court_id = ANY(%s)")
            params.append(self.courts)
        if self.date_from:
            where.append("o.date_filed >= %s")
            params.append(self.date_from)
        if self.date_to:
            where.append("o.date_filed <= %s")
            params.append(self.date_to)
        return (" AND " + " AND ".join(where)) if where else "", params


def search(conn, embedder, query: str, top_k: int = 10, filters: Filters | None = None) -> dict:
    filters = filters or Filters()
    fsql, fparams = filters.sql()
    fts = [r[0] for r in conn.execute(
        "WITH q AS (SELECT NULLIF(replace(plainto_tsquery('english', %s)::text, ' & ', ' | '), '')::tsquery AS q) "
        "SELECT c.id FROM chunks c JOIN opinions o ON o.id = c.opinion_id, q "
        f"WHERE q.q IS NOT NULL AND c.tsv @@ q.q{fsql} ORDER BY ts_rank_cd(c.tsv, q.q) DESC, c.id LIMIT %s",
        [query, *fparams, CANDIDATES])]
    qvec = embedder.embed_query(query)
    with conn.transaction():
        conn.execute("SET LOCAL hnsw.ef_search = 200")
        vec = [r[0] for r in conn.execute(
            "SELECT c.id FROM chunks c JOIN opinions o ON o.id = c.opinion_id "
            f"WHERE c.embedding IS NOT NULL{fsql} ORDER BY c.embedding <=> %s, c.id LIMIT %s",
            [*fparams, qvec, CANDIDATES])]
    fused_all = rrf([fts, vec])
    owner = dict(conn.execute("SELECT id, opinion_id FROM chunks WHERE id = ANY(%s)",
                              ([cid for cid, _ in fused_all],)).fetchall()) if fused_all else {}
    best: dict[int, tuple[int, float]] = {}
    more: dict[int, list[int]] = {}
    for cid, score in fused_all:
        oid = owner[cid]
        if oid in best:
            more[oid].append(cid)
        elif len(best) < top_k:
            best[oid], more[oid] = (cid, score), []
    fused = list(best.values())
    fts_rank = {cid: i for i, cid in enumerate(fts, 1)}
    vec_rank = {cid: i for i, cid in enumerate(vec, 1)}
    rows = {}
    if fused:
        for r in conn.execute(
                "SELECT c.id, c.opinion_id, c.position, c.char_start, c.char_end, c.text, o.case_name, o.citation, "
                "o.court_id, ct.name, o.date_filed, o.source_url, o.docket_number FROM chunks c "
                "JOIN opinions o ON o.id = c.opinion_id JOIN courts ct ON ct.id = o.court_id WHERE c.id = ANY(%s)",
                ([cid for cid, _ in fused],)):
            rows[r[0]] = r
    results = []
    for cid, score in fused:
        r = rows[cid]
        snip, off = snippet(r[5], query)
        results.append({
            "chunk_id": r[0], "opinion_id": r[1], "position": r[2],
            "case_name": r[6], "citation": r[7], "court_id": r[8], "court": r[9],
            "date_filed": r[10].isoformat() if r[10] else None, "docket_number": r[12],
            "snippet": snip, "snippet_start": r[3] + off, "snippet_end": r[3] + off + len(snip),
            "chunk_start": r[3], "chunk_end": r[4], "source_url": r[11],
            "rrf_score": round(score, 6), "fulltext_rank": fts_rank.get(cid), "vector_rank": vec_rank.get(cid),
            "other_matching_chunk_ids": more[r[1]],
        })
    return {"results": results, "fulltext_candidates": len(fts), "vector_candidates": len(vec)}
