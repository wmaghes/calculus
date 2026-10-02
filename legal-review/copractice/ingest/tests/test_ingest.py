import bz2
import json

import httpx
import pytest

from app.chunking import chunk
from app.db import verify_audit
from app.embeddings import DIM, DevHashEmbedder
from cp_ingest.bulk import BulkClient
from cp_ingest.pipeline import Ingest

from fixtures import BASE, Bulk, bz2csv


# ------------------------------------------------------------------ chunking
def test_chunk_offsets_sizes_and_overlap():
    paras = [f"Paragraph {i}. " + ("The covenant not to compete is enforceable. " * (5 + i % 7)) for i in range(40)]
    text = "\n\n".join(paras)
    spans = chunk(text)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert s2 <= e1                       # contiguous or overlapping: no gaps
        assert e1 - s2 <= 400                 # overlap is small
    assert all(e - s <= 2200 for s, e in spans)
    assert all(e - s >= 400 for s, e in spans[:-1])


def test_chunk_giant_paragraph_and_tiny_text():
    giant = "word " * 3000
    spans = chunk(giant)
    assert len(spans) > 5 and all(e - s <= 2200 for s, e in spans)  # MAX + OVERLAP
    assert chunk("") == [] and chunk("Short opinion text.") == [(0, 19)]


def test_chunk_hard_cap_randomized():
    # Found on the live ingest: overlap added to a near-MAX paragraph, and the
    # tail merge, produced 2,390-char chunks. Every chunk must be <= HARD_MAX.
    import random

    HARD_MAX = 2200  # app.chunking.HARD_MAX
    rng = random.Random(7)
    for _ in range(300):
        paras = [("x" * rng.choice([rng.randint(1, 300), rng.randint(1500, 2600)])).replace("x" * 7, "word.. ")
                 for _ in range(rng.randint(1, 30))]
        text = rng.choice(["\n\n", "\n \n\n"]).join(paras)
        spans = chunk(text)
        assert all(0 < e - s <= HARD_MAX for s, e in spans)
        assert spans[0][0] == 0 and spans[-1][1] == len(text)
        assert all(s2 <= e1 or not text[e1:s2].strip() for (_, e1), (s2, _) in zip(spans, spans[1:]))


# ------------------------------------------------------------------ bulk streaming
def test_multistream_bz2_and_bad_rows():
    b = Bulk()
    b.files["bulk-data/x-1.csv.bz2"] = bz2csv(["a", "b"], [[1, 2], [3, 4], [5, 6]], streams=2)
    b.files["bulk-data/y-1.csv.bz2"] = bz2.compress(b"a,b\n1,2\n3\n4,5\n")  # malformed row skipped
    c = BulkClient(BASE, transport=httpx.MockTransport(b))
    assert [r["a"] for r in c.rows("bulk-data/x-1.csv.bz2")] == ["1", "3", "5"]
    assert [r["a"] for r in c.rows("bulk-data/y-1.csv.bz2")] == ["1", "4"]


