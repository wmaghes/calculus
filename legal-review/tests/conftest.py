"""Shared fixtures. Everything runs on the generated SYNTHETIC corpus only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pyotp
import pytest

from lexreview.app import App
from lexreview.authz import Perm, Role
from lexreview.config import load_settings

ROOT = Path(__file__).resolve().parents[1]


def _hex() -> str:
    return os.urandom(32).hex()


@pytest.fixture(scope="session")
def corpus(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("synthetic")
    os.environ["LR_TEST_MANIFEST_KEY"] = _hex()
    env = {**os.environ, "LEXREVIEW_MANIFEST_KEY_REF": "env:LR_TEST_MANIFEST_KEY"}
    subprocess.run([sys.executable, str(ROOT / "scripts/make_synthetic_corpus.py"), "--out", str(out)],
                   check=True, env=env, capture_output=True)
    return out


@pytest.fixture(scope="session")
def labels(corpus) -> dict:
    return json.loads((corpus / "LABELS.json").read_text())


def set_env(mp, data_root: Path, corpus: Path, **extra) -> None:
    mp.setenv("LEXREVIEW_ENV", "dev")
    mp.setenv("LEXREVIEW_DATA_ROOT", str(data_root))
    mp.setenv("LEXREVIEW_APPROVED_DATA_DIR", str(corpus))
    mp.setenv("LEXREVIEW_MANIFEST_KEY_REF", "env:LR_TEST_MANIFEST_KEY")
    mp.setenv("LEXREVIEW_KMS", "devfile")
    mp.setenv("LR_TEST_KMS_MASTER", os.environ.get("LR_TEST_KMS_MASTER") or _hex())
    mp.setenv("LEXREVIEW_DEV_KMS_MASTER_REF", "env:LR_TEST_KMS_MASTER")
    for k, v in extra.items():
        mp.setenv(k, v)


class World:
    """An initialized app with users and two cases."""

    def __init__(self, app: App, corpus: Path):
        self.app, self.corpus = app, corpus
        self.admin_uid, self.admin_totp = app.bootstrap_admin("sysadmin", "admin-password-123")
        self.admin_token = app.login("sysadmin", "admin-password-123", pyotp.TOTP(self.admin_totp).now())
        self.admin = app.principal(self.admin_token)
        self.users: dict[str, dict] = {}
        for name in ("alice", "bob", "carol", "dave"):
            uid, totp = app.create_user(self.admin, name, f"{name}-password-123")
            tok = app.login(name, f"{name}-password-123", pyotp.TOTP(totp).now())
            self.users[name] = {"uid": uid, "totp": totp, "token": tok, "p": app.principal(tok)}
        self.case_a = app.create_case(self.admin, "Harbor Point v. Meridian (synthetic)")
        self.case_b = app.create_case(self.admin, "Unrelated synthetic matter")
        app.add_member(self.admin, self.case_a, self.users["alice"]["uid"], Role.CASE_ADMIN)
        app.add_member(self.admin, self.case_a, self.users["bob"]["uid"], Role.REVIEWER)
        app.add_member(self.admin, self.case_a, self.users["dave"]["uid"], Role.ATTORNEY)
        app.add_member(self.admin, self.case_b, self.users["carol"]["uid"], Role.CASE_ADMIN)

    def p(self, name):
        return self.users[name]["p"]

    def ctx(self, name, case, perm=Perm.VIEW):
        return self.app.authorize(self.p(name), case, perm)


@pytest.fixture
def app(tmp_path, corpus, monkeypatch):
    set_env(monkeypatch, tmp_path / "data", corpus)
    a = App.initialize(load_settings())
    yield a
    a.close()


@pytest.fixture
def world(app, corpus):
    return World(app, corpus)


@pytest.fixture(scope="session")
def ingested(tmp_path_factory, corpus):
    """Session-wide world with the full corpus ingested into case A and the
    contracts folder into case B. Read-only tests share it."""
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("data")
    set_env(mp, root, corpus)
    a = App.initialize(load_settings())
    w = World(a, corpus)
    w.ingest_summary = a.ingest(w.ctx("alice", w.case_a, Perm.INGEST), corpus / "docs")
    a.ingest(w.ctx("carol", w.case_b, Perm.INGEST), corpus / "docs" / "contracts")
    store = a.store(w.ctx("alice", w.case_a))
    docs = {d["source_name"]: d for d in store.list_documents(w.ctx("alice", w.case_a))}
    w.docs = docs
    # Mark the amendment attorneys'-eyes-only in case A.
    a.set_restriction(w.ctx("alice", w.case_a, Perm.MANAGE), docs["docs/contracts/amendment_1.docx"]["doc_id"], "aeo")
    w.data_root = root
    yield w
    a.close()
    mp.undo()
