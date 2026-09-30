"""Model backends (swappable). The model has NO tools: it receives text and
returns text. Nothing it outputs is executed, fetched, or rendered as markup.

Backends:
    ExtractiveBackend  default; no model at all. Answers are built only from
                       sentences in the supplied sources that share terms with
                       the question. Deterministic.
    LocalHTTPBackend   a self-hosted model server (Ollama or llama.cpp
                       server API) on 127.0.0.1 only. The port must be on
                       LEXREVIEW_LOOPBACK_ALLOW. Proxies from the environment
                       are ignored (trust_env=False). Temperature 0.

There is deliberately no hosted-provider backend. Adding one requires a
zero-data-retention agreement and counsel review (SECURITY.md).

Configuration:
    LEXREVIEW_LLM          extractive (default) | ollama | llamacpp
    LEXREVIEW_LLM_URL      e.g. http://127.0.0.1:11434
    LEXREVIEW_LLM_MODEL    model name for the server
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol
from urllib.parse import urlparse

import httpx

from .errors import ConfigError
from .search.embed import tokenize

MAX_OUTPUT_CHARS = 20_000


class LLMBackend(Protocol):
    name: str

    def complete(self, system: str, user: str, sources: list[dict], question: str) -> str: ...


class ExtractiveBackend:
    """No generative model: returns sentences from the sources that best
    overlap the question, as JSON claims quoting themselves."""

    name = "extractive (no generative model)"

    def complete(self, system: str, user: str, sources: list[dict], question: str) -> str:  # noqa: ARG002
        q = set(tokenize(question))
        scored = []
        for src in sources:
            # Join wrapped lines, then split into sentences; quotes still
            # verify because citation matching normalizes whitespace.
            for sent in re.split(r"(?<=[.!?])\s+|\n\s*\n", re.sub(r"(?<!\n)\n(?!\n)", " ", src["text"])):
                sent = sent.strip()
                if len(sent) < 20:
                    continue
                overlap = len(q & set(tokenize(sent)))
                if overlap >= max(2, len(q) // 3):
                    scored.append((overlap, src["id"], sent))
        scored.sort(key=lambda x: -x[0])
        claims = [{"text": sent, "citations": [{"source": sid, "quote": sent}]} for _, sid, sent in scored[:6]]
        return json.dumps({"claims": claims, "not_found": not claims})


class LocalHTTPBackend:
    def __init__(self, kind: str, url: str, model: str, allowed_ports: tuple[int, ...], timeout: float = 120.0):
        u = urlparse(url)
        if u.scheme != "http" or u.hostname not in ("127.0.0.1", "::1", "localhost") or u.port is None:
            raise ConfigError("llm_url_must_be_loopback_with_port")
        if u.port not in allowed_ports:
            raise ConfigError("llm_port_not_in_loopback_allowlist")
        self.kind, self.model = kind, model
        self.name = f"{kind}:{model} (local)"
        # trust_env=False: never route through HTTP(S)_PROXY.
        self._client = httpx.Client(base_url=url.rstrip("/"), timeout=timeout, trust_env=False)

    def complete(self, system: str, user: str, sources: list[dict], question: str) -> str:  # noqa: ARG002
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if self.kind == "ollama":
            r = self._client.post("/api/chat", json={"model": self.model, "messages": msgs, "stream": False,
                                                    "format": "json", "options": {"temperature": 0}})
            r.raise_for_status()
            out = r.json().get("message", {}).get("content", "")
        else:  # llama.cpp server, OpenAI-compatible endpoint
            r = self._client.post("/v1/chat/completions", json={"model": self.model, "messages": msgs, "temperature": 0})
            r.raise_for_status()
            out = r.json()["choices"][0]["message"]["content"]
        return str(out)[:MAX_OUTPUT_CHARS]


def backend_from_env(loopback_ports: tuple[int, ...]) -> LLMBackend:
    kind = os.environ.get("LEXREVIEW_LLM", "extractive")
    if kind == "extractive":
        return ExtractiveBackend()
    if kind in ("ollama", "llamacpp"):
        url = os.environ.get("LEXREVIEW_LLM_URL", "")
        model = os.environ.get("LEXREVIEW_LLM_MODEL", "")
        if not model:
            raise ConfigError("llm_model_unset")
        return LocalHTTPBackend(kind, url, model, loopback_ports)
    raise ConfigError("llm_backend_unknown")
