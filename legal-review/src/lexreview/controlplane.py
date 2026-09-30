"""Control-plane database: users, sessions, cases, memberships, grants.

A SQLCipher database keyed by its own DEK (wrapped by the "control" KEK).
It holds no document content.
"""

from __future__ import annotations

from pathlib import Path

from . import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL,
    totp_secret TEXT,
    last_totp_step INTEGER NOT NULL DEFAULT 0,
    is_sysadmin INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    created_at REAL NOT NULL,
    last_seen REAL NOT NULL,
    expires_at REAL NOT NULL,
    mfa_verified INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'destroyed')),
    created_at REAL NOT NULL,
    destroyed_at REAL
);
CREATE TABLE IF NOT EXISTS memberships (
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    role TEXT NOT NULL,
    PRIMARY KEY (case_id, user_id)
);
CREATE TABLE IF NOT EXISTS grants (
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    label TEXT NOT NULL,
    PRIMARY KEY (case_id, user_id, label)
);
"""


def open_control(path: Path, raw_key: bytes):
    conn = db.connect(path, raw_key)
    conn.executescript(SCHEMA)
    return conn
