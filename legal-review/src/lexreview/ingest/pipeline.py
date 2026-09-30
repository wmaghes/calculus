"""Ingestion pipeline.

1. Data-safety pre-check of EVERY file first (location, signed manifest,
   hash). If any file fails, nothing is ingested.
2. Per file: read once and re-verify hash, dedupe by SHA-256, store the
   original encrypted, parse in the sandbox, chunk, write atomically.
3. Email attachments are ingested as child documents (depth-limited).
4. Every file ends with a coverage status. Nothing is dropped silently.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from ..authz import CaseAccessContext
from ..casestore import Page
from ..chunking import chunk_page
from ..datasafety import MANIFEST_NAME, ApprovedDataGuard
from ..errors import DataSafetyError
from ..safelog import log_event
from .sandbox import run_parser

MAX_DEPTH = 3


def _new_doc_id() -> str:
    return "d_" + uuid.uuid4().hex[:20]


def _collect(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = []
    for p in sorted(path.rglob("*")):
        if p.is_file() and p.name != MANIFEST_NAME:
            files.append(p)
    return files


def ingest_path(app, ctx: CaseAccessContext, path: Path, restriction: str | None) -> dict:
    guard = ApprovedDataGuard(app.settings)
    files = _collect(path)
    # Pre-check everything before reading any content for real.
    for f in files:
        try:
            guard.check(f)
        except DataSafetyError as exc:
            app.audit.record(ctx.user_id, "ingest", "refused", case_id=ctx.case_id, reason=exc.code)
            raise
    store = app.store(ctx)
    t0 = time.time()
    summary: dict[str, int] = {}
    doc_ids: list[str] = []
    degraded = 0

    def ingest_bytes(name: str, data: bytes | None, sha: str, size: int, parent: str | None, depth: int) -> None:
        nonlocal degraded
        doc_id = _new_doc_id()
        dup = store.find_by_sha(ctx, sha)
        pages: list[Page] = []
        chunks: list[tuple[int, int, int, str]] = []
        meta: dict = {}
        children: list[tuple[str, bytes]] = []
        if dup is not None:
            kind, status, reason = "duplicate", "duplicate", "same_sha256_as_existing"
            meta["duplicate_of"] = dup
        elif data is None:
            kind, status, reason = "unknown", "too_large", "file_size_limit"
        else:
            res = run_parser(data, app.settings, app.root / "tmp")
            kind, status, reason, meta, children = res.kind, res.status, res.reason, res.meta, res.children
            meta["sandbox"] = res.sandbox
            degraded += res.sandbox != "isolated"
            if status in ("indexed", "indexed_low_confidence"):
                for p in res.pages:
                    pages.append(Page(doc_id, p["page_no"], p["locator"], p["text"], p["ocr"], p["ocr_conf"]))
                    for s, e in chunk_page(p["text"]):
                        chunks.append((p["page_no"], s, e, p["text"][s:e]))
        if data is not None and dup is None:
            store.put_blob(ctx, doc_id, data)
        store.add_document(ctx, doc_id=doc_id, parent_id=parent, source_name=name, sha=sha, size=size,
                           kind=kind, status=status, reason=reason, restriction=restriction,
                           meta_json=json.dumps(meta), pages=pages, chunks=chunks)
        summary[status] = summary.get(status, 0) + 1
        doc_ids.append(doc_id)
        app.audit.record(ctx.user_id, "ingest_document", status, case_id=ctx.case_id, target=doc_id,
                         parent=parent, reason=reason, pages=len(pages))
        log_event("document_ingested", case_id=ctx.case_id, doc_id=doc_id, status=status, reason=reason,
                  pages=len(pages), chunks=len(chunks))
        if children and depth < MAX_DEPTH:
            import hashlib

            for child_name, blob in children:
                too_big = len(blob) > app.settings.max_file_bytes
                ingest_bytes(f"{name}::attachment::{child_name}", None if too_big else blob,
                             hashlib.sha256(blob).hexdigest(), len(blob), doc_id, depth + 1)
        elif children:
            summary["attachments_not_expanded_depth"] = summary.get("attachments_not_expanded_depth", 0) + len(children)

    for f in files:
        rel, data, sha = guard.read(f, app.settings.max_file_bytes)
        ingest_bytes(rel, data, sha, f.stat().st_size, None, 0)

    app.audit.record(ctx.user_id, "ingest", "ok", case_id=ctx.case_id,
                     documents=len(doc_ids), files=len(files), duration_ms=int((time.time() - t0) * 1000),
                     **{f"n_{k}": v for k, v in sorted(summary.items())})
    return {"files": len(files), "documents": len(doc_ids), "by_status": summary, "sandbox_degraded": degraded}
