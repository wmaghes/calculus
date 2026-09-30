"""Coverage report: what was and was NOT reviewed.

Silent gaps are the most dangerous failure, so every search, answer,
timeline and export carries this report (or its summary). It lists every
document that is not fully searchable and why, plus the number of documents
the requesting user cannot see because of restriction labels.
"""

from __future__ import annotations

from .authz import CaseAccessContext
from .casestore import SEARCHABLE, CaseStore

STATUS_EXPLANATION = {
    "indexed": "Text extracted and searchable.",
    "indexed_low_confidence": "Searchable, but some pages had failed or low-confidence OCR. Check those pages by eye.",
    "ocr_failed": "Scanned file: OCR recovered no text. NOT searchable. Review manually.",
    "corrupted": "File could not be read (damaged or malformed). NOT searchable.",
    "password_protected": "Encrypted/password-protected. NOT searchable. Obtain the password or a decrypted copy.",  # nosec B105 - message text
    "unsupported": "Format not supported in this build. NOT searchable.",
    "too_large": "Exceeded a size/page limit. NOT searchable.",
    "rejected_unsafe": "Rejected as unsafe (e.g. decompression bomb). NOT searchable.",
    "timeout": "Parsing timed out. NOT searchable.",
    "parse_error": "Parser failed unexpectedly. NOT searchable.",
    "duplicate": "Exact duplicate of another document (same SHA-256). The original is searchable.",
}


def coverage_report(store: CaseStore, ctx: CaseAccessContext) -> dict:
    docs = store.list_documents(ctx)
    by_status: dict[str, int] = {}
    gaps = []
    low_pages = []
    total_pages = 0
    for d in docs:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
        total_pages += d["page_count"]
        if d["status"] not in SEARCHABLE and d["status"] != "duplicate":
            gaps.append({"doc_id": d["doc_id"], "source_name": d["source_name"], "status": d["status"],
                         "reason": d["reason"], "explanation": STATUS_EXPLANATION.get(d["status"], "")})
        elif d["status"] == "indexed_low_confidence":
            low_pages.append({"doc_id": d["doc_id"], "source_name": d["source_name"], "reason": d["reason"]})
    searchable = sum(v for k, v in by_status.items() if k in SEARCHABLE)
    return {
        "case_id": ctx.case_id,
        "documents_total_visible": len(docs),
        "documents_searchable": searchable,
        "documents_not_searchable": len(gaps),
        "documents_withheld_by_restriction": store.withheld_count(ctx),
        "pages_total": total_pages,
        "by_status": dict(sorted(by_status.items())),
        "not_searchable": gaps,
        "low_confidence": low_pages,
    }


def coverage_summary_line(rep: dict) -> str:
    s = (f"Coverage: {rep['documents_searchable']} of {rep['documents_total_visible']} visible documents searchable; "
         f"{rep['documents_not_searchable']} NOT searchable")
    if rep["low_confidence"]:
        s += f"; {len(rep['low_confidence'])} with low-confidence OCR pages"
    if rep["documents_withheld_by_restriction"]:
        s += f"; {rep['documents_withheld_by_restriction']} withheld from you by restriction labels"
    return s + "."
