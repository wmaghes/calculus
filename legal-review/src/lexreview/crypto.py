"""Symmetric crypto primitives (AES-256-GCM, HKDF-SHA256).

Envelope scheme per case:
    KEK  (lives in the KMS/HSM, never leaves it for Vault/HSM backends)
     └─ wraps DEK (32 random bytes, stored only in wrapped form on disk)
          ├─ HKDF(info="sqlcipher")  -> raw key for the case SQLCipher DB
          ├─ HKDF(info="blob")       -> AES-256-GCM key for blobs
          └─ HKDF(info="vector")     -> AES-256-GCM key for vector index files

Every ciphertext is bound to its purpose and location with GCM associated
data (AAD), so a blob copied into another case or another slot fails to
decrypt.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import CryptoError

KEY_LEN = 32
NONCE_LEN = 12
_MAGIC = b"LXR1"


def new_key() -> bytes:
    return os.urandom(KEY_LEN)


def derive(key: bytes, info: str, length: int = KEY_LEN) -> bytes:
    if len(key) != KEY_LEN:
        raise CryptoError("bad_key_length")
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=info.encode()).derive(key)


def seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE_LEN)
    return _MAGIC + nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def open_sealed(key: bytes, blob: bytes, aad: bytes) -> bytes:
    if len(blob) < len(_MAGIC) + NONCE_LEN + 16 or not blob.startswith(_MAGIC):
        raise CryptoError("ciphertext_malformed")
    nonce = blob[len(_MAGIC): len(_MAGIC) + NONCE_LEN]
    try:
        return AESGCM(key).decrypt(nonce, blob[len(_MAGIC) + NONCE_LEN:], aad)
    except InvalidTag as exc:
        raise CryptoError("decrypt_failed") from exc
