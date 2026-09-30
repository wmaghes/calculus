"""Build the case's structured store: entities, mentions, dated events.

Rebuilt for the whole case after each ingestion run (the people list is
case-wide, so a name learned from one document is matched in all others).
Runs on stored page text only. Documents that are not searchable (OCR
failed, password-protected, ...) contribute nothing and stay listed in the
coverage report.
"""

from __future__ import annotations

import json
from email.utils import parsedate_to_datetime

from ..authz import CaseAccessContext, Perm
from ..casestore import SEARCHABLE, CaseStore
from .dates import find_dates, resolve_years
from .entities import find_all, org_candidates, people_candidates
from .segments import segments, window

TAGS = {
    "temperature": ("temperature", "degrees", "excursion", "reefer", "setpoint", "alarm"),
    "notice": ("notice", "notif", "called", "call ", "inform"),
    "rejection": ("reject",),
    "claim/insurance": ("claim", "insur"),
    "agreement": ("agreement", "amendment", "signed", "effective", "amended"),
    "maintenance": ("maintenance", "compressor", "calibrat", "repair", "replace"),
    "payment": ("invoice", "payment", "rate", "usd"),
}


def _tags(text: str) -> list[str]:
    low = text.lower()
    return [t for t, kws in TAGS.items() if any(k in low for k in kws)]


def _doc_date(meta: dict):
    raw = meta.get("date")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date()
    except (TypeError, ValueError, IndexError):
        return None


def run_extraction(store: CaseStore, ctx: CaseAccessContext) -> dict:
    store._ctx(ctx, Perm.INGEST)
    c = store.conn
    marks = ",".join("?" * len(SEARCHABLE))
    docs = c.execute(
        f"SELECT doc_id, parent_id, kind, meta_json FROM documents WHERE status IN ({marks})",  # nosec B608 - constant clause, bound params
        SEARCHABLE).fetchall()
    meta = {d[0]: json.loads(d[3] or "{}") for d in docs}
    all_parents = dict(c.execute("SELECT doc_id, parent_id FROM documents").fetchall())
    all_meta = {r[0]: json.loads(r[1] or "{}") for r in c.execute("SELECT doc_id, meta_json FROM documents")}
    pages: dict[str, list[tuple[int, str]]] = {}
    for doc_id, page_no, text in c.execute(
            f"SELECT p.doc_id, p.page_no, p.text FROM pages p JOIN documents d ON d.doc_id=p.doc_id "  # nosec B608 - constant clause, bound params
            f"WHERE d.status IN ({marks}) ORDER BY p.doc_id, p.page_no", SEARCHABLE):
        pages.setdefault(doc_id, []).append((page_no, text))

    all_texts = [t for pl in pages.values() for _, t in pl]
    email_meta = [m for m in meta.values() if "from" in m or "to" in m]
    people = sorted(people_candidates(all_texts, email_meta))
    orgs = org_candidates(all_texts)
    surnames: dict[str, list[str]] = {}
    for n in people:
        surnames.setdefault(n.split()[-1], []).append(n)

    c.execute("BEGIN")
    try:
        for tbl in ("event_entities", "events", "mentions", "unresolved_dates", "entities"):
            c.execute(f"DELETE FROM {tbl}")  # nosec B608 - fixed table names
        ent_id: dict[tuple[str, str], int] = {}
        for n in people:
            ent_id[("person", n)] = c.execute("INSERT INTO entities (kind, name) VALUES ('person', ?)", (n,)).lastrowid
        for canon in sorted(orgs):
            ent_id[("org", canon)] = c.execute("INSERT INTO entities (kind, name) VALUES ('org', ?)", (canon,)).lastrowid

        n_events = n_unresolved = n_mentions = 0
        for doc_id, plist in pages.items():
            # Attachments inherit their parent email's date as the anchor.
            anchor = _doc_date(meta[doc_id]) or _doc_date(all_meta.get(all_parents.get(doc_id) or "", {}))
            # ---- mentions
            page_mentions: dict[int, list[tuple[int, int, int]]] = {}
            for page_no, text in plist:
                spans: list[tuple[int, int, int, str]] = []
                for n in people:
                    for s, e in find_all(text, n):
                        spans.append((s, e, ent_id[("person", n)], "full_name"))
                    last = n.split()[-1]
                    if len(surnames[last]) == 1 and len(last) > 3:
                        for s, e in find_all(text, last):
                            if not any(a <= s < b for a, b, _, _ in spans):
                                spans.append((s, e, ent_id[("person", n)], "surname"))
                for canon, aliases in orgs.items():
                    taken: list[tuple[int, int]] = []
                    for alias in sorted(aliases, key=len, reverse=True):
                        for s, e in find_all(text, alias):
                            if not any(a < e and s < b for a, b in taken):
                                taken.append((s, e))
                                spans.append((s, e, ent_id[("org", canon)], "name" if alias == canon else "alias"))
                for s, e, eid, method in spans:
                    c.execute("INSERT INTO mentions (entity_id, doc_id, page_no, char_start, char_end, method) VALUES (?,?,?,?,?,?)",
                              (eid, doc_id, page_no, s, e, method))
                n_mentions += len(spans)
                page_mentions[page_no] = [(s, e, eid) for s, e, eid, _ in spans]
            # ---- dates (resolved with document-wide context)
            by_page = {pn: find_dates(t) for pn, t in plist}
            flat = []
            for pn, ms in by_page.items():
                for m in ms:
                    m.start += pn * 10**8
                    m.end += pn * 10**8
                    flat.append(m)
            flat.sort(key=lambda m: m.start)
            resolve_years([m for m in flat if m.kind != "relative"], anchor)
            for m in flat:
                pn = m.start // 10**8
                m.start -= pn * 10**8
                m.end -= pn * 10**8
            # ---- events
            for pn, text in plist:
                segs = segments(text)
                is_email_first = meta[doc_id].get("from") is not None and pn == 1
                seen = set()
                for m in by_page[pn]:
                    seg = next(((s, e) for s, e in segs if s <= m.start and m.end <= e), None) or (m.start, m.end)
                    seg = window(text, seg, (m.start, m.end))
                    if not m.resolved:
                        c.execute("INSERT INTO unresolved_dates (doc_id, page_no, char_start, char_end, seg_start, seg_end, kind) "
                                  "VALUES (?,?,?,?,?,?,?)", (doc_id, pn, m.start, m.end, seg[0], seg[1], m.kind))
                        n_unresolved += 1
                        continue
                    key = (seg, m.value_start)
                    if key in seen:
                        continue
                    seen.add(key)
                    seg_text = text[seg[0]:seg[1]]
                    source = "email_header" if is_email_first and seg_text.startswith("From:") else "text"
                    eid = c.execute(
                        "INSERT INTO events (doc_id, page_no, seg_start, seg_end, date_start, date_end, precision, "
                        "date_char_start, date_char_end, flags, tags, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (doc_id, pn, seg[0], seg[1], m.value_start.isoformat(), m.value_end.isoformat(), m.precision,
                         m.start, m.end, json.dumps(m.flags), json.dumps(_tags(seg_text)), source)).lastrowid
                    for s, e, ent in page_mentions.get(pn, []):
                        if seg[0] <= s and e <= seg[1]:
                            c.execute("INSERT OR IGNORE INTO event_entities (event_id, entity_id) VALUES (?,?)", (eid, ent))
                    n_events += 1
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
    return {"people": len(people), "orgs": len(orgs), "mentions": n_mentions, "events": n_events,
            "unresolved_dates": n_unresolved}
