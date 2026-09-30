"""Permission-checked, watermarked, logged exports.

Every exported file carries a watermark naming the exporting user, the UTC
timestamp, the case and a unique export ID, on every page (PDF) or in the
header and footer (CSV). The caller (App.export) has already checked the
EXPORT permission and records the export, including the file's SHA-256, in
the audit log.

An export is plaintext that leaves the encrypted store by design. Where it
goes after that is outside this system's control (SECURITY.md).
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .authz import CaseAccessContext
from .coverage import coverage_report, coverage_summary_line
from .errors import ConfigError

LEAD_NOTICE = "Leads for attorney review. Not legal conclusions. Verify every item against the source."


def _watermark(app, ctx: CaseAccessContext, export_id: str) -> str:
    row = app.control.execute("SELECT username FROM users WHERE user_id=?", (ctx.user_id,)).fetchone()
    who = row[0] if row else ctx.user_id
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"CONFIDENTIAL - exported by {who} ({ctx.user_id}) at {ts} - case {ctx.case_id} - export {export_id}"


def _rows(app, ctx: CaseAccessContext, what: str) -> tuple[list[str], list[list], str]:
    store = app.store(ctx)
    rep = coverage_report(store, ctx)
    if what == "coverage":
        header = ["doc_id", "source_name", "status", "reason", "explanation"]
        rows = [[g[k] for k in header] for g in rep["not_searchable"]]
        rows += [[d["doc_id"], d["source_name"], "indexed_low_confidence", d["reason"], "Check OCR pages manually."]
                 for d in rep["low_confidence"]]
        return header, rows, coverage_summary_line(rep)
    if what == "documents":
        header = ["doc_id", "parent_id", "source_name", "kind", "status", "reason", "page_count", "ocr_pages", "low_conf_pages"]
        return header, [[d[k] for k in header] for d in store.list_documents(ctx)], coverage_summary_line(rep)
    raise ConfigError("export_kind_unknown")


def export_report(app, ctx: CaseAccessContext, what: str, fmt: str, out_dir: Path) -> tuple[Path, str]:
    export_id = "x_" + uuid.uuid4().hex[:12]
    mark = _watermark(app, ctx, export_id)
    header, rows, summary = _rows(app, ctx, what)
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = out_dir / f"{ctx.case_id}-{what}-{export_id}.{fmt}"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([mark])
        w.writerow([LEAD_NOTICE])
        w.writerow([summary])
        w.writerow(header)
        for r in rows:
            # Neutralize spreadsheet formula injection from document-derived text.
            w.writerow([("'" + c) if isinstance(c, str) and c[:1] in ("=", "+", "-", "@", "\t", "\r") else c for c in r])
        w.writerow([mark])
        data = buf.getvalue().encode()
    elif fmt == "pdf":
        data = _pdf(mark, summary, header, rows)
    else:
        raise ConfigError("export_format_unknown")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return path, hashlib.sha256(data).hexdigest()


def _pdf(mark: str, summary: str, header: list[str], rows: list[list]) -> bytes:
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(letter))
    c.setTitle("lexreview export")
    width, height = landscape(letter)

    def decorate():
        c.saveState()
        c.setFont("Helvetica-Bold", 22)
        c.setFillGray(0.85)
        c.translate(width / 2, height / 2)
        c.rotate(30)
        c.drawCentredString(0, 0, mark[:90])
        c.restoreState()
        c.setFont("Helvetica", 7)
        c.drawString(30, 15, mark)
        c.drawString(30, height - 20, LEAD_NOTICE)

    decorate()
    y = height - 40
    c.setFont("Helvetica", 8)
    c.drawString(30, y, summary[:200])
    y -= 16
    c.setFont("Helvetica-Bold", 7)
    c.drawString(30, y, " | ".join(header))
    c.setFont("Helvetica", 7)
    for r in rows:
        y -= 11
        if y < 35:
            c.showPage()
            decorate()
            c.setFont("Helvetica", 7)
            y = height - 40
        c.drawString(30, y, " | ".join("" if v is None else str(v) for v in r)[:220])
    c.showPage()
    c.save()
    return buf.getvalue()
