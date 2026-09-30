"""Instruction-driven document ranking: "find everything relevant to X".

Recall first. The instruction is parsed into:
  * a topic (the words left after removing date phrases and filler),
  * an optional date range ("between March and June 2023", "in April 2023",
    "after May 1, 2023", "before 6/30/2023"),
  * optional people/organizations named in it (matched against the case's
    extracted entities).

Every candidate document ends up in exactly one list, so nothing is dropped
silently:
  ranked         matches the topic (or names), and has a date in range or no range was given
  undated        matches, but no date could be found in it (check manually)
  outside_range  matches, but every date found in it is outside the range

Each document carries its best verified passage with a jump-to-passage link,
the reasons it was included, and an evidence-based band. An optional model
pass can add a note to a document, but only with a quote that verifies, and
it can never remove or demote a document.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import date

from .authz import CaseAccessContext, Perm
from .casestore import CaseStore
from .citations import normalize, normalize_with_map
from .extract.dates import find_dates
from .extract.timeline import entities as list_entities
from .search.hybrid import hybrid_search, viewer_link

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
_MREF = re.compile(r"(?<![A-Za-z])(" + "|".join(sorted((m for m in _MONTHS), key=len, reverse=True)) +
                   r")\.?(?:\s{1,3}(\d{1,2})(?:st|nd|rd|th)?)?(?:,?\s{1,3}((?:19|20)\d{2}))?(?![A-Za-z])", re.I)
_FILLER = re.compile(r"\b(find|show|list|give|get|everything|anything|all|documents?|docs|files?|relevant|related|"
                     r"regarding|concerning|about|involving|between|from|to|and|in|during|after|since|before|until|"
                     r"by|on|of|the|a|an|me|build|chronology|timeline|events?)\b", re.I)


def parse_instruction(text: str, known_entities: list[dict]) -> dict:
    spans, points = [], []
    for m in _MREF.finditer(text):
        mo = _MONTHS[m.group(1).lower()]
        if m.group(1).lower() == "may" and m.group(1) != "May":
            continue
        day = int(m.group(2)) if m.group(2) else None
        yr = int(m.group(3)) if m.group(3) else None
        points.append([m.start(), mo, day, yr])
        spans.append(m.span())
    for d in find_dates(text):
        if d.kind in ("iso", "mdy_num") and d.value_start and not any(a <= d.start < b for a, b in spans):
            points.append([d.start, d.value_start.month, d.value_start.day, d.value_start.year])
            spans.append((d.start, d.end))
    points.sort()
    notes = []
    for i, p in enumerate(points):  # "between March and June 2023": March takes 2023
        if p[3] is None:
            later = [q[3] for q in points[i + 1:] if q[3]]
            earlier = [q[3] for q in points[:i] if q[3]]
            p[3] = later[0] if later else (earlier[-1] if earlier else None)
            if p[3] is None:
                notes.append("A month in the instruction has no year; it was not used as a date filter.")
    points = [p for p in points if p[3]]
    rng_from = rng_to = None
    if points:
        def first(p):
            return date(p[3], p[1], p[2] or 1)

        def last(p):
            return date(p[3], p[1], p[2] or calendar.monthrange(p[3], p[1])[1])
        low = text.lower()
        pos0 = points[0][0]
        prefix = low[max(0, pos0 - 12):pos0]
        if len(points) == 1 and re.search(r"\b(after|since|from)\s*$", prefix):
            rng_from = first(points[0])
        elif len(points) == 1 and re.search(r"\b(before|until|by)\s*$", prefix):
            rng_to = last(points[0])
        else:
            rng_from, rng_to = min(first(p) for p in points), max(last(p) for p in points)
    topic = text
    for a, b in sorted(spans, reverse=True):
        topic = topic[:a] + " " + topic[b:]
    names = [e for e in known_entities if e["name"].lower() in text.lower()
             or (e["kind"] == "org" and e["name"].split()[0].lower() in text.lower().split())]
    for e in names:
        topic = re.sub(re.escape(e["name"]), " ", topic, flags=re.I)
    topic = " ".join(_FILLER.sub(" ", topic).split())
    return {"topic": topic, "date_from": rng_from, "date_to": rng_to, "entities": names, "notes": notes}


def _doc_dates(store: CaseStore, top_ids: list[str]) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {d: [] for d in top_ids}
    if not top_ids:
        return out
    q = ",".join("?" * len(top_ids))
    for top, ds, de in store.conn.execute(
            f"SELECT COALESCE(d.parent_id, d.doc_id), ev.date_start, ev.date_end FROM events ev "  # nosec B608 - placeholders only
            f"JOIN documents d ON d.doc_id = ev.doc_id WHERE COALESCE(d.parent_id, d.doc_id) IN ({q})", top_ids):
        out.setdefault(top, []).append((ds, de))
    return out


def rank_documents(store: CaseStore, ctx: CaseAccessContext, index, instruction: str, backend=None,
                   model_notes_for: int = 15) -> dict:
    ctx.require(Perm.SEARCH)
    instruction = (instruction or "").strip()[:2000]
    ents = list_entities(store, ctx)
    parsed = parse_instruction(instruction, ents)
    search = hybrid_search(store, ctx, index, parsed["topic"] or instruction, top_k=10_000)
    docs: dict[str, dict] = {}
    for h in search["results"]:
        d = docs.setdefault(h["top_level_doc_id"], {"doc_id": h["top_level_doc_id"], "best": h, "passages": 0,
                                                    "reasons": [], "entity_hits": []})
        d["passages"] += 1
    # Documents mentioning a named person/org are candidates even without topic words.
    vis, vparams = store.visibility_sql(ctx)
    for e in parsed["entities"]:
        for doc_id, top in store.conn.execute(
                f"SELECT DISTINCT m.doc_id, COALESCE(d.parent_id, d.doc_id) FROM mentions m "  # nosec B608 - constant clause, bound params
                f"JOIN documents d ON d.doc_id = m.doc_id WHERE m.entity_id = ? AND {vis}", [e["entity_id"], *vparams]):
            d = docs.setdefault(top, {"doc_id": top, "best": None, "passages": 0, "reasons": [], "entity_hits": []})
            if e["name"] not in d["entity_hits"]:
                d["entity_hits"].append(e["name"])
    names = {r[0]: r[1] for r in store.conn.execute("SELECT doc_id, source_name FROM documents")}
    dates = _doc_dates(store, list(docs))
    ranked, undated, outside = [], [], []
    rf = parsed["date_from"].isoformat() if parsed["date_from"] else None
    rt = parsed["date_to"].isoformat() if parsed["date_to"] else None
    for top, d in docs.items():
        best = d["best"]
        if best is None:  # entity-only candidate: cite its first visible mention
            row = store.conn.execute(
                "SELECT m.doc_id, m.page_no, m.char_start, m.char_end, p.locator FROM mentions m "
                "JOIN pages p ON p.doc_id=m.doc_id AND p.page_no=m.page_no "
                "JOIN documents d ON d.doc_id=m.doc_id WHERE COALESCE(d.parent_id, d.doc_id)=? ORDER BY m.page_no, m.char_start LIMIT 1",
                (top,)).fetchone()
            if row is None:
                continue
            text = store.get_page(ctx, row[0], row[1]).text
            best = {"doc_id": row[0], "page_no": row[1], "char_start": row[2], "char_end": row[3], "locator": row[4],
                    "snippet": text[row[2]:row[3]], "band": "weak", "source_name": names.get(row[0], ""),
                    "link": viewer_link(ctx.case_id, row[0], row[1], row[2], row[3]), "ocr": False, "ocr_conf": None}
        in_range = [ds for ds, de in dates.get(top, []) if (rf is None or de >= rf) and (rt is None or ds <= rt)]
        score = (1.0 / (10 + best.get("rank", 1000))) + 0.01 * d["passages"] + 0.05 * len(d["entity_hits"])
        reasons = []
        if d["passages"]:
            reasons.append(f"{d['passages']} matching passage(s)")
        if d["entity_hits"]:
            reasons.append("mentions " + ", ".join(d["entity_hits"]))
        entry = {"doc_id": top, "source_name": names.get(top, ""), "score": round(score, 4), "band": best["band"],
                 "reasons": reasons, "dates_in_range": sorted(set(in_range))[:10],
                 "all_dates": sorted({ds for ds, _ in dates.get(top, [])})[:10],
                 "best_passage": {k: best[k] for k in ("doc_id", "page_no", "locator", "char_start", "char_end",
                                                        "snippet", "link", "ocr", "ocr_conf")},
                 "model_note": None}
        if (rf or rt) and not dates.get(top):
            undated.append(entry)
        elif (rf or rt) and not in_range:
            outside.append(entry)
        else:
            if in_range:
                entry["reasons"].append("dated in range: " + ", ".join(entry["dates_in_range"][:3]))
            ranked.append(entry)
    for lst in (ranked, undated, outside):
        lst.sort(key=lambda e: -e["score"])
        for i, e in enumerate(lst, start=1):
            e["rank"] = i
    if backend is not None and getattr(backend, "name", "").startswith(("ollama", "llamacpp")):
        for e in ranked[:model_notes_for]:
            e["model_note"] = _model_note(store, ctx, backend, parsed["topic"] or instruction, e)
    return {"instruction": instruction, "parsed": {**parsed, "date_from": rf, "date_to": rt},
            "ranked": ranked, "undated": undated, "outside_range": outside,
            "documents_searched": search["documents_searched"]}


def _model_note(store, ctx, backend, topic: str, entry: dict) -> dict | None:
    """Ask the local model whether the best passage is relevant; keep the
    answer only if its quote verifies inside that passage."""
    from .qa import build_prompt, looks_like_injection, neutralize, parse_output

    bp = entry["best_passage"]
    src = [{"id": "S1", "text": bp["snippet"]}]
    system, user, _ = build_prompt(f"Is this source relevant to: {topic}? If yes, give one claim with a quote.", src)
    try:
        parsed = parse_output(backend.complete(system, user, src, topic))
    except Exception:  # noqa: BLE001
        return None
    if not parsed or not parsed["claims"]:
        return None
    c = parsed["claims"][0]
    for cite in c["citations"]:
        q = normalize(cite["quote"])
        norm, _ = normalize_with_map(bp["snippet"])
        if cite["source"] == "S1" and len(q) >= 12 and q in norm:
            return {"text": neutralize(c["text"])[:500], "quote": cite["quote"][:500],
                    "source_flagged_injection": looks_like_injection(bp["snippet"])}
    return None


def recall(result: dict, relevant_names: set[str]) -> dict:
    main = {e["source_name"] for e in result["ranked"]}
    every = main | {e["source_name"] for e in result["undated"] + result["outside_range"]}
    return {"relevant": len(relevant_names), "found_in_ranked": len(relevant_names & main),
            "found_anywhere": len(relevant_names & every),
            "missed": sorted(relevant_names - every)}


_ = json
