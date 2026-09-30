"""Per-case encrypted store.

Layout under <data_root>/cases/<case_id>/:
    dek.wrapped     the case DEK, wrapped by the case KEK in the KMS
    case.db         SQLCipher DB: documents, pages, chunks, FTS index, coverage
    blobs/<id>.bin  original files, AES-256-GCM with AAD "<case_id>:<doc_id>"

A CaseStore is bound to exactly one case and refuses any context whose
case_id differs. Every read that can return document data applies the
caller's restriction-label grants inside the SQL, so restricted documents
never appear in results, counts or snippets for users without the grant.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from . import crypto, db
from .authz import CaseAccessContext, Perm, verify_context
from .errors import NotFound

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES documents(doc_id),
    source_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    page_count INTEGER NOT NULL DEFAULT 0,
    ocr_pages INTEGER NOT NULL DEFAULT 0,
    low_conf_pages INTEGER NOT NULL DEFAULT 0,
    restriction TEXT,
    meta_json TEXT,
    ingested_at REAL NOT NULL,
    ingested_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS documents_sha ON documents(source_sha256);
CREATE TABLE IF NOT EXISTS pages (
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    page_no INTEGER NOT NULL,
    locator TEXT NOT NULL,
    text TEXT NOT NULL,
    ocr INTEGER NOT NULL DEFAULT 0,
    ocr_conf REAL,
    PRIMARY KEY (doc_id, page_no)
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    page_no INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id, page_no);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='chunk_id', tokenize='porter unicode61'
);
-- Query text is work product: it lives only here, inside the encrypted case
-- DB. The audit log records a keyed digest and the query_id.
CREATE TABLE IF NOT EXISTS queries (
    query_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    query_text TEXT NOT NULL,
    n_results INTEGER NOT NULL
);
-- Phase 3: extraction. Every row is a span in stored page text.
CREATE TABLE IF NOT EXISTS entities (
    entity_id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('person', 'org')),
    name TEXT NOT NULL,
    UNIQUE (kind, name)
);
CREATE TABLE IF NOT EXISTS mentions (
    mention_id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL REFERENCES entities(entity_id),
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    page_no INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    method TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS mentions_doc ON mentions(doc_id, page_no);
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    page_no INTEGER NOT NULL,
    seg_start INTEGER NOT NULL,
    seg_end INTEGER NOT NULL,
    date_start TEXT NOT NULL,
    date_end TEXT NOT NULL,
    precision TEXT NOT NULL,
    date_char_start INTEGER NOT NULL,
    date_char_end INTEGER NOT NULL,
    flags TEXT NOT NULL,
    tags TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_date ON events(date_start);
CREATE TABLE IF NOT EXISTS event_entities (
    event_id INTEGER NOT NULL REFERENCES events(event_id),
    entity_id INTEGER NOT NULL REFERENCES entities(entity_id),
    PRIMARY KEY (event_id, entity_id)
);
CREATE TABLE IF NOT EXISTS unresolved_dates (
    id INTEGER PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    page_no INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    seg_start INTEGER NOT NULL,
    seg_end INTEGER NOT NULL,
    kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS marks (
    mark_id INTEGER PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    page_no INTEGER,
    user_id TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('relevant', 'not_relevant')),
    query_id TEXT,
    created_at REAL NOT NULL
);
"""

# Statuses recorded in the coverage ledger. Only "indexed" and
# "indexed_low_confidence" documents are searchable.
STATUSES = (
    "indexed", "indexed_low_confidence", "ocr_failed", "corrupted",
    "password_protected", "unsupported", "too_large", "rejected_unsafe",
    "timeout", "duplicate", "parse_error",
)
SEARCHABLE = ("indexed", "indexed_low_confidence")


@dataclass(frozen=True)
class Page:
    doc_id: str
    page_no: int
    locator: str
    text: str
    ocr: bool
    ocr_conf: float | None


