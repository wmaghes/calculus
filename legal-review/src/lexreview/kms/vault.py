"""HashiCorp Vault Transit KMS adapter.

The KEK lives in Vault and never leaves it: Vault encrypts/decrypts the DEK.
Keys are created with `deletion_allowed` so a case KEK can be destroyed
(crypto-shred). Vault context (derived keys) binds wrapped DEKs to a case.

STATUS: unit-tested against a mocked HTTP transport only. It has NOT been
run against a live Vault. It needs an integration test in the target
environment before use (see SECURITY.md, open items).
"""

from __future__ import annotations

import base64
import re

import httpx

from ..errors import ConfigError, CryptoError, KeyDestroyed
from ..secrets import resolve_secret
from . import KMS

_KEY_ID = re.compile(r"^[a-z0-9_\-]{1,64}$")


class VaultTransitKMS(KMS):
    name = "vault"

    def __init__(self, addr: str, token_ref: str, mount: str = "transit", transport: httpx.BaseTransport | None = None):
        if not addr.startswith("https://"):
            raise ConfigError("vault_addr_must_be_https")
        self._token_ref = token_ref
        self._mount = mount
        self._client = httpx.Client(base_url=addr.rstrip("/") + "/v1", transport=transport, timeout=10.0)

    def _headers(self) -> dict:
        return {"X-Vault-Token": resolve_secret(self._token_ref).decode()}

    @staticmethod
    def _check(key_id: str) -> str:
        if not _KEY_ID.match(key_id):
            raise ConfigError("kms_key_id_invalid")
        return key_id

    def _post(self, path: str, body: dict, missing_is_destroyed: bool = False) -> dict:
        r = self._client.post(f"/{self._mount}/{path}", json=body, headers=self._headers())
        # Vault answers 400 "encryption key not found" once a key is deleted.
        if missing_is_destroyed and r.status_code in (400, 404):
            raise KeyDestroyed()
        if r.status_code >= 400:
            raise CryptoError("vault_request_failed")
        return r.json() if r.content else {}

    def create_key(self, key_id: str) -> None:
        k = self._check(key_id)
        self._post(f"keys/{k}", {"type": "aes256-gcm96", "derived": True, "exportable": False})
        self._post(f"keys/{k}/config", {"deletion_allowed": True})

    def wrap(self, key_id: str, plaintext: bytes, context: bytes) -> bytes:
        k = self._check(key_id)
        r = self._post(f"encrypt/{k}", {
            "plaintext": base64.b64encode(plaintext).decode(),
            "context": base64.b64encode(context).decode(),
        }, missing_is_destroyed=True)
        return r["data"]["ciphertext"].encode()

    def unwrap(self, key_id: str, wrapped: bytes, context: bytes) -> bytes:
        k = self._check(key_id)
        r = self._post(f"decrypt/{k}", {
            "ciphertext": wrapped.decode(),
            "context": base64.b64encode(context).decode(),
        }, missing_is_destroyed=True)
        return base64.b64decode(r["data"]["plaintext"])

    def destroy_key(self, key_id: str) -> None:
        k = self._check(key_id)
        r = self._client.delete(f"/{self._mount}/keys/{k}", headers=self._headers())
        if r.status_code >= 400 and r.status_code != 404:
            raise CryptoError("vault_request_failed")

    def key_exists(self, key_id: str) -> bool:
        k = self._check(key_id)
        r = self._client.get(f"/{self._mount}/keys/{k}", headers=self._headers())
        return r.status_code == 200
