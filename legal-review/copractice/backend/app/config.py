"""Settings from the environment (.env). No secrets in code."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    embed_backend: str
    embed_model_path: str | None
    bulk_base: str
    sample_size: int


def load() -> Settings:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    backend = os.environ.get("EMBED_BACKEND", "sentence-transformers")
    if backend not in ("sentence-transformers", "dev-hash"):
        raise RuntimeError("EMBED_BACKEND must be sentence-transformers or dev-hash")
    return Settings(
        database_url=url,
        embed_backend=backend,
        embed_model_path=os.environ.get("EMBED_MODEL_PATH"),
        bulk_base=os.environ.get("COURTLISTENER_BULK_BASE",
                                 "https://com-courtlistener-storage.s3-us-west-2.amazonaws.com").rstrip("/"),
        sample_size=int(os.environ.get("INGEST_SAMPLE_SIZE", "1000")),
    )