class CaseStore:
    def __init__(self, case_dir: Path, case_id: str, dek: bytes):
        self.case_id = case_id
        self.dir = Path(case_dir)
        (self.dir / "blobs").mkdir(parents=True, exist_ok=True, mode=0o700)
        self._blob_key = crypto.derive(dek, "blob")
        self._vector_key = crypto.derive(dek, "vector")
        self.conn = db.connect(self.dir / "case.db", crypto.derive(dek, "sqlcipher"))
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---- helpers ----------------------------------------------------------
    def _ctx(self, ctx: CaseAccessContext, perm: Perm) -> CaseAccessContext:
        verify_context(ctx, self.case_id)
        ctx.require(perm)
        return ctx

    # SQL built with f-strings in this class interpolates ONLY the fixed clause
    # returned by visibility_sql (constant text plus "?" placeholders). Every
    # value, including restriction labels, is passed as a bound parameter.
    @staticmethod
    def visibility_sql(ctx: CaseAccessContext, alias: str = "d") -> tuple[str, list]:
        grants = sorted(ctx.grants)
        if not grants:
            return f"{alias}.restriction IS NULL", []
        marks = ",".join("?" * len(grants))
        return f"({alias}.restriction IS NULL OR {alias}.restriction IN ({marks}))", grants

    # ---- writes (ingestion) -------------------------------------------------
    def put_blob(self, ctx: CaseAccessContext, doc_id: str, data: bytes) -> None:
        self._ctx(ctx, Perm.INGEST)
        sealed = crypto.seal(self._blob_key, data, aad=f"{self.case_id}:{doc_id}".encode())
        path = self.dir / "blobs" / f"{doc_id}.bin"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(sealed)

    def find_by_sha(self, ctx: CaseAccessContext, sha: str) -> str | None:
        self._ctx(ctx, Perm.INGEST)
        row = self.conn.execute("SELECT doc_id FROM documents WHERE source_sha256=? AND status != 'duplicate' LIMIT 1", (sha,)).fetchone()
        return row[0] if row else None

    def add_document(self, ctx: CaseAccessContext, *, doc_id: str, parent_id: str | None, source_name: str,
                     sha: str, size: int, kind: str, status: str, reason: str | None,
                     restriction: str | None, meta_json: str | None,
                     pages: list[Page], chunks: list[tuple[int, int, int, str]]) -> None:
        """chunks: (page_no, char_start, char_end, text). Atomic per document."""
        self._ctx(ctx, Perm.INGEST)
        if status not in STATUSES:
            raise ValueError("unknown_status")
        ocr_pages = sum(1 for p in pages if p.ocr)
        low = sum(1 for p in pages if p.ocr and (p.ocr_conf or 0) < 60.0)
        c = self.conn
        c.execute("BEGIN")
        try:
            c.execute(
                "INSERT INTO documents (doc_id, parent_id, source_name, source_sha256, bytes, kind, status, reason, "
                "page_count, ocr_pages, low_conf_pages, restriction, meta_json, ingested_at, ingested_by) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (doc_id, parent_id, source_name, sha, size, kind, status, reason, len(pages), ocr_pages, low,
                 restriction, meta_json, time.time(), ctx.user_id))
            c.executemany(
                "INSERT INTO pages (doc_id, page_no, locator, text, ocr, ocr_conf) VALUES (?,?,?,?,?,?)",
                [(doc_id, p.page_no, p.locator, p.text, int(p.ocr), p.ocr_conf) for p in pages])
            for page_no, start, end, text in chunks:
                cur = c.execute(
                    "INSERT INTO chunks (doc_id, page_no, char_start, char_end, text) VALUES (?,?,?,?,?)",
                    (doc_id, page_no, start, end, text))
                c.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (cur.lastrowid, text))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def set_restriction(self, ctx: CaseAccessContext, doc_id: str, label: str | None) -> None:
        self._ctx(ctx, Perm.MANAGE)
        cur = self.conn.execute("UPDATE documents SET restriction=? WHERE doc_id=?", (label, doc_id))
        if cur.rowcount != 1:
            raise NotFound()

    # ---- reads --------------------------------------------------------------
    def get_blob(self, ctx: CaseAccessContext, doc_id: str) -> bytes:
        self._ctx(ctx, Perm.VIEW)
        self.get_document(ctx, doc_id)  # enforces visibility
        path = self.dir / "blobs" / f"{doc_id}.bin"
        return crypto.open_sealed(self._blob_key, path.read_bytes(), aad=f"{self.case_id}:{doc_id}".encode())

    def get_document(self, ctx: CaseAccessContext, doc_id: str) -> dict:
        self._ctx(ctx, Perm.VIEW)
        vis, params = self.visibility_sql(ctx)
        row = self.conn.execute(
            f"SELECT doc_id, parent_id, source_name, kind, status, reason, page_count, ocr_pages, low_conf_pages, restriction, meta_json "  # nosec B608 - constant clause, bound params
            f"FROM documents d WHERE d.doc_id=? AND {vis}", [doc_id, *params]).fetchone()
        if row is None:
            # Same answer for "does not exist" and "exists but not visible".
            raise NotFound()
        keys = ("doc_id", "parent_id", "source_name", "kind", "status", "reason", "page_count", "ocr_pages",
                "low_conf_pages", "restriction", "meta_json")
        return dict(zip(keys, row))

    def get_page(self, ctx: CaseAccessContext, doc_id: str, page_no: int) -> Page:
        self._ctx(ctx, Perm.VIEW)
        vis, params = self.visibility_sql(ctx)
        row = self.conn.execute(
            f"SELECT p.doc_id, p.page_no, p.locator, p.text, p.ocr, p.ocr_conf FROM pages p "  # nosec B608 - constant clause, bound params
            f"JOIN documents d ON d.doc_id = p.doc_id WHERE p.doc_id=? AND p.page_no=? AND {vis}",
            [doc_id, page_no, *params]).fetchone()
        if row is None:
            raise NotFound()
        return Page(row[0], row[1], row[2], row[3], bool(row[4]), row[5])

    def list_documents(self, ctx: CaseAccessContext) -> list[dict]:
        self._ctx(ctx, Perm.VIEW)
        vis, params = self.visibility_sql(ctx)
        rows = self.conn.execute(
            f"SELECT doc_id, parent_id, source_name, kind, status, reason, page_count, ocr_pages, low_conf_pages "  # nosec B608 - constant clause, bound params
            f"FROM documents d WHERE {vis} ORDER BY source_name, doc_id", params).fetchall()
        keys = ("doc_id", "parent_id", "source_name", "kind", "status", "reason", "page_count", "ocr_pages", "low_conf_pages")
        return [dict(zip(keys, r)) for r in rows]

    def withheld_count(self, ctx: CaseAccessContext) -> int:
        """How many documents exist that this user cannot see. Reported (as a
        number only) so restricted material is never a *silent* gap."""
        self._ctx(ctx, Perm.VIEW)
        vis, params = self.visibility_sql(ctx)
        return self.conn.execute(f"SELECT count(*) FROM documents d WHERE NOT {vis}", params).fetchone()[0]  # nosec B608 - constant clause, bound params

    # ---- search support (Phase 2) -------------------------------------------
    def searchable_chunks(self, ctx: CaseAccessContext):
        """All chunks of searchable documents, for building the case's
        semantic index. Restriction labels are NOT applied here: the index is
        built once per case and filtered per user at query time."""
        self._ctx(ctx, Perm.INGEST)
        marks = ",".join("?" * len(SEARCHABLE))
        return self.conn.execute(
            f"SELECT c.chunk_id, c.text FROM chunks c JOIN documents d ON d.doc_id = c.doc_id "  # nosec B608 - constant clause, bound params
            f"WHERE d.status IN ({marks}) ORDER BY c.chunk_id", SEARCHABLE).fetchall()

    def put_vectors(self, ctx: CaseAccessContext, data: bytes) -> None:
        self._ctx(ctx, Perm.INGEST)
        sealed = crypto.seal(self._vector_key, data, aad=f"{self.case_id}:vectors".encode())
        tmp = self.dir / "vectors.bin.new"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(sealed)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.dir / "vectors.bin")

    def get_vectors(self, ctx: CaseAccessContext) -> bytes | None:
        self._ctx(ctx, Perm.SEARCH)
        path = self.dir / "vectors.bin"
        if not path.exists():
            return None
        return crypto.open_sealed(self._vector_key, path.read_bytes(), aad=f"{self.case_id}:vectors".encode())

    def visible_chunk_ids(self, ctx: CaseAccessContext) -> set[int]:
        self._ctx(ctx, Perm.SEARCH)
        vis, params = self.visibility_sql(ctx)
        marks = ",".join("?" * len(SEARCHABLE))
        rows = self.conn.execute(
            f"SELECT c.chunk_id FROM chunks c JOIN documents d ON d.doc_id = c.doc_id "  # nosec B608 - constant clause, bound params
            f"WHERE d.status IN ({marks}) AND {vis}", [*SEARCHABLE, *params]).fetchall()
        return {r[0] for r in rows}

    def fts_search(self, ctx: CaseAccessContext, fts_query: str, limit: int) -> list[tuple[int, float]]:
        """BM25 over visible, searchable chunks. `fts_query` must come from
        search.hybrid.to_fts_query (quoted terms only)."""
        self._ctx(ctx, Perm.SEARCH)
        vis, params = self.visibility_sql(ctx)
        marks = ",".join("?" * len(SEARCHABLE))
        rows = self.conn.execute(
            f"SELECT f.rowid, bm25(chunks_fts) AS score FROM chunks_fts f "  # nosec B608 - constant clause, bound params
            f"JOIN chunks c ON c.chunk_id = f.rowid JOIN documents d ON d.doc_id = c.doc_id "
            f"WHERE chunks_fts MATCH ? AND d.status IN ({marks}) AND {vis} ORDER BY score LIMIT ?",
            [fts_query, *SEARCHABLE, *params, limit]).fetchall()
        return [(r[0], r[1]) for r in rows]

    def chunk_details(self, ctx: CaseAccessContext, chunk_ids: list[int]) -> dict[int, dict]:
        self._ctx(ctx, Perm.SEARCH)
        if not chunk_ids:
            return {}
        vis, params = self.visibility_sql(ctx)
        marks = ",".join("?" * len(chunk_ids))
        rows = self.conn.execute(
            f"SELECT c.chunk_id, c.doc_id, c.page_no, c.char_start, c.char_end, c.text, p.locator, p.ocr, p.ocr_conf, "  # nosec B608 - constant clause, bound params
            f"d.source_name, d.parent_id, d.kind, d.meta_json FROM chunks c "
            f"JOIN documents d ON d.doc_id = c.doc_id JOIN pages p ON p.doc_id = c.doc_id AND p.page_no = c.page_no "
            f"WHERE c.chunk_id IN ({marks}) AND {vis}", [*chunk_ids, *params]).fetchall()
        keys = ("chunk_id", "doc_id", "page_no", "char_start", "char_end", "text", "locator", "ocr", "ocr_conf",
                "source_name", "parent_id", "kind", "meta_json")
        return {r[0]: dict(zip(keys, r)) for r in rows}

    def searchable_visible_count(self, ctx: CaseAccessContext) -> int:
        self._ctx(ctx, Perm.SEARCH)
        vis, params = self.visibility_sql(ctx)
        marks = ",".join("?" * len(SEARCHABLE))
        return self.conn.execute(
            f"SELECT count(*) FROM documents d WHERE d.status IN ({marks}) AND {vis}",  # nosec B608 - constant clause, bound params
            [*SEARCHABLE, *params]).fetchone()[0]

    def record_query(self, ctx: CaseAccessContext, query_id: str, text: str, n: int) -> None:
        self._ctx(ctx, Perm.SEARCH)
        self.conn.execute("INSERT INTO queries (query_id, user_id, created_at, query_text, n_results) VALUES (?,?,?,?,?)",
                          (query_id, ctx.user_id, time.time(), text, n))

    def add_mark(self, ctx: CaseAccessContext, doc_id: str, page_no: int | None, label: str, query_id: str | None) -> int:
        self._ctx(ctx, Perm.MARK)
        self.get_document(ctx, doc_id)  # visibility check
        cur = self.conn.execute(
            "INSERT INTO marks (doc_id, page_no, user_id, label, query_id, created_at) VALUES (?,?,?,?,?,?)",
            (doc_id, page_no, ctx.user_id, label, query_id, time.time()))
        return cur.lastrowid

    def marks_for(self, ctx: CaseAccessContext, doc_id: str) -> list[dict]:
        self._ctx(ctx, Perm.VIEW)
        self.get_document(ctx, doc_id)
        rows = self.conn.execute(
            "SELECT mark_id, page_no, user_id, label, query_id, created_at FROM marks WHERE doc_id=? ORDER BY mark_id",
            (doc_id,)).fetchall()
        return [dict(zip(("mark_id", "page_no", "user_id", "label", "query_id", "created_at"), r)) for r in rows]
