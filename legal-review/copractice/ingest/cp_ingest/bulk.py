"""Stream a bz2-compressed CSV over HTTPS without saving it: bytes are
decompressed and parsed incrementally, so multi-GB bulk files never touch
disk. Handles multi-stream bz2 (pbzip2) files.

Only the configured bulk host is contacted; every request is written to the
audit log (destination + hash of the request line; no user data exists in
these requests)."""

from __future__ import annotations

import bz2
import csv
import io
import sys
from typing import Iterator
from urllib.parse import urlparse

import httpx

csv.field_size_limit(sys.maxsize)


class _BZ2Stream(io.RawIOBase):
    def __init__(self, chunks: Iterator[bytes]):
        self._chunks, self._dec, self._buf, self._eof = chunks, bz2.BZ2Decompressor(), b"", False

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        while not self._buf and not self._eof:
            try:
                data = next(self._chunks)
            except StopIteration:
                self._eof = True
                break
            while data:
                if self._dec.eof:  # next stream in a multi-stream file
                    self._dec = bz2.BZ2Decompressor()
                self._buf += self._dec.decompress(data)
                data = self._dec.unused_data if self._dec.eof else b""
        n = min(len(b), len(self._buf))
        b[:n] = self._buf[:n]
        self._buf = self._buf[n:]
        return n


class BulkClient:
    def __init__(self, base: str, audit=None, transport: httpx.BaseTransport | None = None):
        self.base = base.rstrip("/")
        self.host = urlparse(self.base).hostname
        self._audit = audit
        self._client = httpx.Client(transport=transport, timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=False)

    def _check(self, url: str) -> None:
        u = urlparse(url)
        if u.scheme != "https" or u.hostname != self.host:
            raise ValueError("only the configured bulk host may be contacted")
        if self._audit:
            self._audit("ingest", "download", outbound=True, destination=url, payload=f"GET {url}".encode())

    def _resilient_bytes(self, url: str, retries: int = 8) -> Iterator[bytes]:
        """Yield the body of `url`, reconnecting after network errors with an
        HTTP Range request from the exact byte already received, so a stalled
        multi-GB download resumes instead of restarting. The caller's
        decompressor state is untouched, so no byte is lost or repeated."""
        import time

        offset, failures = 0, 0
        while True:
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            try:
                with self._client.stream("GET", url, headers=headers) as r:
                    if offset and r.status_code != 206:
                        raise RuntimeError("server does not support resuming (no 206)")
                    r.raise_for_status()
                    for chunk in r.iter_bytes(1 << 20):
                        offset += len(chunk)
                        failures = 0
                        yield chunk
                    return
            except (httpx.TransportError, httpx.RemoteProtocolError):
                failures += 1
                if failures > retries:
                    raise
                if self._audit:
                    self._audit("ingest", "download_resume", outbound=True, destination=url,
                                payload=f"GET {url} Range: bytes={offset}-".encode(), offset=offset, attempt=failures)
                time.sleep(min(60, 2 ** failures))

    def rows(self, key: str) -> Iterator[dict]:
        url = f"{self.base}/{key}"
        self._check(url)
        text = io.TextIOWrapper(io.BufferedReader(_BZ2Stream(self._resilient_bytes(url)), 1 << 20),
                                encoding="utf-8", errors="replace", newline="")
        reader = csv.reader(text)
        header = next(reader)
        for row in reader:
            if len(row) == len(header):
                yield dict(zip(header, row))

    def get(self, key: str, max_bytes: int = 50 * 1024 * 1024) -> bytes:
        url = f"{self.base}/{key}"
        self._check(url)
        with self._client.stream("GET", url) as r:
            r.raise_for_status()
            buf = bytearray()
            for chunk in r.iter_bytes():
                buf += chunk
                if len(buf) > max_bytes:
                    raise ValueError("file too large")
            return bytes(buf)

    def latest(self, prefix: str) -> str:
        """Newest bulk file with this prefix (e.g. 'bulk-data/dockets-')."""
        import re

        keys, token = [], None
        while True:
            params = {"list-type": "2", "prefix": prefix}
            if token:
                params["continuation-token"] = token
            self._check(f"{self.base}/?list-type=2&prefix={prefix}")
            r = self._client.get(self.base + "/", params=params)
            r.raise_for_status()
            keys += re.findall(r"<Key>([^<]+\.csv\.bz2)</Key>", r.text)
            m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", r.text)
            if not m:
                break
            token = m.group(1)
        if not keys:
            raise RuntimeError(f"no bulk file for {prefix}")
        return sorted(keys)[-1]
