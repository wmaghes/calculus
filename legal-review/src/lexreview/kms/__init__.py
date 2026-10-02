"""Key management interface.

Backends implement KMS. The application only ever asks the KMS to create,
wrap with, unwrap with, and destroy a named key-encryption key (KEK). For
Vault Transit and HSM backends the KEK never leaves the KMS.

Destroying a case KEK is the crypto-shredding primitive: once it is gone,
the wrapped DEK on disk (and in every backup) can no longer be unwrapped.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings
from ..errors import ConfigError


class KMS(ABC):
    name = "abstract"

    @abstractmethod
    def create_key(self, key_id: str) -> None: ...

    @abstractmethod
    def wrap(self, key_id: str, plaintext: bytes, context: bytes) -> bytes: ...

    @abstractmethod
    def unwrap(self, key_id: str, wrapped: bytes, context: bytes) -> bytes: ...

    @abstractmethod
    def destroy_key(self, key_id: str) -> None: ...

    @abstractmethod
    def key_exists(self, key_id: str) -> bool: ...


def kms_from_settings(settings: Settings) -> KMS:
    if settings.kms_backend == "devfile":
        from .devfile import DevFileKMS

        if not settings.dev_kms_master_ref:
            raise ConfigError("dev_kms_master_ref_unset")
        return DevFileKMS(settings.data_root / "devkms", settings.dev_kms_master_ref, settings)
    if settings.kms_backend == "vault":
        from .vault import VaultTransitKMS

        if not (settings.vault_addr and settings.vault_token_ref):
            raise ConfigError("vault_config_incomplete")
        return VaultTransitKMS(settings.vault_addr, settings.vault_token_ref)
    raise ConfigError("kms_backend_invalid")
