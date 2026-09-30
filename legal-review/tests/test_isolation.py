"""Cross-case isolation, restriction labels, forged contexts, crypto-shred,
and 'no plaintext at rest'."""

import dataclasses
import json

import pytest

from lexreview.authz import CaseAccessContext, Perm, Role, issue_context
from lexreview.casestore import CaseStore
from lexreview.errors import AccessDenied, CryptoError, KeyDestroyed, NotFound


def test_user_a_cannot_authorize_case_b(ingested):
    w = ingested
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("alice"), w.case_b, Perm.VIEW)
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("carol"), w.case_a, Perm.VIEW)
    denied = [r for r in w.app.audit.records() if r["action"] == "authorize" and r["outcome"] == "denied"]
    assert any(r["case_id"] == w.case_b and r["actor"] == w.users["alice"]["uid"] for r in denied)


def test_sysadmin_has_no_implicit_case_data_access(ingested):
    w = ingested
    with pytest.raises(AccessDenied):
        w.app.authorize(w.admin, w.case_a, Perm.VIEW)


def test_case_b_doc_ids_invisible_from_case_a(ingested):
    w = ingested
    ctx_b = w.ctx("carol", w.case_b)
    b_doc = w.app.store(ctx_b).list_documents(ctx_b)[0]["doc_id"]
    ctx_a = w.ctx("alice", w.case_a)
    with pytest.raises(NotFound):
        w.app.view_page(ctx_a, b_doc, 1)
    with pytest.raises(NotFound):
        w.app.store(ctx_a).get_blob(ctx_a, b_doc)


def test_context_for_case_a_rejected_by_case_b_store(ingested):
    w = ingested
    ctx_a = w.ctx("alice", w.case_a)
    store_b = w.app.store(w.ctx("carol", w.case_b))
    with pytest.raises(AccessDenied):
        store_b.list_documents(ctx_a)


def test_forged_context_rejected(ingested):
    w = ingested
    forged = CaseAccessContext(w.users["alice"]["uid"], w.case_b, Role.CASE_ADMIN, frozenset(Perm), frozenset({"aeo"}), "s_x")
    with pytest.raises(AccessDenied):
        w.app.store(forged)
    # A genuine context with one field changed keeps its old seal: rejected.
    real_a = w.ctx("bob", w.case_a)  # reviewer: every change below is an escalation
    for change in ({"case_id": w.case_b}, {"grants": frozenset({"aeo"})}, {"perms": frozenset(Perm)},
                   {"user_id": w.users["carol"]["uid"]}):
        with pytest.raises(AccessDenied):
            w.app.store(dataclasses.replace(real_a, **change))


def test_role_permissions_enforced(ingested):
    w = ingested
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("bob"), w.case_a, Perm.EXPORT)   # reviewer cannot export
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("bob"), w.case_a, Perm.INGEST)
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("dave"), w.case_a, Perm.DESTROY)  # attorney cannot destroy


def test_restricted_document_hidden_everywhere(ingested):
    w = ingested
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    for name in ("bob", "dave", "alice"):  # no grants yet, not even case_admin
        ctx = w.ctx(name, w.case_a)
        store = w.app.store(ctx)
        assert amend not in {d["doc_id"] for d in store.list_documents(ctx)}
        with pytest.raises(NotFound):
            store.get_page(ctx, amend, 1)
        with pytest.raises(NotFound):
            store.get_document(ctx, amend)
        rep = w.app.coverage(ctx)
        assert rep["documents_withheld_by_restriction"] == 1  # a number, never the doc


def test_grant_reveals_restricted_document(ingested):
    w = ingested
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    w.app.grant_label(w.p("alice"), w.case_a, w.users["dave"]["uid"], "aeo")
    ctx = w.ctx("dave", w.case_a)
    assert "within one hour" in w.app.view_page(ctx, amend, 1).text
    with pytest.raises(NotFound):  # bob still cannot
        w.app.view_page(w.ctx("bob", w.case_a), amend, 1)


def test_reviewer_cannot_grant(ingested):
    w = ingested
    with pytest.raises(AccessDenied):
        w.app.grant_label(w.p("bob"), w.case_a, w.users["bob"]["uid"], "aeo")


def _all_bytes(root):
    for p in root.rglob("*"):
        if p.is_file():
            yield p, p.read_bytes()


def test_no_plaintext_at_rest(ingested, labels):
    """Canary strings from the synthetic documents must not appear anywhere
    under the data root: DB files, blobs, audit log, temp dirs."""
    w = ingested
    needles = [c.encode() for c in labels["canaries"]] + [b"Temperature Excursion", b"trailer 4471", b"Okafor"]
    hits = [(str(p), n) for p, data in _all_bytes(w.data_root) for n in needles if n in data]
    assert hits == []


def test_crypto_shred(world, corpus):
    w = world
    ctx = w.ctx("alice", w.case_a, Perm.INGEST)
    w.app.ingest(ctx, corpus / "docs" / "emails")
    case_dir = w.app.root / "cases" / w.case_a
    # Keep a "backup" copy of the encrypted files before destruction.
    backup = {p.relative_to(case_dir): p.read_bytes() for p in case_dir.rglob("*") if p.is_file()}
    assert any(k.name == "case.db" for k in backup)
    w.app.destroy_case(w.p("alice"), w.case_a, confirm=w.case_a)
    assert not case_dir.exists()
    with pytest.raises(AccessDenied):
        w.app.authorize(w.p("alice"), w.case_a, Perm.VIEW)
    # Restore the backup: it must be useless without the destroyed KEK.
    for rel, data in backup.items():
        (case_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (case_dir / rel).write_bytes(data)
    wrapped = (case_dir / "dek.wrapped").read_bytes()
    with pytest.raises(KeyDestroyed):
        w.app.kms.unwrap("case-" + w.case_a.replace("_", "-"), wrapped, w.case_a.encode())
    with pytest.raises(CryptoError):  # and a guessed key does not open the DB
        CaseStore(case_dir, w.case_a, b"\0" * 32)
    # The other case is unaffected.
    assert w.app.authorize(w.p("carol"), w.case_b, Perm.VIEW)


def test_destroy_requires_confirmation_and_role(world):
    w = world
    with pytest.raises(AccessDenied):
        w.app.destroy_case(w.p("alice"), w.case_a, confirm="wrong")
    with pytest.raises(AccessDenied):
        w.app.destroy_case(w.p("bob"), w.case_a, confirm=w.case_a)


def test_data_files_owner_only(ingested):
    loose = [str(p) for p in ingested.data_root.rglob("*") if p.stat().st_mode & 0o077]
    assert loose == []
