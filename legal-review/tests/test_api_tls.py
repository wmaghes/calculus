"""HTTP API: auth, cross-case access, security headers, TLS 1.3 only."""

import datetime
import socket
import ssl
import threading
import time

import pyotp
import pytest
from fastapi.testclient import TestClient

from lexreview.api import SECURITY_HEADERS, build_server, create_api


@pytest.fixture
def client(ingested):
    return TestClient(create_api(ingested.app), base_url="https://testserver")


def bearer(w, name):
    return {"Authorization": "Bearer " + w.users[name]["token"]}


def test_requires_auth(client, ingested):
    r = client.get(f"/cases/{ingested.case_a}/coverage")
    assert r.status_code == 401 and r.json() == {"error": "auth_failed"}


def test_security_headers(client, ingested):
    r = client.get(f"/cases/{ingested.case_a}/coverage", headers=bearer(ingested, "alice"))
    assert r.status_code == 200
    for k, v in SECURITY_HEADERS.items():
        assert r.headers[k] == v


def test_cross_case_api_denied(client, ingested):
    w = ingested
    assert client.get(f"/cases/{w.case_b}/documents", headers=bearer(w, "alice")).status_code == 403
    ctx_b = w.ctx("carol", w.case_b)
    b_doc = w.app.store(ctx_b).list_documents(ctx_b)[0]["doc_id"]
    r = client.get(f"/cases/{w.case_a}/documents/{b_doc}/pages/1", headers=bearer(w, "alice"))
    assert r.status_code == 404


def test_page_and_quote_endpoints(client, ingested):
    w = ingested
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    r = client.get(f"/cases/{w.case_a}/documents/{msa}/pages/4", headers=bearer(w, "bob"))
    assert r.status_code == 200 and "7.2" in r.json()["text"]
    ok = client.post(f"/cases/{w.case_a}/verify-quote", headers=bearer(w, "bob"),
                     json={"doc_id": msa, "page": 4, "quote": "Any reading outside that range for more than thirty minutes"})
    assert ok.json()["verified"] is True
    bad = client.post(f"/cases/{w.case_a}/verify-quote", headers=bearer(w, "bob"),
                      json={"doc_id": msa, "page": 4, "quote": "Meridian is never liable for anything at all"})
    assert bad.json() == {"verified": False, "reason": "quote_not_on_page"}


def test_cookie_session_requires_csrf_for_state_change(client, ingested):
    w = ingested
    client.cookies.set("lr_session", w.users["dave"]["token"])
    client.cookies.set("lr_csrf", "abc")
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    body = {"doc_id": msa, "page": 4, "quote": "Any reading outside that range for more than thirty minutes"}
    assert client.post(f"/cases/{w.case_a}/verify-quote", json=body).status_code == 401
    assert client.post(f"/cases/{w.case_a}/verify-quote", json=body, headers={"X-CSRF-Token": "abc"}).status_code == 200


def test_errors_do_not_leak_exception_text(client, ingested, monkeypatch):
    w = ingested

    def boom(*a, **k):
        raise RuntimeError("CANARY-7F3A9C-REEFER")
    monkeypatch.setattr(w.app, "coverage", boom)
    r = client.get(f"/cases/{w.case_a}/coverage", headers=bearer(w, "alice"))
    assert r.status_code == 500 and "CANARY" not in r.text


def _self_signed(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(key, hashes.SHA256()))
    c, k = tmp_path / "c.pem", tmp_path / "k.pem"
    c.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    k.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    return str(c), str(k)


def test_server_speaks_only_tls13(ingested, tmp_path):
    cert, key = _self_signed(tmp_path)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    from lexreview import netguard

    netguard.allow_loopback_port(port)  # the guard is installed by App
    server = build_server(ingested.app, "127.0.0.1", port, cert, key)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)

    def handshake(version):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ctx.maximum_version = version
        with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
            with ctx.wrap_socket(raw, server_hostname="localhost") as tls:
                return tls.version()
    try:
        assert handshake(ssl.TLSVersion.TLSv1_3) == "TLSv1.3"
        with pytest.raises(ssl.SSLError):
            handshake(ssl.TLSVersion.TLSv1_2)
    finally:
        server.should_exit = True
        t.join(5)