def test_stalled_download_resumes_from_byte_offset(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    b = Bulk()
    rows = [[i, f"value {i} " * 20] for i in range(3000)]
    b.files["bulk-data/big-1.csv.bz2"] = bz2csv(["a", "b"], rows)
    b.stall_once["bulk-data/big-1.csv.bz2"] = len(b.files["bulk-data/big-1.csv.bz2"]) // 2
    events = []
    c = BulkClient(BASE, audit=lambda *a, **k: events.append((a, k)), transport=httpx.MockTransport(b))
    got = [int(r["a"]) for r in c.rows("bulk-data/big-1.csv.bz2")]
    assert got == list(range(3000))                        # nothing lost, nothing duplicated
    assert any(a[1] == "download_resume" for a, k in events)


def test_only_configured_host():
    c = BulkClient(BASE, transport=httpx.MockTransport(Bulk()))
    c.base = "https://evil.example"
    with pytest.raises(ValueError):
        c.get("x")
    with pytest.raises(ValueError):
        BulkClient("http://bulk.fixture.example", transport=httpx.MockTransport(Bulk())).get("x")


# ------------------------------------------------------------------ pipeline
def _ingest(conn, bulk, logs):
    from app.db import audit
    client = BulkClient(BASE, audit=lambda *a, **k: audit(conn, *a, **k), transport=httpx.MockTransport(bulk))
    return Ingest(conn, client, DevHashEmbedder(), {"ohio": ["ohio", "ohioctapp"], "ca6": ["ca6"]}, log=logs.append)


def test_full_run_idempotent_and_resumable(conn):
    for t in ("chunks", "opinion_texts", "opinions", "ingest_candidates", "ingest_state"):
        conn.execute(f"DELETE FROM {t}")
    logs, bulk = [], Bulk()
    bulk.fail_on.add("harvard_pdf/102.pdf")            # simulate an interruption mid-run
    ing = _ingest(conn, bulk, logs)
    ing.run(10)
    rows = dict(conn.execute("SELECT cluster_id, status FROM ingest_candidates").fetchall())
    assert set(rows) == {101, 102, 103, 104, 105}       # Texas court and no-PDF case excluded
    assert rows[101] == "done" and rows[103] == "done"
    assert rows[102].startswith("failed:download") and rows[104] == "failed:unreadable" and rows[105] == "failed:too_little_text"

    # Resume: the failed download succeeds now; finished work is not redone.
    bulk.fail_on.clear()
    conn.execute("UPDATE ingest_candidates SET status='pending' WHERE status LIKE 'failed:download%'")
    n_req = len(bulk.requests)
    ing.run(10)
    assert rows != dict(conn.execute("SELECT cluster_id, status FROM ingest_candidates").fetchall())
    stage_files = [r for r in bulk.requests[n_req:] if "bulk-data/" in r and ".csv.bz2" in r]
    assert stage_files == []                             # finished stages are skipped
    assert conn.execute("SELECT count(*) FROM opinions").fetchone()[0] == 3

    # Idempotent: a third run changes nothing.
    before = conn.execute("SELECT count(*), sum(text_chars) FROM opinions").fetchone(), conn.execute("SELECT count(*) FROM chunks").fetchone()
    ing.run(10)
    after = conn.execute("SELECT count(*), sum(text_chars) FROM opinions").fetchone(), conn.execute("SELECT count(*) FROM chunks").fetchone()
    assert before == after


def test_ingested_rows_are_complete_and_exact(conn):
    op = conn.execute("SELECT id, case_name, citation, court_id, date_filed, source_url, text_sha256 FROM opinions WHERE cluster_id=101").fetchone()
    assert op[1] == "FIXTURE Freight Co. v. Example Cold Storage" and op[3] == "ohio" and str(op[4]) == "2015-03-02"
    assert op[2] == "2015 Ohio 999; 999 Fixture Ohio St. 3d 1"
    assert op[5] == "https://www.courtlistener.com/opinion/101/fixture-freight/"
    text = conn.execute("SELECT text FROM opinion_texts WHERE opinion_id=%s", (op[0],)).fetchone()[0]
    for s, e, t, emb, model in conn.execute("SELECT char_start, char_end, text, embedding, embed_model FROM chunks WHERE opinion_id=%s ORDER BY position", (op[0],)):
        assert text[s:e] == t and len(emb.to_numpy()) == DIM and model.startswith("dev-hash")
    court = conn.execute("SELECT name, jurisdiction FROM courts WHERE id='ohioctapp'").fetchone()
    assert court == ("Ohio Court of Appeals", "ohio")


def test_reindex_rebuilds_chunks_offline(conn):
    bulk = Bulk()
    conn.execute("UPDATE chunks SET text='tampered', char_end=char_start+8")
    n_req = len(bulk.requests)
    res = _ingest(conn, bulk, []).reindex()
    assert bulk.requests[n_req:] == []                   # no network at all
    assert res["opinions"] == conn.execute("SELECT count(*) FROM opinion_texts").fetchone()[0] == 3
    for oid, text in conn.execute("SELECT opinion_id, text FROM opinion_texts").fetchall():
        spans = [(s, e, t) for s, e, t in conn.execute("SELECT char_start, char_end, text FROM chunks WHERE opinion_id=%s ORDER BY position", (oid,))]
        assert [(s, e) for s, e, _ in spans] == chunk(text) and all(text[s:e] == t for s, e, t in spans)
    assert conn.execute("SELECT detail->>'chunks' FROM audit_log WHERE action='reindex'").fetchone()[0] == str(res["chunks"])


def test_every_download_is_audited_without_payload_text(conn):
    rows = conn.execute("SELECT destination, payload_sha256, detail FROM audit_log WHERE action='download'").fetchall()
    assert rows and all(r[0].startswith(BASE) and len(r[1]) == 64 for r in rows)
    assert all("covenant" not in json.dumps(r[2]) for r in rows)
    assert verify_audit(conn) >= len(rows)


def test_missing_configured_court_fails_loudly(conn):
    logs, bulk = [], Bulk()
    conn.execute("DELETE FROM ingest_state")
    ing = _ingest(conn, bulk, logs)
    ing.config = {"x": ["nonexistent_court"]}
    ing.court_juris = {"nonexistent_court": "x"}
    with pytest.raises(RuntimeError):
        ing.courts()
