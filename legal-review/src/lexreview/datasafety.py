"""Development data rule: refuse anything that is not approved synthetic data.

This build must only ever read synthetic or public test documents. Before
ingestion reads a single byte of a file, the file must:

1. resolve (after following symlinks) to a path inside
   LEXREVIEW_APPROVED_DATA_DIR,
2. be listed in that directory's MANIFEST.json, and
3. match the SHA-256 recorded in the manifest.

The manifest must also carry `"synthetic": true` and a valid HMAC signature
made with the manifest key (a secret reference, never hardcoded). A file
dropped into the approved directory by copy-paste is therefore still
refused, because it is not in the signed manifest.

There is deliberately no bypass flag. Enabling real data requires a code
change plus the reviews listed in PENTEST_AND_COUNSEL_REVIEW.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from .config import Settings
from .errors import DataSafetyError
from .secrets import resolve_hex_key

MANIFEST_NAME = "MANIFEST.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sign_manifest(entries: dict[str, str], key: bytes, description: str) -> dict:
    body = {"synthetic": True, "description": description, "files": dict(sorted(entries.items()))}
    return {**body, "signature": hmac.new(key, _canon(body), hashlib.sha256).hexdigest()}


class ApprovedDataGuard:
    def __init__(self, settings: Settings):
        if settings.production:
            # A production mode for real data does not exist in this build.
            raise DataSafetyError("production_data_mode_not_available")
        if settings.approved_data_dir is None or settings.manifest_key_ref is None:
            raise DataSafetyError("approved_dir_not_configured")
        self.root = settings.approved_data_dir
        if not self.root.is_dir():
            raise DataSafetyError("approved_dir_missing")
        key = resolve_hex_key(settings.manifest_key_ref)
        mpath = self.root / MANIFEST_NAME
        if not mpath.is_file():
            raise DataSafetyError("manifest_missing")
        try:
            manifest = json.loads(mpath.read_text())
            sig = manifest.pop("signature")
        except (ValueError, KeyError) as exc:
            raise DataSafetyError("manifest_malformed") from exc
        if not hmac.compare_digest(sig, hmac.new(key, _canon(manifest), hashlib.sha256).hexdigest()):
            raise DataSafetyError("manifest_signature_invalid")
        if manifest.get("synthetic") is not True:
            raise DataSafetyError("manifest_not_synthetic")
        self._files: dict[str, str] = manifest["files"]

    def check(self, path: Path) -> str:
        """Return the approved relative path, or raise DataSafetyError."""
        real = Path(path).resolve(strict=True)
        try:
            rel = real.relative_to(self.root)
        except ValueError as exc:
            raise DataSafetyError("path_outside_approved_dir") from exc
        rel_s = rel.as_posix()
        expected = self._files.get(rel_s)
        if expected is None:
            raise DataSafetyError("file_not_in_manifest")
        if sha256_file(real) != expected:
            raise DataSafetyError("file_hash_mismatch")
        return rel_s

    def read(self, path: Path, max_bytes: int) -> tuple[str, bytes | None, str]:
        """Check and read in one pass, so the bytes that get parsed are the
        exact bytes whose hash was verified (no check-then-reopen race).

        Returns (relative_path, data, sha256). `data` is None when the file
        exceeds max_bytes; the hash is still verified by streaming."""
        rel = self.check(path)
        real = Path(path).resolve(strict=True)
        if real.stat().st_size > max_bytes:
            return rel, None, self._files[rel]
        data = real.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != self._files[rel]:
            raise DataSafetyError("file_hash_mismatch")
        return rel, data, digest

    def approved_files(self) -> list[Path]:
        return [self.root / rel for rel in sorted(self._files)]
