"""Development data rule: only signed, synthetic, approved files are ingested."""

import json
import os
import shutil

import pytest

from lexreview.authz import Perm
from lexreview.config import load_settings
from lexreview.datasafety import ApprovedDataGuard
from lexreview.errors import DataSafetyError


def test_approved_file_passes(app, corpus):
    guard = ApprovedDataGuard(app.settings)
    assert guard.check(corpus / "docs/emails/e01.eml") == "docs/emails/e01.eml"


def test_file_outside_approved_dir_refused(app, tmp_path):
    outside = tmp_path / "real_client_file.pdf"
    outside.write_bytes(b"%PDF-1.4 not approved")
    with pytest.raises(DataSafetyError) as e:
        ApprovedDataGuard(app.settings).check(outside)
    assert e.value.code == "path_outside_approved_dir"


def test_symlink_escape_refused(app, corpus, tmp_path):
    target = tmp_path / "secret.txt"
    target.write_text("not synthetic")
    link = corpus / "docs" / "sneaky_link.txt"
    os.symlink(target, link)
    try:
        with pytest.raises(DataSafetyError):
            ApprovedDataGuard(app.settings).check(link)
    finally:
        link.unlink()


def test_unlisted_file_inside_approved_dir_refused(world, corpus):
    stray = corpus / "docs" / "dropped_in.txt"
    stray.write_text("someone copied a real document here")
    try:
        ctx = world.ctx("alice", world.case_a, Perm.INGEST)
        with pytest.raises(DataSafetyError) as e:
            world.app.ingest(ctx, corpus / "docs")
        assert e.value.code == "file_not_in_manifest"
        # Nothing at all was ingested: the pre-check runs before any parsing.
        assert world.app.store(ctx).list_documents(world.ctx("alice", world.case_a)) == []
    finally:
        stray.unlink()


def test_modified_file_refused(app, corpus, tmp_path):
    victim = corpus / "docs/emails/e12.eml"
    original = victim.read_bytes()
    victim.write_bytes(original + b"tampered")
    try:
        with pytest.raises(DataSafetyError) as e:
            ApprovedDataGuard(app.settings).check(victim)
        assert e.value.code == "file_hash_mismatch"
    finally:
        victim.write_bytes(original)


def test_tampered_manifest_refused(app, corpus, tmp_path, monkeypatch):
    fake = tmp_path / "fake_corpus"
    shutil.copytree(corpus, fake)
    m = json.loads((fake / "MANIFEST.json").read_text())
    m["files"]["docs/real.pdf"] = "0" * 64
    (fake / "MANIFEST.json").write_text(json.dumps(m))
    monkeypatch.setenv("LEXREVIEW_APPROVED_DATA_DIR", str(fake))
    with pytest.raises(DataSafetyError) as e:
        ApprovedDataGuard(load_settings())
    assert e.value.code == "manifest_signature_invalid"


def test_manifest_signed_with_other_key_refused(app, monkeypatch):
    monkeypatch.setenv("LR_TEST_MANIFEST_KEY", os.urandom(32).hex())
    with pytest.raises(DataSafetyError):
        ApprovedDataGuard(load_settings())


def test_no_production_bypass(app, monkeypatch):
    monkeypatch.setenv("LEXREVIEW_ENV", "production")
    with pytest.raises(DataSafetyError) as e:
        ApprovedDataGuard(load_settings())
    assert e.value.code == "production_data_mode_not_available"
