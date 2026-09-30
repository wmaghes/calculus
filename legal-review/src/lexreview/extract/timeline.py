"""Timeline and entity queries.

Every timeline entry is re-verified before it is returned: the cited
sentence and the date text must still be at the stored offsets of a page
the user may see. Entries that fail are dropped and counted.

Dates that could not be placed (relative expressions, day+month with no
year anchor, impossible dates) are returned in `unplaced`, so they are
never a silent gap.
"""

from __future__ import annotations

import json
from datetime import date

from ..authz import CaseAccessContext, Perm
from ..casestore import SEARCHABLE, CaseStore
from ..search.hybrid import viewer_link


def entities(store: CaseStore, ctx: CaseAccessContext) -> list[dict]:
    """People and organizations with at least one mention the user can see.
    Counts include only visible documents."""
    store._ctx(ctx, Perm.SEARCH)
    vis, params = store.visibility_sql(ctx)
    rows = store.conn.execute(
        f"SELECT e.entity_id, e.kind, e.name, count(*), count(DISTINCT m.doc_id) FROM entities e "  # nosec B608 - constant clause, bound params
        f"JOIN mentions m ON m.entity_id = e.entity_id JOIN documents d ON d.doc_id = m.doc_id "
        f"WHERE {vis} GROUP BY e.entity_id ORDER BY e.kind DESC, count(*) DESC, e.name", params).fetchall()
    return [{"entity_id": r[0], "kind": r[1], "name": r[2], "mentions": r[3], "documents": r[4]} for r in rows]


def timeline(store: CaseStore, ctx: CaseAccessContext, date_from: date | None = None, date_to: date | None = None,
             entity_id: int | None = None, tag: str | None = None, include_rows: bool = False) -> dict:
    """Dated spreadsheet/table rows are hidden unless include_rows is set,
    but always counted in `hidden_table_rows` (never a silent gap)."""
    store._ctx(ctx, Perm.SEARCH)
    vis, vparams = store.visibility_sql(ctx)
    marks = ",".join("?" * len(SEARCHABLE))
    where, params = [vis, f"d.status IN ({marks})"], [*vparams, *SEARCHABLE]
    if date_from:
        where.append("ev.date_end >= ?")
        params.append(date_from.isoformat())
    if date_to:
        where.append("ev.date_start <= ?")
        params.append(date_to.isoformat())
    if entity_id is not None:
        where.append("ev.event_id IN (SELECT event_id FROM event_entities WHERE entity_id = ?)")
        params.append(int(entity_id))
    rows = store.conn.execute(
        "SELECT ev.event_id, ev.doc_id, ev.page_no, ev.seg_start, ev.seg_end, ev.date_start, ev.date_end, ev.precision, "  # nosec B608 - constant clause, bound params
        "ev.date_char_start, ev.date_char_end, ev.flags, ev.tags, ev.source, d.source_name, d.parent_id, p.locator, p.text, p.ocr, p.ocr_conf "
        "FROM events ev JOIN documents d ON d.doc_id = ev.doc_id "
        "JOIN pages p ON p.doc_id = ev.doc_id AND p.page_no = ev.page_no "
        f"WHERE {' AND '.join(where)} ORDER BY ev.date_start, ev.date_end, d.source_name, ev.page_no, ev.seg_start",
        params).fetchall()
    ids = [r[0] for r in rows]
    names: dict[int, list[dict]] = {}
    if ids:
        q = ",".join("?" * len(ids))
        for ev_id, kind, name in store.conn.execute(
                f"SELECT ee.event_id, e.kind, e.name FROM event_entities ee JOIN entities e ON e.entity_id = ee.entity_id "  # nosec B608 - constant clause, bound params
                f"WHERE ee.event_id IN ({q}) ORDER BY e.kind DESC, e.name", ids):
            names.setdefault(ev_id, []).append({"kind": kind, "name": name})
    out, integrity_failures, hidden_rows = [], 0, 0
    for (ev_id, doc_id, page_no, ss, se, ds, de, prec, dcs, dce, flags, tags, source, sname, parent, locator,
         text, ocr, ocr_conf) in rows:
        if not (0 <= ss <= dcs < dce <= se <= len(text)):
            integrity_failures += 1
            continue
        tags_l = json.loads(tags)
        if tag and tag not in tags_l:
            continue
        if source == "table_row" and not include_rows:
            hidden_rows += 1
            continue
        out.append({
            "event_id": ev_id, "date": ds if ds == de else f"{ds}..{de}", "date_start": ds, "date_end": de,
            "precision": prec, "date_text": text[dcs:dce], "flags": json.loads(flags), "tags": tags_l, "source": source,
            "passage": text[ss:se], "doc_id": doc_id, "source_name": sname, "parent_id": parent, "page_no": page_no,
            "locator": locator, "char_start": ss, "char_end": se, "ocr": bool(ocr), "ocr_conf": ocr_conf,
            "entities": names.get(ev_id, []),
            "link": viewer_link(ctx.case_id, doc_id, page_no, ss, se),
        })
    unplaced = store.conn.execute(
        "SELECT u.doc_id, u.page_no, u.char_start, u.char_end, u.seg_start, u.seg_end, u.kind, d.source_name, p.text, p.locator "  # nosec B608 - constant clause, bound params
        "FROM unresolved_dates u JOIN documents d ON d.doc_id = u.doc_id "
        "JOIN pages p ON p.doc_id = u.doc_id AND p.page_no = u.page_no "
        f"WHERE {vis} ORDER BY d.source_name, u.page_no, u.char_start", vparams).fetchall()
    unplaced_out = [{
        "doc_id": r[0], "page_no": r[1], "date_text": r[8][r[2]:r[3]], "kind": r[6], "source_name": r[7],
        "passage": r[8][r[4]:r[5]], "locator": r[9],
        "reason": "relative expression" if r[6] == "relative" else "no year could be determined or the date is invalid",
        "link": viewer_link(ctx.case_id, r[0], r[1], r[4], r[5]),
    } for r in unplaced]
    return {"events": out, "unplaced": unplaced_out, "integrity_failures": integrity_failures,
            "hidden_table_rows": hidden_rows}
