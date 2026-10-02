"""DEVELOPMENT-ONLY file-backed KMS.

NOT FOR PRODUCTION. Refuses to start when LEXREVIEW_ENV=production.

KEKs are random 32-byte keys, each stored sealed under a master key that is
resolved from a secret reference (never hardcoded). Destroying a key
overwrites and unlinks its file. On journaling or copy-on-write filesystems,
and on SSDs, overwriting does not guarantee the old bytes are gone; that is
one reason this backend is dev-only. A real HSM or Vault Transit key
deletion is the production crypto-shred primitive.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .. import crypto
from ..config import Settings
from ..errors import ConfigError, KeyDestroyed
from ..secrets import resolve_hex_key
from . import KMS

_KEY_ID = re.compile(r"^[a-z0-9_\-]{1,64}$")


class DevFileKMS(KMS):
    name = "devfile"

    def __init__(self, directory: Path, master_ref: str, settings: Settings):
        if settings.production:
            raise ConfigError("devfile_kms_forbidden_in_production")
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._master = resolve_hex_key(master_ref)

    def _path(self, key_id: str) -> Path:
        if not _KEY_ID.match(key_id):
            raise ConfigError("kms_key_id_invalid")
        return self._dir / f"{key_id}.kek"

    def create_key(self, key_id: str) -> None:
        p = self._path(key_id)
        if p.exists():
            raise ConfigError("kms_key_exists")
        sealed = crypto.seal(self._master, crypto.new_key(), aad=b"kek:" + key_id.encode())
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(sealed)

    def _kek(self, key_id: str) -> bytes:
        p = self._path(key_id)
        if not p.exists():
            raise KeyDestroyed()
        return crypto.open_sealed(self._master, p.read_bytes(), aad=b"kek:" + key_id.encode())

    def wrap(self, key_id: str, plaintext: bytes, context: bytes) -> bytes:
        return crypto.seal(self._kek(key_id), plaintext, aad=b"wrap:" + context)

    def unwrap(self, key_id: str, wrapped: bytes, context: bytes) -> bytes:
        return crypto.open_sealed(self._kek(key_id), wrapped, aad=b"wrap:" + context)

    def destroy_key(self, key_id: str) -> None:
        p = self._path(key_id)
        if not p.exists():
            return
        size = p.stat().st_size
        with open(p, "r+b") as fh:
            fh.write(os.urandom(size))
            fh.flush()
            os.fsync(fh.fileno())
        p.unlink()

    def key_exists(self, key_id: str) -> bool:
        return self._path(key_id).exists()
