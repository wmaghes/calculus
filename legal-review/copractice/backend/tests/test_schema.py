import uuid

import numpy as np
import psycopg
import pytest

from app.db import audit, migrate, verify_audit


def test_tables_and_indexes(conn):
    tables = {r[0] for r in conn.execute("select tablename from pg_tables where schemaname='public'")}
    assert {"opinions", "chunks", "matters", "audit_log", "courts", "opinion_texts", "ingest_state", "ingest_candidates"} <= tables
    idx = {r[0]: r[1] for r in conn.execute("select indexname, indexdef from pg_indexes where tablename='chunks'")}
    assert "USING gin (tsv)" in idx["chunks_tsv_gin"]
    assert "USING hnsw (embedding vector_cosine_ops)" in idx["chunks_embedding_hnsw"]


def test_migrate_is_idempotent(conn):
    migrate(conn)
    migrate(conn)


def test_generated_tsvector_and_vector_roundtrip(conn):
    conn.execute("insert into courts values ('t_ct','Test Court','test') on conflict do nothing")
    oid = conn.execute("insert into opinions (source, cluster_id, case_name, court_id, source_url, text_sha256, text_chars) "
                       "values ('test', 1, 'A v. B', 't_ct', 'https://example.invalid/1', 'x', 10) returning id").fetchone()[0]
    vec = np.arange(384, dtype=np.float32) / 384
    conn.execute("insert into chunks (opinion_id, position, char_start, char_end, text, embedding, embed_model) values (%s,0,0,10,%s,%s,'t')",
                 (oid, "The covenant not to compete was unenforceable.", vec))
    tsv, emb = conn.execute("select tsv::text, embedding from chunks where opinion_id=%s", (oid,)).fetchone()
    assert "'compet'" in tsv and np.allclose(np.asarray(emb.to_numpy() if hasattr(emb, "to_numpy") else emb), vec)
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute("insert into chunks (opinion_id, position, char_start, char_end, text) values (%s,0,0,5,'dup')", (oid,))
    conn.execute("delete from opinions where id=%s", (oid,))  # cascade removes chunks
    assert conn.execute("select count(*) from chunks where opinion_id=%s", (oid,)).fetchone()[0] == 0


def test_audit_log_is_append_only_and_chained(conn):
    audit(conn, "tester", "search", query_digest="abc")
    audit(conn, "ingest", "download", outbound=True, destination="https://example.invalid/x", payload=b"GET /x")
    n = verify_audit(conn)
    assert n >= 2
    row = conn.execute("select payload_sha256, payload_bytes, detail from audit_log where action='download'").fetchone()
    assert len(row[0]) == 64 and row[1] == 6 and "GET" not in str(row[2])
    for stmt in ("update audit_log set actor='x'", "delete from audit_log", "truncate audit_log"):
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(stmt)


def test_matters_hold_no_facts(conn):
    cols = {r[0] for r in conn.execute("select column_name from information_schema.columns where table_name='matters'")}
    assert cols == {"id", "title", "lexreview_case_id", "created_by", "created_at"}
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into matters (id, title, created_by) values (%s, %s, 'u')", (uuid.uuid4(), "x" * 201))
