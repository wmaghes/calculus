"""Legal-authority leads with human approval of every outbound query.

Workflow (each step audited):
  1. propose   anyone with LEGAL_PROPOSE writes the exact query text and
               picks sources + jurisdictions. Checks:
                 - BLOCKED if any 5-word run of the query appears in a case
                   document (no document text may leave the firm);
                 - WARNING if it contains a party/person/org name or a
                   4+ digit number that appears in the case (reveals the
                   matter); the approver must acknowledge warnings.
  2. approve   an attorney or case admin (LEGAL_APPROVE) approves. The
               approval is bound to the SHA-256 of the exact text + the
               destination list. Any change needs a new proposal.
  3. run       sends exactly the approved text, once, to the approved
               sources only. Each result is re-fetched by ID and cross-checked;
               unverifiable results are discarded (count shown). Unreachable
               sources are reported as unavailable, never filled in.
  4. leads     every lead is labelled "Lead for attorney verification", with
               jurisdiction, date, source and retrieval time, and the notice
               that citator / good-law status has NOT been checked.

Models are not involved at any step: no citation can come from model memory.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid

from ..authz import CaseAccessContext, Perm
from ..casestore import CaseStore
from ..errors import AccessDenied, ConfigError, NotFound
from .gateway import LegalGateway, SourceUnavailable
from .sources import ADAPTERS, JURISDICTIONS, SOURCES

LEAD_LABEL = "Lead for attorney verification"
CITATOR_NOTICE = "Citator / good-law status has NOT been checked."
_WORD = re.compile(r"[a-z0-9]+")
_NUM = re.compile(r"\b\d{4,}\b")

# Generic issue phrasings suggested from timeline topics. They contain no
# document text; the user still edits and approves the exact query.
SUGGESTIONS = {
    "temperature": "carrier liability for temperature-controlled cargo damage",
    "notice": "contractual notice requirement breach damages",
    "rejection": "buyer rejection of nonconforming goods",
    "claim/insurance": "cargo insurance claim denial late notice",
    "agreement": "breach of master services agreement limitation of liability",
    "maintenance": "negligent maintenance of equipment by motor carrier",
}


def _sha(text: str, sources: list[str], juris: list[str]) -> str:
    return hashlib.sha256(json.dumps([text, sorted(sources), sorted(juris)]).encode()).hexdigest()


def check_query(store: CaseStore, text: str) -> tuple[list[str], list[str]]:
    """Returns (blocking_reasons, warnings). Never returns document text."""
    blocks, warns = [], []
    words = _WORD.findall(text.lower())
    for i in range(len(words) - 4):
        phrase = " ".join(words[i:i + 5])
        hit = store.conn.execute("SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1", (f'"{phrase}"',)).fetchone()
        if hit:
            blocks.append("contains a 5-word phrase copied from a case document")
            break
    low = text.lower()
    names = [r[0] for r in store.conn.execute("SELECT name FROM entities")]
    hits = sorted({n for n in names if n.lower() in low or (len(n.split()[-1]) > 3 and re.search(
        r"\b" + re.escape(n.split()[-1].lower()) + r"\b", low))})
    if hits:
        warns.append("names a person or organization from this case: " + ", ".join(hits))
    for num in set(_NUM.findall(text)):
        if len(num) == 4 and num[:2] in ("19", "20"):
            continue  # a year on its own is not identifying
        if store.conn.execute("SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1", (f'"{num}"',)).fetchone():
            warns.append(f"contains the number {num}, which appears in case documents")
    return blocks, warns


def suggestions(store: CaseStore, ctx: CaseAccessContext) -> list[str]:
    store._ctx(ctx, Perm.LEGAL_PROPOSE)
    tags: dict[str, int] = {}
    for (t,) in store.conn.execute("SELECT tags FROM events"):
        for x in json.loads(t):
            tags[x] = tags.get(x, 0) + 1
    return [SUGGESTIONS[t] for t, _ in sorted(tags.items(), key=lambda kv: -kv[1]) if t in SUGGESTIONS]


def propose(store: CaseStore, ctx: CaseAccessContext, text: str, sources: list[str], juris: list[str]) -> dict:
    store._ctx(ctx, Perm.LEGAL_PROPOSE)
    text = " ".join((text or "").split())
    if not 3 <= len(text) <= 200:
        raise ConfigError("legal_query_length")
    sources = sorted(set(sources))
    juris = sorted(set(juris))
    if not sources or any(s not in SOURCES for s in sources):
        raise ConfigError("legal_source_invalid")
    if not juris or any(j not in JURISDICTIONS for j in juris):
        raise ConfigError("legal_jurisdiction_invalid")
    blocks, warns = check_query(store, text)
    if blocks:
        return {"status": "blocked", "reasons": blocks, "warnings": warns}
    qid = "lq_" + uuid.uuid4().hex[:16]
    store.conn.execute(
        "INSERT INTO legal_queries (query_id, text, text_sha256, sources, jurisdictions, warnings, status, proposed_by, proposed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (qid, text, _sha(text, sources, juris), json.dumps(sources), json.dumps(juris), json.dumps(warns), "proposed",
         ctx.user_id, time.time()))
    return {"status": "proposed", "query_id": qid, "warnings": warns}


def get_query(store: CaseStore, ctx: CaseAccessContext, qid: str) -> dict:
    store._ctx(ctx, Perm.LEGAL_PROPOSE if Perm.LEGAL_PROPOSE in ctx.perms else Perm.SEARCH)
    row = store.conn.execute(
        "SELECT query_id, text, text_sha256, sources, jurisdictions, warnings, status, proposed_by, proposed_at, "
        "decided_by, decided_at, approved_sha256, sent_at, source_status FROM legal_queries WHERE query_id=?", (qid,)).fetchone()
    if row is None:
        raise NotFound()
    keys = ("query_id", "text", "text_sha256", "sources", "jurisdictions", "warnings", "status", "proposed_by",
            "proposed_at", "decided_by", "decided_at", "approved_sha256", "sent_at", "source_status")
    q = dict(zip(keys, row))
    for k in ("sources", "jurisdictions", "warnings"):
        q[k] = json.loads(q[k])
    q["source_status"] = json.loads(q["source_status"]) if q["source_status"] else None
    return q


def list_queries(store: CaseStore, ctx: CaseAccessContext) -> list[dict]:
    store._ctx(ctx, Perm.SEARCH)
    return [get_query(store, ctx, r[0]) for r in
            store.conn.execute("SELECT query_id FROM legal_queries ORDER BY proposed_at DESC")]


def decide(store: CaseStore, ctx: CaseAccessContext, qid: str, approve: bool, acknowledge_warnings: bool) -> dict:
    store._ctx(ctx, Perm.LEGAL_APPROVE)
    q = get_query(store, ctx, qid)
    if q["status"] != "proposed":
        raise ConfigError("legal_query_not_pending")
    if _sha(q["text"], q["sources"], q["jurisdictions"]) != q["text_sha256"]:
        raise AccessDenied("legal_query_tampered")
    if approve and q["warnings"] and not acknowledge_warnings:
        raise ConfigError("legal_warnings_not_acknowledged")
    store.conn.execute(
        "UPDATE legal_queries SET status=?, decided_by=?, decided_at=?, approved_sha256=? WHERE query_id=? AND status='proposed'",
        ("approved" if approve else "rejected", ctx.user_id, time.time(), q["text_sha256"] if approve else None, qid))
    return get_query(store, ctx, qid)


def run(store: CaseStore, ctx: CaseAccessContext, qid: str, gateway: LegalGateway) -> dict:
    store._ctx(ctx, Perm.LEGAL_PROPOSE)
    q = get_query(store, ctx, qid)
    if q["status"] != "approved":
        raise AccessDenied("legal_query_not_approved")
    # The text/destinations about to be sent must be exactly what was approved.
    if _sha(q["text"], q["sources"], q["jurisdictions"]) != q["approved_sha256"]:
        raise AccessDenied("legal_query_changed_after_approval")
    # Claim the send atomically so the approved query goes out once.
    cur = store.conn.execute("UPDATE legal_queries SET status='sent', sent_at=? WHERE query_id=? AND status='approved'",
                             (time.time(), qid))
    if cur.rowcount != 1:
        raise AccessDenied("legal_query_not_approved")
    status: dict[str, dict] = {}
    now = time.time()
    for src in q["sources"]:
        adapter = ADAPTERS[src](gateway)
        st = {"verified": 0, "discarded_unverifiable": 0, "unavailable": None}
        seen = set()
        for j in q["jurisdictions"]:
            try:
                cands = adapter.search(q["text"], j)
            except SourceUnavailable as exc:
                st["unavailable"] = exc.reason
                break
            for c in cands:
                if c.source_id in seen:
                    continue
                seen.add(c.source_id)
                try:
                    v = adapter.verify(c)
                except SourceUnavailable:
                    v = None
                if v is None:
                    st["discarded_unverifiable"] += 1
                    continue
                store.conn.execute(
                    "INSERT INTO legal_leads (query_id, source, source_id, kind, title, citation, jurisdiction, body, date, url, "
                    "snippet, retrieved_at, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (qid, v.source, v.source_id, v.kind, v.title, v.citation, v.jurisdiction, v.body, v.date, v.url,
                     v.snippet, now, time.time()))
                st["verified"] += 1
        status[src] = st
    store.conn.execute("UPDATE legal_queries SET source_status=? WHERE query_id=?", (json.dumps(status), qid))
    return {"query_id": qid, "source_status": status, "leads": leads(store, ctx, qid)}


def leads(store: CaseStore, ctx: CaseAccessContext, qid: str) -> list[dict]:
    store._ctx(ctx, Perm.SEARCH)
    rows = store.conn.execute(
        "SELECT lead_id, source, source_id, kind, title, citation, jurisdiction, body, date, url, snippet, retrieved_at "
        "FROM legal_leads WHERE query_id=? ORDER BY source, lead_id", (qid,)).fetchall()
    out = []
    for r in rows:
        out.append({"lead_id": r[0], "source": r[1], "source_id": r[2], "kind": r[3], "title": r[4], "citation": r[5],
                    "jurisdiction": r[6], "body": r[7], "date": r[8], "url": r[9], "snippet": r[10],
                    "retrieved_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(r[11])),
                    "label": LEAD_LABEL, "citator_notice": CITATOR_NOTICE})
    return out
