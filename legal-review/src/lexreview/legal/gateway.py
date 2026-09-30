"""Legal-authority gateway: the ONLY component that sends requests off the
firm network, and only to an allowlist of official/public legal sources.

* HTTPS only; host must be on LEGAL_HOSTS (checked for every request and
  every redirect is refused).
* Environment proxies are ignored (trust_env=False). A firm egress proxy can
  be configured explicitly with LEXREVIEW_LEGAL_PROXY.
* Responses are capped in size and treated as untrusted text.
* Disabled unless LEXREVIEW_LEGAL_SOURCES=1. When enabled, the hosts are
  added to the in-process egress guard; the network-layer firewall must
  allow them too (ideally from a separate egress host; see
  deploy/nftables.example).
* API keys are secret references, never literals.

Nothing is sent from here except a query text a person approved (see
legal/leads.py) or an ID taken from a result of that query.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from .. import netguard
from ..errors import ConfigError, EgressBlocked
from ..secrets import resolve_secret

LEGAL_HOSTS = frozenset({
    "www.courtlistener.com",
    "api.govinfo.gov",
    "www.ecfr.gov",
    "codes.ohio.gov",
    "www.legislature.mi.gov",
    # Copractice additions: SEC EDGAR (public filings) and bar ethics opinions.
    "efts.sec.gov",
    "www.sec.gov",
    "www.bpc.ohio.gov",
    "www.michbar.org",
})
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 20.0


class SourceUnavailable(Exception):
    """The source could not be reached or answered unusably. `reason` is a
    fixed code, never response content."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class LegalGateway:
    def __init__(self, transport: httpx.BaseTransport | None = None, enabled: bool | None = None):
        self.enabled = (os.environ.get("LEXREVIEW_LEGAL_SOURCES") == "1") if enabled is None else enabled
        proxy = os.environ.get("LEXREVIEW_LEGAL_PROXY") or None
        self._client = httpx.Client(transport=transport, timeout=TIMEOUT, trust_env=False, follow_redirects=False,
                                    proxy=proxy if transport is None else None,
                                    headers={"User-Agent": "lexreview-legal-gateway/0.1"})
        if self.enabled and transport is None:
            for h in LEGAL_HOSTS:
                netguard.allow_host(h)

    @staticmethod
    def secret(ref_env: str) -> str | None:
        ref = os.environ.get(ref_env)
        return resolve_secret(ref).decode() if ref else None

    def get(self, url: str, params: dict | None = None, headers: dict | None = None,
            json_body: dict | None = None) -> "Resp":
        if not self.enabled:
            raise SourceUnavailable("legal_sources_disabled")
        u = urlparse(url)
        if u.scheme != "https" or u.hostname not in LEGAL_HOSTS:
            raise ConfigError("legal_host_not_allowlisted")
        method = "POST" if json_body is not None else "GET"
        try:
            with self._client.stream(method, url, params=params, headers=headers, json=json_body) as r:
                if 300 <= r.status_code < 400:
                    raise SourceUnavailable("redirect_refused")
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > MAX_BYTES:  # stop reading; never buffer an unbounded body
                        raise SourceUnavailable("response_too_large")
                return Resp(r.status_code, bytes(buf))
        except EgressBlocked:
            raise SourceUnavailable("egress_blocked") from None
        except httpx.TimeoutException:
            raise SourceUnavailable("timeout") from None
        except httpx.HTTPError:
            raise SourceUnavailable("connection_failed") from None


class Resp:
    def __init__(self, status: int, content: bytes):
        self.status_code, self.content = status, content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self):
        import json

        try:
            return json.loads(self.content)
        except ValueError:
            raise SourceUnavailable("invalid_json") from None
