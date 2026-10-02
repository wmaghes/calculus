"""Database access: connection, migrations, and the audit log."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

SCHEMA = Path(__file__).with_name("schema.sql")
GENESIS = "0" * 64


def connect(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def migrate(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text())


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def audit(conn: psycopg.Connection, actor: str, action: str, *, outbound: bool = False,
          destination: str | None = None, payload: bytes | None = None, **detail) -> None:
    """Append one hash-chained record. Payloads are recorded as SHA-256 and
    size only; text never enters the log. Serialized with an advisory lock so
    the chain has no forks."""
    ph = hashlib.sha256(payload).hexdigest() if payload is not None else None
    pb = len(payload) if payload is not None else None
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(784512)")
        row = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev = row[0] if row else GENESIS
        body = {"actor": actor, "action": action, "outbound": outbound, "destination": destination,
                "payload_sha256": ph, "payload_bytes": pb, "detail": detail}
        h = hashlib.sha256((prev + _canon(body)).encode()).hexdigest()
        conn.execute(
            "INSERT INTO audit_log (actor, action, outbound, destination, payload_sha256, payload_bytes, detail, prev_hash, hash) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (actor, action, outbound, destination, ph, pb, json.dumps(detail, default=str), prev, h))


def verify_audit(conn: psycopg.Connection) -> int:
    prev, n = GENESIS, 0
    for actor, action, outbound, dest, ph, pb, detail, p, h in conn.execute(
            "SELECT actor, action, outbound, destination, payload_sha256, payload_bytes, detail, prev_hash, hash "
            "FROM audit_log ORDER BY id"):
        body = {"actor": actor, "action": action, "outbound": outbound, "destination": dest,
                "payload_sha256": ph, "payload_bytes": pb, "detail": detail}
        if p != prev or hashlib.sha256((prev + _canon(body)).encode()).hexdigest() != h:
            raise ValueError(f"audit chain broken at record {n + 1}")
        prev, n = h, n + 1
    return n
