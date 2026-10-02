"""Default-deny egress."""

import socket

import pytest

from lexreview import netguard
from lexreview.errors import EgressBlocked
from lexreview.ingest.sandbox import run_parser


@pytest.fixture
def guard():
    netguard.uninstall()
    netguard.install(("vault.internal.example",))
    yield
    netguard.uninstall()


def test_dns_to_unlisted_host_blocked(guard):
    with pytest.raises(EgressBlocked):
        socket.getaddrinfo("exfil.example", 443)


def test_direct_ip_connect_blocked(guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(EgressBlocked):
            s.connect(("93.184.216.34", 80))
    finally:
        s.close()


def _listener():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    return srv


def test_loopback_only_to_allowlisted_ports(guard):
    ok, other = _listener(), _listener()
    netguard.allow_loopback_port(ok.getsockname()[1])
    try:
        c = socket.socket()
        c.connect(ok.getsockname())
        c.close()
        c = socket.socket()
        with pytest.raises(EgressBlocked):
            c.connect(other.getsockname())
        c.close()
    finally:
        ok.close()
        other.close()


def _chain(exc):
    while exc is not None:
        yield exc
        exc = exc.__cause__ or exc.__context__


def test_http_client_blocked_even_via_local_proxy(guard, monkeypatch):
    """A forward proxy on loopback must not become an egress path."""
    import httpx

    proxy = _listener()
    monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{proxy.getsockname()[1]}")
    try:
        with pytest.raises(Exception) as e:
            httpx.get("https://exfil.example/collect", timeout=2)
        assert any(isinstance(x, EgressBlocked) for x in _chain(e.value))
        monkeypatch.delenv("HTTPS_PROXY")
        with pytest.raises(Exception) as e:
            httpx.get("https://exfil.example/collect", timeout=2, trust_env=False)
        assert any(isinstance(x, EgressBlocked) for x in _chain(e.value))
    finally:
        proxy.close()


def test_app_installs_guard(app):
    with pytest.raises(EgressBlocked):
        socket.getaddrinfo("exfil.example", 443)
    netguard.uninstall()


def test_parser_worker_has_no_network(app, tmp_path):
    """Run the worker's network denial directly: a parser that tries to open
    a socket must fail."""
    import subprocess
    import sys

    code = ("from lexreview.ingest.worker import _deny_network; _deny_network();"
            "import socket\n"
            "try:\n socket.socket(); print('OPEN')\nexcept PermissionError: print('DENIED')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.stdout.strip() == "DENIED"
    # And the namespace layer: inside `unshare -n` only loopback exists.
    import shutil
    if shutil.which("unshare"):
        r = subprocess.run(["unshare", "-n", sys.executable, "-c",
                            "import socket;s=socket.socket();s.settimeout(2)\n"
                            "try:\n s.connect(('1.1.1.1',80)); print('OPEN')\nexcept OSError: print('NO_ROUTE')"],
                           capture_output=True, text=True)
        assert r.stdout.strip() == "NO_ROUTE"
