"""AES-256-GCM envelope encryption and the KMS adapters."""

import base64
import json

import httpx
import pytest

from lexreview import crypto
from lexreview.config import load_settings
from lexreview.errors import ConfigError, CryptoError, KeyDestroyed
from lexreview.kms.devfile import DevFileKMS
from lexreview.kms.vault import VaultTransitKMS


def test_seal_roundtrip_and_aad_binding():
    k = crypto.new_key()
    blob = crypto.seal(k, b"privileged text", b"case1:doc1")
    assert b"privileged" not in blob
    assert crypto.open_sealed(k, blob, b"case1:doc1") == b"privileged text"
    with pytest.raises(CryptoError):
        crypto.open_sealed(k, blob, b"case2:doc1")  # moved to another case
    with pytest.raises(CryptoError):
        crypto.open_sealed(crypto.new_key(), blob, b"case1:doc1")
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(CryptoError):
        crypto.open_sealed(k, tampered, b"case1:doc1")


def test_derived_keys_differ():
    k = crypto.new_key()
    assert len({crypto.derive(k, "sqlcipher"), crypto.derive(k, "blob"), crypto.derive(k, "vector")}) == 3


def test_devfile_kms_wrap_destroy(app):
    kms = app.kms
    kms.create_key("case-test")
    w = kms.wrap("case-test", b"k" * 32, b"ctx")
    assert kms.unwrap("case-test", w, b"ctx") == b"k" * 32
    with pytest.raises(CryptoError):
        kms.unwrap("case-test", w, b"other-ctx")
    kms.destroy_key("case-test")
    with pytest.raises(KeyDestroyed):
        kms.unwrap("case-test", w, b"ctx")


def test_devfile_kms_refused_in_production(app, monkeypatch, tmp_path):
    monkeypatch.setenv("LEXREVIEW_ENV", "production")
    with pytest.raises(ConfigError):
        DevFileKMS(tmp_path, "env:LR_TEST_KMS_MASTER", load_settings())


def test_secret_refs_only(monkeypatch, tmp_path):
    from lexreview.secrets import resolve_secret

    with pytest.raises(ConfigError):
        resolve_secret("deadbeef")  # a literal is not a reference
    f = tmp_path / "s"
    f.write_text("x")
    f.chmod(0o644)
    with pytest.raises(ConfigError):
        resolve_secret(f"file:{f}")  # world-readable secret file refused
    f.chmod(0o600)
    assert resolve_secret(f"file:{f}") == b"x"


class FakeVault:
    """Minimal mock of Vault Transit semantics, for adapter unit tests only."""

    def __init__(self):
        self.keys = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Vault-Token"] == "t0ken"
        parts = request.url.path.split("/")  # /v1/transit/<op>/<key>[/config]
        op, key = parts[3], parts[4]
        if request.method == "DELETE":
            self.keys.pop(key, None)
            return httpx.Response(204)
        if request.method == "GET":
            return httpx.Response(200 if key in self.keys else 404, json={})
        body = json.loads(request.content or b"{}")
        if op == "keys":
            self.keys.setdefault(key, crypto.new_key())
            return httpx.Response(204)
        if key not in self.keys:
            return httpx.Response(400, json={"errors": ["encryption key not found"]})
        k, ctx = self.keys[key], base64.b64decode(body["context"])
        if op == "encrypt":
            ct = crypto.seal(k, base64.b64decode(body["plaintext"]), ctx)
            return httpx.Response(200, json={"data": {"ciphertext": "vault:v1:" + base64.b64encode(ct).decode()}})
        if op == "decrypt":
            pt = crypto.open_sealed(k, base64.b64decode(body["ciphertext"][9:]), ctx)
            return httpx.Response(200, json={"data": {"plaintext": base64.b64encode(pt).decode()}})
        return httpx.Response(404)


def test_vault_adapter_against_mock(monkeypatch):
    monkeypatch.setenv("VT", "t0ken")
    fv = FakeVault()
    kms = VaultTransitKMS("https://vault.internal.example", "env:VT", transport=httpx.MockTransport(fv.handler))
    kms.create_key("case-c1")
    assert kms.key_exists("case-c1")
    w = kms.wrap("case-c1", b"d" * 32, b"c1")
    assert kms.unwrap("case-c1", w, b"c1") == b"d" * 32
    kms.destroy_key("case-c1")
    with pytest.raises(KeyDestroyed):
        kms.unwrap("case-c1", w, b"c1")


def test_vault_requires_https():
    with pytest.raises(ConfigError):
        VaultTransitKMS("http://vault.internal.example", "env:VT")
