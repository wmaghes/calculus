"""In-process default-deny egress guard (defense in depth).

Loopback is NOT trusted blindly: a local forward proxy (e.g. one configured
through HTTPS_PROXY) would relay traffic anywhere. Loopback connections are
allowed only to ports on an explicit allowlist (LEXREVIEW_LOOPBACK_ALLOW,
e.g. the local model server's port). Found during Phase 1 testing, when an
HTTP client reached the internet through this sandbox's loopback proxy.

The primary egress control has to be at the network layer (host firewall /
Kubernetes NetworkPolicy / no default route; see deploy/nftables.example).
This guard is a second layer inside the process: once installed, DNS lookups
and outbound connections are refused unless the destination is loopback or a
hostname on the allowlist (LEXREVIEW_EGRESS_ALLOW plus hosts added by
components that need them, e.g. the Vault address).

Refusals raise EgressBlocked and are logged as an event with no destination
details beyond a reason code.
"""

from __future__ import annotations

import ipaddress
import socket
import threading

from .errors import EgressBlocked
from .safelog import log_event

_lock = threading.Lock()
_allowed_hosts: set[str] = set()
_allowed_ips: set[str] = set()
_loopback_ports: set[int] = set()
_installed = False
_orig_getaddrinfo = socket.getaddrinfo
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex


def _is_loopback(host: str) -> bool:
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _guarded_getaddrinfo(host, *args, **kwargs):
    h = (host.decode() if isinstance(host, bytes) else str(host or "")).lower().rstrip(".")
    if not (_is_loopback(h) or h in _allowed_hosts):
        log_event("egress_blocked", reason="dns_not_allowlisted")
        raise EgressBlocked()
    res = _orig_getaddrinfo(host, *args, **kwargs)
    with _lock:
        for fam, *_rest, sockaddr in res:
            if fam in (socket.AF_INET, socket.AF_INET6) and not _is_loopback(h):
                _allowed_ips.add(sockaddr[0])
    return res


def _check_addr(sock, address) -> None:
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return  # AF_UNIX etc. are local
    host = str(address[0])
    if _is_loopback(host):
        if int(address[1]) in _loopback_ports:
            return
        log_event("egress_blocked", reason="loopback_port_not_allowlisted")
        raise EgressBlocked()
    if host in _allowed_ips:
        return
    log_event("egress_blocked", reason="connect_not_allowlisted")
    raise EgressBlocked()


def _guarded_connect(self, address):
    _check_addr(self, address)
    return _orig_connect(self, address)


def _guarded_connect_ex(self, address):
    _check_addr(self, address)
    return _orig_connect_ex(self, address)


def install(allow_hosts: tuple[str, ...] | list[str] = (), loopback_ports: tuple[int, ...] | list[int] = ()) -> None:
    global _installed
    with _lock:
        _allowed_hosts.update(h.lower().rstrip(".") for h in allow_hosts)
        _loopback_ports.update(int(p) for p in loopback_ports)
        if _installed:
            return
        socket.getaddrinfo = _guarded_getaddrinfo
        socket.socket.connect = _guarded_connect
        socket.socket.connect_ex = _guarded_connect_ex
        _installed = True


def allow_host(host: str) -> None:
    with _lock:
        _allowed_hosts.add(host.lower().rstrip("."))


def allow_loopback_port(port: int) -> None:
    with _lock:
        _loopback_ports.add(int(port))


def uninstall() -> None:
    """For tests only."""
    global _installed
    with _lock:
        socket.getaddrinfo = _orig_getaddrinfo
        socket.socket.connect = _orig_connect
        socket.socket.connect_ex = _orig_connect_ex
        _allowed_hosts.clear()
        _allowed_ips.clear()
        _loopback_ports.clear()
        _installed = False
