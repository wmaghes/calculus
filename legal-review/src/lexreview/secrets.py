"""Secret references.

Secrets and keys are never hardcoded and never passed as literal config
values. Config holds a *reference*, resolved at use time:

    env:NAME          value of environment variable NAME
    file:/abs/path    contents of a file (must not be group/world readable)

A secret-manager backend (e.g. Vault KV) can be added as another scheme.
"""

from __future__ import annotations

import os
import stat

from .errors import ConfigError


def resolve_secret(ref: str) -> bytes:
    if not isinstance(ref, str) or ":" not in ref:
        raise ConfigError("secret_ref_invalid")
    scheme, _, rest = ref.partition(":")
    if scheme == "env":
        val = os.environ.get(rest)
        if not val:
            raise ConfigError("secret_ref_unset")
        return val.encode()
    if scheme == "file":
        if not os.path.isabs(rest):
            raise ConfigError("secret_ref_invalid")
        st = os.stat(rest)
        if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ConfigError("secret_file_permissions")
        with open(rest, "rb") as fh:
            return fh.read().strip()
    raise ConfigError("secret_ref_scheme_unsupported")


def resolve_hex_key(ref: str, length: int = 32) -> bytes:
    raw = resolve_secret(ref)
    try:
        key = bytes.fromhex(raw.decode())
    except ValueError as exc:
        raise ConfigError("secret_key_not_hex") from exc
    if len(key) != length:
        raise ConfigError("secret_key_wrong_length")
    return key
