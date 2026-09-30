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
