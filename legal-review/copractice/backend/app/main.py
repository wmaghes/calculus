"""Copractice API.

NOTE: no authentication yet. The API must only listen on loopback (as the
compose file does) and must sit behind lexreview's authenticated app before
any multi-user use. Issue statements are sensitive even though the index is
public.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config, db, embeddings
from .search import Filters, search as run_search

DISCLAIMER = "Research aid for attorneys, not legal advice."
GOOD_LAW = "Good-law status is not checked. Confirm every authority with a citator before relying on it."

app = FastAPI(title="Copractice", docs_url=None, redoc_url=None)


@lru_cache(maxsize=1)
def _state():
    s = config.load()
    conn = db.connect(s.database_url)
    db.migrate(conn)
    return conn, embeddings.from_settings(s)


@app.middleware("http")
async def headers(request, call_next):
    try:
        resp = await call_next(request)
    except Exception:  # never echo internals or query text
        resp = JSONResponse({"error": "internal_error"}, status_code=500)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000, description="Issue statement")
    top_k: int = Field(default=10, ge=1, le=50)
    courts: list[str] | None = Field(default=None, max_length=20)
    date_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


@app.get("/health")
def health():
    conn, emb = _state()
    n = conn.execute("SELECT count(*) FROM opinions").fetchone()[0]
    return {"ok": True, "opinions": n, "embedder": emb.name}


@app.post("/search")
def search(req: SearchRequest):
    conn, emb = _state()
    out = run_search(conn, emb, req.query.strip(), req.top_k, Filters(req.courts, req.date_from, req.date_to))
    # The query text is never logged; only that a search happened and its size.
    db.audit(conn, "api", "search", query_chars=len(req.query), results=len(out["results"]))
    total = conn.execute("SELECT count(*) FROM opinions").fetchone()[0]
    return {**out, "opinions_indexed": total, "embedder": emb.name, "disclaimer": DISCLAIMER, "good_law_notice": GOOD_LAW}


@app.get("/opinions/{opinion_id}")
def opinion(opinion_id: int):
    conn, _ = _state()
    r = conn.execute(
        "SELECT o.id, o.case_name, o.citation, o.court_id, ct.name, o.date_filed, o.judges, o.docket_number, o.source_url, t.text "
        "FROM opinions o JOIN courts ct ON ct.id=o.court_id JOIN opinion_texts t ON t.opinion_id=o.id WHERE o.id=%s",
        (opinion_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "not_found")
    db.audit(conn, "api", "view_opinion", opinion_id=opinion_id)
    keys = ("id", "case_name", "citation", "court_id", "court", "date_filed", "judges", "docket_number", "source_url", "text")
    d = dict(zip(keys, r))
    d["date_filed"] = d["date_filed"].isoformat() if d["date_filed"] else None
    return {**d, "disclaimer": DISCLAIMER, "good_law_notice": GOOD_LAW}
