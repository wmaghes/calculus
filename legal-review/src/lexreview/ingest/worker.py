"""Sandboxed parser worker entry point.

Run only by ingest.sandbox: `python -I -m lexreview.ingest.worker '<limits json>'`
with the file bytes on stdin and a JSON result on stdout. It runs with
resource limits, an empty network namespace when available, a private
TMPDIR, and a socket guard as a second layer. Its stderr is discarded by
the parent, so a crashing third-party parser cannot leak content into logs.
"""

from __future__ import annotations

import base64
import json
import socket
import sys


def _deny_network() -> None:
    class _NoSocket(socket.socket):
        def __init__(self, *a, **k):  # noqa: ARG002
            raise PermissionError("network_disabled_in_parser")

    socket.socket = _NoSocket  # type: ignore[misc]
    socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(PermissionError("network_disabled_in_parser"))  # type: ignore[assignment]


def main() -> int:
    _deny_network()
    limits = json.loads(sys.argv[1])
    data = sys.stdin.buffer.read()
    if len(sys.argv) > 2 and sys.argv[2].startswith("render:"):
        from .formats import render_page

        png = render_page(data, int(sys.argv[2].split(":", 1)[1]), limits)
        sys.stdout.write(json.dumps({"png": base64.b64encode(png).decode() if png else None}))
        sys.stdout.flush()
        return 0
    from .formats import parse

    res = parse(data, limits)
    out = {
        "kind": res.kind,
        "status": res.status,
        "reason": res.reason,
        "pages": [p.__dict__ for p in res.pages],
        "meta": res.meta,
        "children": [[name, base64.b64encode(blob).decode()] for name, blob in res.children],
    }
    sys.stdout.write(json.dumps(out))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
