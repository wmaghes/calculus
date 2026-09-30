"""SQLCipher connection helper (AES-256, page-level encryption).

Every database this application writes (the control plane and each case
store) is a SQLCipher file keyed with a raw 256-bit key. Temp tables and
sort spills are forced into memory so no plaintext temp files are written.
"""

from __future__ import annotations

from pathlib import Path

import sqlcipher3

from .errors import CryptoError


def connect(path: Path, raw_key: bytes) -> sqlcipher3.Connection:
    if len(raw_key) != 32:
        raise CryptoError("bad_key_length")
    conn = sqlcipher3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute(f"PRAGMA key = \"x'{raw_key.hex()}'\"")
    conn.execute("PRAGMA cipher_memory_security = ON")
    try:
        # Fails here (not at PRAGMA key) if the key is wrong or data is garbage.
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlcipher3.DatabaseError as exc:
        conn.close()
        raise CryptoError("db_key_invalid_or_corrupt") from exc
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA secure_delete = ON")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = DELETE")
    return conn
