"""Ingest pipeline: CourtListener public bulk data -> local Postgres.

Stages (each recorded in ingest_state; a finished stage is skipped on rerun):
  courts     courts CSV            -> courts rows for the configured court ids
  dockets    dockets CSV (stream)  -> docket_id -> court for those courts
  clusters   clusters CSV (stream) -> ingest_candidates (cases with a Harvard PDF)
  citations  citations CSV (stream)-> citation strings for candidates
  opinions   per candidate: fetch PDF, extract text (sandboxed), chunk, embed,
             insert opinion + text + chunks in ONE transaction, mark done.

Idempotent: opinions are unique on (source, cluster_id); a candidate already
done is skipped. Resumable: an interrupted run continues from the next
pending candidate. The sample is the N most-cited candidates, balanced across
jurisdictions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.chunking import chunk
from app.db import audit

from .bulk import BulkClient
from .pdftext import extract

CONFIG = Path(__file__).resolve().parents[1] / "jurisdictions.json"
MIN_TEXT = 500


def load_config(path: Path = CONFIG) -> dict[str, list[str]]:
    cfg = json.loads(path.read_text())
    return {k: v["courts"] for k, v in cfg.items() if not k.startswith("_")}


def _state(conn, key):
    row = conn.execute("SELECT value FROM ingest_state WHERE key=%s", (key,)).fetchone()
    return row[0] if row else None


def _set_state(conn, key, value) -> None:
    conn.execute("INSERT INTO ingest_state (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE "
                 "SET value=EXCLUDED.value, updated_at=now()", (key, json.dumps(value)))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class Ingest:
    def __init__(self, conn, bulk: BulkClient, embedder, config: dict[str, list[str]] | None = None, log=print):
        self.conn, self.bulk, self.embedder, self.log = conn, bulk, embedder, log
        self.config = config or load_config()
        self.court_juris = {c: j for j, cs in self.config.items() for c in cs}
        conn.execute("CREATE TABLE IF NOT EXISTS ingest_dockets (docket_id bigint PRIMARY KEY, court_id text NOT NULL, docket_number text)")

    def _stage(self, name: str, fn) -> None:
        done = _state(self.conn, f"stage:{name}")
        if done and done.get("done"):
            self.log(f"stage {name}: already done, skipping")
            return
        result = fn()
        _set_state(self.conn, f"stage:{name}", {"done": True, **(result or {})})
        audit(self.conn, "ingest", f"stage_{name}_done", **(result or {}))
        self.log(f"stage {name}: {result}")

    def courts(self) -> dict:
        key = self.bulk.latest("bulk-data/courts-")
        found = 0
        for row in self.bulk.rows(key):
            if row.get("id") in self.court_juris:
                self.conn.execute("INSERT INTO courts (id, name, jurisdiction) VALUES (%s,%s,%s) ON CONFLICT (id) DO UPDATE "
                                  "SET name=EXCLUDED.name", (row["id"], row.get("full_name") or row["id"], self.court_juris[row["id"]]))
                found += 1
        missing = set(self.court_juris) - {r[0] for r in self.conn.execute("SELECT id FROM courts")}
        if missing:
            raise RuntimeError(f"configured court ids not found in bulk courts file: {sorted(missing)}")
        return {"file": key, "courts": found}

    def dockets(self) -> dict:
        key = self.bulk.latest("bulk-data/dockets-")
        n = kept = 0
        batch = []
        for row in self.bulk.rows(key):
            n += 1
            if row.get("court_id") in self.court_juris:
                batch.append((_int(row["id"]), row["court_id"], (row.get("docket_number") or "")[:200]))
                if len(batch) >= 5000:
                    kept += self._put_dockets(batch)
                    batch = []
            if n % 1_000_000 == 0:
                self.log(f"  dockets scanned {n:,}, kept {kept + len(batch):,}")
        kept += self._put_dockets(batch)
        return {"file": key, "scanned": n, "kept": kept}

    def _put_dockets(self, batch) -> int:
        if batch:
            with self.conn.cursor() as cur:
                cur.executemany("INSERT INTO ingest_dockets VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", batch)
        return len(batch)

    def clusters(self) -> dict:
        key = self.bulk.latest("bulk-data/opinion-clusters-")
        dockets = {r[0]: (r[1], r[2]) for r in self.conn.execute("SELECT docket_id, court_id, docket_number FROM ingest_dockets")}
        n = kept = 0
        batch = []
        for row in self.bulk.rows(key):
            n += 1
            d = dockets.get(_int(row.get("docket_id")))
            pdf = row.get("filepath_pdf_harvard") or ""
            if d and pdf.startswith("harvard_pdf/") and row.get("blocked") != "t":
                batch.append((_int(row["id"]), d[0], (row.get("case_name") or row.get("case_name_full") or "")[:500],
                              row.get("date_filed") or None, (row.get("judges") or "")[:500], _int(row["docket_id"]), d[1],
                              row.get("precedential_status") or None, _int(row.get("citation_count")) or 0,
                              (row.get("slug") or "")[:200], pdf))
                if len(batch) >= 2000:
                    kept += self._put_candidates(batch)
                    batch = []
            if n % 1_000_000 == 0:
                self.log(f"  clusters scanned {n:,}, kept {kept + len(batch):,}")
        kept += self._put_candidates(batch)
        return {"file": key, "scanned": n, "kept": kept}

    def _put_candidates(self, batch) -> int:
        if batch:
            with self.conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO ingest_candidates (cluster_id, court_id, case_name, date_filed, judges, docket_id, docket_number, "
                    "precedential_status, citation_count, slug, pdf_path) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (cluster_id) DO NOTHING", batch)
        return len(batch)

    def citations(self) -> dict:
        key = self.bulk.latest("bulk-data/citations-")
        wanted = {r[0] for r in self.conn.execute("SELECT cluster_id FROM ingest_candidates")}
        found: dict[int, list[str]] = {}
        for row in self.bulk.rows(key):
            cid = _int(row.get("cluster_id"))
            if cid in wanted:
                found.setdefault(cid, []).append(f"{row.get('volume')} {row.get('reporter')} {row.get('page')}".strip())
        with self.conn.cursor() as cur:
            cur.executemany("UPDATE ingest_candidates SET citation=%s WHERE cluster_id=%s",
                            [("; ".join(sorted(v)), k) for k, v in found.items()])
        return {"file": key, "with_citation": len(found)}

    def select_sample(self, size: int) -> list[int]:
        """Most-cited candidates, split evenly across jurisdictions (a stable
        choice, so reruns pick the same sample)."""
        per = max(1, size // max(1, len(self.config)))
        chosen = []
        for juris, courts in self.config.items():
            rows = self.conn.execute(
                "SELECT cluster_id FROM ingest_candidates WHERE court_id = ANY(%s) AND precedential_status IS DISTINCT FROM 'Unpublished' "
                "ORDER BY citation_count DESC, cluster_id LIMIT %s", (courts, per)).fetchall()
            chosen += [r[0] for r in rows]
        return chosen

    def opinions(self, size: int) -> dict:
        ids = self.select_sample(size)
        done = failed = skipped = 0
        for i, cid in enumerate(ids, 1):
            c = self.conn.execute("SELECT cluster_id, court_id, case_name, date_filed, judges, docket_id, docket_number, "
                                  "precedential_status, citation_count, slug, pdf_path, citation, status FROM ingest_candidates "
                                  "WHERE cluster_id=%s", (cid,)).fetchone()
            if c[12] == "done" or self.conn.execute(
                    "SELECT 1 FROM opinions WHERE source='courtlistener' AND cluster_id=%s", (cid,)).fetchone():
                skipped += 1
                continue
            status = self._one(c)
            self.conn.execute("UPDATE ingest_candidates SET status=%s WHERE cluster_id=%s", (status, cid))
            done += status == "done"
            failed += status != "done"
            if i % 50 == 0:
                self.log(f"  opinions {i}/{len(ids)}: done {done}, failed {failed}, skipped {skipped}")
        return {"selected": len(ids), "done": done, "failed": failed, "skipped_existing": skipped}

    def _one(self, c) -> str:
        (cid, court, name, date, judges, docket_id, docket_no, prec, cites, slug, pdf_path, citation, _status) = c
        try:
            data = self.bulk.get(pdf_path)
        except Exception as exc:  # network / HTTP errors -> recorded, run continues
            return f"failed:download_{type(exc).__name__}"
        res = extract(data)
        if not res.get("ok"):
            return f"failed:{res.get('reason')}"
        text = res["text"]
        if len(text.strip()) < MIN_TEXT:
            return "failed:too_little_text"
        spans = chunk(text)
        vecs = self.embedder.embed_documents([text[s:e] for s, e in spans])
        url = f"https://www.courtlistener.com/opinion/{cid}/{slug}/" if slug else f"https://www.courtlistener.com/opinion/{cid}/"
        with self.conn.transaction():
            oid = self.conn.execute(
                "INSERT INTO opinions (source, cluster_id, case_name, citation, court_id, date_filed, judges, docket_id, docket_number, "
                "precedential_status, citation_count, source_url, text_url, text_sha256, text_chars) "
                "VALUES ('courtlistener',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (source, cluster_id) DO NOTHING RETURNING id",
                (cid, name, citation, court, date, judges, docket_id, docket_no, prec, cites, url,
                 f"{self.bulk.base}/{pdf_path}", hashlib.sha256(text.encode()).hexdigest(), len(text))).fetchone()
            if oid is None:
                return "done"
            oid = oid[0]
            self.conn.execute("INSERT INTO opinion_texts (opinion_id, text) VALUES (%s,%s)", (oid, text))
            with self.conn.cursor() as cur:
                cur.executemany("INSERT INTO chunks (opinion_id, position, char_start, char_end, text, embedding, embed_model) "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                [(oid, i, s, e, text[s:e], vecs[i], self.embedder.name) for i, (s, e) in enumerate(spans)])
        return "done"

    def run(self, size: int) -> None:
        self._stage("courts", self.courts)
        self._stage("dockets", self.dockets)
        self._stage("clusters", self.clusters)
        self._stage("citations", self.citations)
        res = self.opinions(size)
        audit(self.conn, "ingest", "opinions_run", **res)
        self.log(f"opinions: {res}")
