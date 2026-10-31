"""Content-addressed cache for paid / slow API calls.

Every request is hashed (endpoint + payload). If the hash exists in .cache/
the stored bytes are returned and no API call (and no charge) happens.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from .config import CACHE


def key_for(namespace: str, payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return f"{namespace}-{hashlib.sha256(blob).hexdigest()[:24]}"


def cached_bytes(namespace: str, payload: dict, ext: str, produce: Callable[[], bytes]) -> tuple[Path, bool]:
    """Return (path, was_cached)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{key_for(namespace, payload)}.{ext}"
    if path.exists() and path.stat().st_size > 0:
        return path, True
    data = produce()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    (CACHE / f"{path.stem}.request.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path, False
