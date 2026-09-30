import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_layout_exists():
    for p in ("backend/app", "frontend", "ingest", "docker-compose.yml", "README.md", "CLAUDE.md", ".env.example"):
        assert (ROOT / p).exists(), p


def test_privacy_rule_recorded():
    text = (ROOT / "CLAUDE.md").read_text()
    assert "Public case law is the only thing indexed" in text and "anonymized issue summary" in text


def test_no_secrets_committed():
    env = (ROOT / ".env.example").read_text()
    assert "sk-" not in env and "PASSWORD=" not in env.replace("POSTGRES_PASSWORD", "")
    assert ".env" in (ROOT / ".gitignore").read_text().split()


def test_settings_require_database_url(monkeypatch):
    from app.config import load

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load()
    monkeypatch.setenv("DATABASE_URL", "postgresql://x@localhost/y")
    monkeypatch.setenv("EMBED_BACKEND", "remote-api")
    with pytest.raises(RuntimeError):
        load()


def test_compose_binds_loopback_only():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert '"127.0.0.1:5432:5432"' in compose and '"127.0.0.1:8000:8000"' in compose
    _ = os
