"""Runtime configuration, read from environment variables only.

Nothing here is a secret. Secrets are given as references (see secrets.py).

    LEXREVIEW_ENV                   "dev" (default) or "production"
    LEXREVIEW_DATA_ROOT             where per-case stores, control DB and audit log live
    LEXREVIEW_APPROVED_DATA_DIR     the only directory ingestion may read (dev build)
    LEXREVIEW_MANIFEST_KEY_REF      secret ref for the synthetic-corpus manifest HMAC key
    LEXREVIEW_KMS                   "devfile" or "vault"
    LEXREVIEW_DEV_KMS_MASTER_REF    secret ref (devfile KMS only)
    LEXREVIEW_VAULT_ADDR            https URL of Vault (vault KMS only)
    LEXREVIEW_VAULT_TOKEN_REF       secret ref for the Vault token
    LEXREVIEW_EGRESS_ALLOW          comma-separated extra host allowlist
    LEXREVIEW_LOOPBACK_ALLOW        comma-separated loopback ports the app may connect to
    LEXREVIEW_REQUIRE_MFA           "1" (default) or "0" (dev only)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError


@dataclass(frozen=True)
class Settings:
    env: str
    data_root: Path
    approved_data_dir: Path | None
    manifest_key_ref: str | None
    kms_backend: str
    dev_kms_master_ref: str | None
    vault_addr: str | None
    vault_token_ref: str | None
    egress_allow: tuple[str, ...] = field(default_factory=tuple)
    loopback_allow: tuple[int, ...] = field(default_factory=tuple)
    require_mfa: bool = True

    # Ingestion limits. Anything over a limit is recorded in coverage as
    # too_large, never silently dropped.
    max_file_bytes: int = 512 * 1024 * 1024
    max_pages: int = 5000
    max_zip_uncompressed: int = 1024 * 1024 * 1024
    max_zip_ratio: int = 200
    parse_timeout_s: int = 600
    parse_mem_bytes: int = 3 * 1024 * 1024 * 1024
    ocr_min_chars: int = 25
    ocr_low_conf: float = 60.0

    @property
    def production(self) -> bool:
        return self.env == "production"


def load_settings() -> Settings:
    env = os.environ.get("LEXREVIEW_ENV", "dev")
    if env not in ("dev", "production"):
        raise ConfigError("env_invalid")
    root = os.environ.get("LEXREVIEW_DATA_ROOT")
    if not root:
        raise ConfigError("data_root_unset")
    approved = os.environ.get("LEXREVIEW_APPROVED_DATA_DIR")
    kms = os.environ.get("LEXREVIEW_KMS", "devfile")
    if kms not in ("devfile", "vault"):
        raise ConfigError("kms_backend_invalid")
    allow = tuple(
        h.strip().lower()
        for h in os.environ.get("LEXREVIEW_EGRESS_ALLOW", "").split(",")
        if h.strip()
    )
    try:
        loopback = tuple(int(p) for p in os.environ.get("LEXREVIEW_LOOPBACK_ALLOW", "").split(",") if p.strip())
    except ValueError as exc:
        raise ConfigError("loopback_allow_invalid") from exc
    require_mfa = os.environ.get("LEXREVIEW_REQUIRE_MFA", "1") != "0"
    if env == "production" and not require_mfa:
        raise ConfigError("mfa_required_in_production")
    s = Settings(
        env=env,
        data_root=Path(root).resolve(),
        approved_data_dir=Path(approved).resolve() if approved else None,
        manifest_key_ref=os.environ.get("LEXREVIEW_MANIFEST_KEY_REF"),
        kms_backend=kms,
        dev_kms_master_ref=os.environ.get("LEXREVIEW_DEV_KMS_MASTER_REF"),
        vault_addr=os.environ.get("LEXREVIEW_VAULT_ADDR"),
        vault_token_ref=os.environ.get("LEXREVIEW_VAULT_TOKEN_REF"),
        egress_allow=allow,
        loopback_allow=loopback,
        require_mfa=require_mfa,
    )
    return s
