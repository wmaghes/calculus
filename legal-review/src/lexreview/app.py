"""Application facade: the single entry point used by the CLI and the API.

Every operation that touches case data goes through `authorize()`, which
turns an authenticated Principal plus a case_id into a sealed
CaseAccessContext, or refuses (and audits the refusal).
"""

from __future__ import annotations

import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import crypto, netguard
from .audit import AuditLog
from .auth import Authenticator, Principal
from .authz import CaseAccessContext, Perm, Role, issue_context, verify_context
from .casestore import CaseStore
from .config import Settings
from .controlplane import open_control
from .errors import AccessDenied, AuthError, ConfigError, KeyDestroyed, NotFound
from .kms import KMS, kms_from_settings
from .safelog import log_event

CONTROL_KEY_ID = "control"
_LABEL = re.compile(r"^[a-z0-9_\-]{1,32}$")
AUDIT_KEY_ID = "audit"


def _case_key_id(case_id: str) -> str:
    return "case-" + case_id.replace("_", "-")


def _write_new(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def _shred_file(path: Path) -> None:
    """Best-effort overwrite + unlink. Not a guarantee on SSD/COW/journaled
    storage; the KEK destruction is what makes the data unrecoverable."""
    if path.exists():
        size = path.stat().st_size
        with open(path, "r+b") as fh:
            fh.write(os.urandom(size))
            fh.flush()
            os.fsync(fh.fileno())
        path.unlink()


class App:
    def __init__(self, settings: Settings, kms: KMS | None = None):
        # Everything this process creates (DBs, journals, blobs, exports) is
        # owner-only. SQLCipher and tempfile otherwise follow the umask.
        os.umask(0o077)
        self.settings = settings
        self.root = settings.data_root
        self.kms = kms or kms_from_settings(settings)
        netguard.install(settings.egress_allow, settings.loopback_allow)
        if settings.vault_addr:
            from urllib.parse import urlparse

            netguard.allow_host(urlparse(settings.vault_addr).hostname or "")
        ctl_wrapped = self.root / "control.dek.wrapped"
        aud_wrapped = self.root / "audit.key.wrapped"
        if not (ctl_wrapped.exists() and aud_wrapped.exists()):
            raise ConfigError("not_initialized")
        ctl_key = self.kms.unwrap(CONTROL_KEY_ID, ctl_wrapped.read_bytes(), b"control")
        aud_key = self.kms.unwrap(AUDIT_KEY_ID, aud_wrapped.read_bytes(), b"audit")
        self.control = open_control(self.root / "control.db", crypto.derive(ctl_key, "sqlcipher"))
        self.audit = AuditLog(self.root / "audit" / "audit.log", crypto.derive(aud_key, "audit-hmac"))
        self.auth = Authenticator(self.control, settings.require_mfa)
        self._stores: dict[str, CaseStore] = {}
        self._indexes: dict[str, object] = {}  # case_id -> VectorIndex (decrypted, in memory)
        self._lock = threading.RLock()  # store() is called while holding it (e.g. from _index)

    # ------------------------------------------------------------ bootstrap
    @classmethod
    def initialize(cls, settings: Settings, kms: KMS | None = None) -> "App":
        os.umask(0o077)
        root = settings.data_root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        kms = kms or kms_from_settings(settings)
        for key_id, fname, ctx in ((CONTROL_KEY_ID, "control.dek.wrapped", b"control"),
                                   (AUDIT_KEY_ID, "audit.key.wrapped", b"audit")):
            path = root / fname
            if path.exists():
                continue
            if not kms.key_exists(key_id):
                kms.create_key(key_id)
            _write_new(path, kms.wrap(key_id, crypto.new_key(), ctx))
        return cls(settings, kms)

    def close(self) -> None:
        for s in self._stores.values():
            s.close()
        self._stores.clear()
        self.control.close()

    # ------------------------------------------------------------ auth
    def bootstrap_admin(self, username: str, password: str) -> tuple[str, str | None]:
        if self.control.execute("SELECT count(*) FROM users").fetchone()[0]:
            raise AccessDenied("already_bootstrapped")
        uid, totp = self.auth.create_user(username, password, is_sysadmin=True)
        self.audit.record(uid, "bootstrap_admin", "ok")
        return uid, totp

    def login(self, username: str, password: str, totp: str | None) -> str:
        try:
            token, p = self.auth.login(username, password, totp)
        except AuthError:
            uid = self.auth.user_id_for(username)
            self.audit.record(uid or "unknown_user", "login", "denied",
                              username_digest=self.audit.digest("user:" + username))
            raise
        self.audit.record(p.user_id, "login", "ok", session=p.session_id)
        return token

    def principal(self, token: str) -> Principal:
        return self.auth.authenticate(token)

    def logout(self, token: str) -> None:
        try:
            p = self.auth.authenticate(token)
            self.audit.record(p.user_id, "logout", "ok", session=p.session_id)
        except AuthError:
            pass
        self.auth.logout(token)

    def create_user(self, p: Principal, username: str, password: str, sysadmin: bool = False) -> tuple[str, str | None]:
        if not p.is_sysadmin:
            self.audit.record(p.user_id, "create_user", "denied")
            raise AccessDenied()
        uid, totp = self.auth.create_user(username, password, is_sysadmin=sysadmin)
        self.audit.record(p.user_id, "create_user", "ok", target=uid, sysadmin=sysadmin)
        return uid, totp

    # ------------------------------------------------------------ cases
    def create_case(self, p: Principal, display_name: str) -> str:
        if not p.is_sysadmin:
            self.audit.record(p.user_id, "create_case", "denied")
            raise AccessDenied()
        case_id = "c_" + uuid.uuid4().hex[:16]
        case_dir = self.root / "cases" / case_id
        case_dir.mkdir(parents=True, mode=0o700)
        key_id = _case_key_id(case_id)
        self.kms.create_key(key_id)
        dek = crypto.new_key()
        _write_new(case_dir / "dek.wrapped", self.kms.wrap(key_id, dek, case_id.encode()))
        CaseStore(case_dir, case_id, dek).close()
        self.control.execute("INSERT INTO cases (case_id, display_name, status, created_at) VALUES (?,?,?,?)",
                             (case_id, display_name, "active", time.time()))
        self.audit.record(p.user_id, "create_case", "ok", case_id=case_id)
        return case_id

    def _case_role(self, user_id: str, case_id: str) -> Role | None:
        row = self.control.execute(
            "SELECT m.role FROM memberships m JOIN cases c ON c.case_id=m.case_id "
            "WHERE m.case_id=? AND m.user_id=? AND c.status='active'", (case_id, user_id)).fetchone()
        return Role(row[0]) if row else None

    def add_member(self, p: Principal, case_id: str, user_id: str, role: Role) -> None:
        allowed = p.is_sysadmin or self._case_role(p.user_id, case_id) == Role.CASE_ADMIN
        exists = self.control.execute("SELECT 1 FROM cases WHERE case_id=? AND status='active'", (case_id,)).fetchone()
        if not allowed or not exists:
            self.audit.record(p.user_id, "add_member", "denied", case_id=case_id, target=user_id)
            raise AccessDenied()
        self.control.execute("INSERT OR REPLACE INTO memberships (case_id, user_id, role) VALUES (?,?,?)",
                             (case_id, user_id, Role(role).value))
        self.audit.record(p.user_id, "add_member", "ok", case_id=case_id, target=user_id, role=Role(role).value)

    def grant_label(self, p: Principal, case_id: str, user_id: str, label: str) -> None:
        ctx = self.authorize(p, case_id, Perm.MANAGE)
        if not _LABEL.match(label):
            raise ConfigError("label_invalid")
        if self._case_role(user_id, case_id) is None:
            raise NotFound()
        self.control.execute("INSERT OR IGNORE INTO grants (case_id, user_id, label) VALUES (?,?,?)",
                             (case_id, user_id, label))
        self.audit.record(ctx.user_id, "grant_label", "ok", case_id=case_id, target=user_id, label=label)

    def authorize(self, p: Principal, case_id: str, perm: Perm) -> CaseAccessContext:
        role = self._case_role(p.user_id, case_id)
        if role is None or perm not in issue_context(p.user_id, case_id, role, frozenset(), p.session_id).perms:
            self.audit.record(p.user_id, "authorize", "denied", case_id=case_id, perm=perm.value)
            log_event("access_denied", user_id=p.user_id, reason="not_member_or_perm")
            raise AccessDenied()
        grants = frozenset(r[0] for r in self.control.execute(
            "SELECT label FROM grants WHERE case_id=? AND user_id=?", (case_id, p.user_id)))
        return issue_context(p.user_id, case_id, role, grants, p.session_id)

    def store(self, ctx: CaseAccessContext) -> CaseStore:
        verify_context(ctx)
        with self._lock:
            s = self._stores.get(ctx.case_id)
            if s is None:
                case_dir = self.root / "cases" / ctx.case_id
                wrapped = (case_dir / "dek.wrapped")
                if not wrapped.exists():
                    raise KeyDestroyed()
                dek = self.kms.unwrap(_case_key_id(ctx.case_id), wrapped.read_bytes(), ctx.case_id.encode())
                s = CaseStore(case_dir, ctx.case_id, dek)
                self._stores[ctx.case_id] = s
            return s

    def destroy_case(self, p: Principal, case_id: str, confirm: str) -> None:
        """Crypto-shred: destroy the case KEK, then delete the files.
        After the KEK is gone the data (and every backup of it) is
        unreadable even if file deletion is incomplete."""
        ctx = self.authorize(p, case_id, Perm.DESTROY)
        if confirm != case_id:
            raise AccessDenied("confirmation_mismatch")
        with self._lock:
            s = self._stores.pop(case_id, None)
            self._indexes.pop(case_id, None)
            if s:
                s.close()
        self.kms.destroy_key(_case_key_id(case_id))
        case_dir = self.root / "cases" / case_id
        _shred_file(case_dir / "dek.wrapped")
        shutil.rmtree(case_dir, ignore_errors=True)
        self.control.execute("UPDATE cases SET status='destroyed', destroyed_at=? WHERE case_id=?", (time.time(), case_id))
        self.control.execute("DELETE FROM grants WHERE case_id=?", (case_id,))
        self.audit.record(ctx.user_id, "destroy_case", "ok", case_id=case_id)

    def set_restriction(self, ctx: CaseAccessContext, doc_id: str, label: str | None) -> None:
        if label is not None and not _LABEL.match(label):
            raise ConfigError("label_invalid")
        self.store(ctx).set_restriction(ctx, doc_id, label)
        self.audit.record(ctx.user_id, "set_restriction", "ok", case_id=ctx.case_id, target=doc_id, label=label)

    # ------------------------------------------------------------ data access
    def view_page(self, ctx: CaseAccessContext, doc_id: str, page_no: int):
        store = self.store(ctx)
        try:
            page = store.get_page(ctx, doc_id, page_no)
        except NotFound:
            self.audit.record(ctx.user_id, "view_page", "not_found", case_id=ctx.case_id, target=doc_id, page=page_no)
            raise
        self.audit.record(ctx.user_id, "view_page", "ok", case_id=ctx.case_id, target=doc_id, page=page_no)
        return page

    def view_document(self, ctx: CaseAccessContext, doc_id: str) -> dict:
        store = self.store(ctx)
        try:
            doc = store.get_document(ctx, doc_id)
        except NotFound:
            self.audit.record(ctx.user_id, "view_document", "not_found", case_id=ctx.case_id, target=doc_id)
            raise
        self.audit.record(ctx.user_id, "view_document", "ok", case_id=ctx.case_id, target=doc_id)
        return doc

    def ingest(self, ctx: CaseAccessContext, path: Path, restriction: str | None = None) -> dict:
        from .ingest.pipeline import ingest_path

        ctx.require(Perm.INGEST)
        if restriction is not None and not _LABEL.match(restriction):
            raise ConfigError("label_invalid")
        return ingest_path(self, ctx, Path(path), restriction)

    def cases_for(self, p: Principal) -> list[dict]:
        rows = self.control.execute(
            "SELECT c.case_id, c.display_name, m.role FROM memberships m JOIN cases c ON c.case_id=m.case_id "
            "WHERE m.user_id=? AND c.status='active' ORDER BY c.display_name", (p.user_id,)).fetchall()
        return [{"case_id": r[0], "display_name": r[1], "role": r[2]} for r in rows]

    def rebuild_index(self, ctx: CaseAccessContext) -> int:
        from .search.hybrid import build_index

        ctx.require(Perm.INGEST)
        n = build_index(self.store(ctx), ctx)
        with self._lock:
            self._indexes.pop(ctx.case_id, None)
        self.audit.record(ctx.user_id, "rebuild_index", "ok", case_id=ctx.case_id, chunks=n)
        return n

    def _index(self, ctx: CaseAccessContext):
        from .search.hybrid import load_index

        with self._lock:
            if ctx.case_id not in self._indexes:
                self._indexes[ctx.case_id] = load_index(self.store(ctx), ctx)
            return self._indexes[ctx.case_id]

    def search(self, ctx: CaseAccessContext, query: str, top_k: int = 50) -> dict:
        """Hybrid search. Every result is cited and re-verified; the response
        always carries the coverage report."""
        from .coverage import coverage_report, coverage_summary_line
        from .search.hybrid import hybrid_search

        try:
            ctx.require(Perm.SEARCH)
        except AccessDenied:
            self.audit.record(ctx.user_id, "search", "denied", case_id=ctx.case_id)
            raise
        query = (query or "").strip()[:2000]
        store = self.store(ctx)
        res = hybrid_search(store, ctx, self._index(ctx), query, max(1, min(int(top_k), 500)))
        rep = coverage_report(store, ctx)
        res["coverage"] = rep
        res["coverage_summary"] = coverage_summary_line(rep)
        if res["not_found"]:
            res["message"] = "Not found in the reviewed documents."
        self.audit.record(ctx.user_id, "search", "ok", case_id=ctx.case_id, query_id=res["query_id"],
                          query_digest=self.audit.digest("q:" + query), n_results=len(res["results"]),
                          integrity_failures=res["integrity_failures"])
        return res

    def mark(self, ctx: CaseAccessContext, doc_id: str, page_no: int | None, label: str, query_id: str | None) -> int:
        if label not in ("relevant", "not_relevant"):
            raise ConfigError("mark_label_invalid")
        if query_id is not None and not re.match(r"^q_[0-9a-f]{16}$", query_id):
            query_id = None
        try:
            mark_id = self.store(ctx).add_mark(ctx, doc_id, page_no, label, query_id)
        except (AccessDenied, NotFound):
            self.audit.record(ctx.user_id, "mark", "denied", case_id=ctx.case_id, target=doc_id)
            raise
        self.audit.record(ctx.user_id, "mark", "ok", case_id=ctx.case_id, target=doc_id, page=page_no,
                          label=label, query_id=query_id)
        return mark_id

    def page_image(self, ctx: CaseAccessContext, doc_id: str, page_no: int) -> bytes | None:
        """PNG of the original page (PDF/image only), rendered in the parser
        sandbox from the decrypted original. Never cached."""
        from .ingest.sandbox import run_render

        store = self.store(ctx)
        doc = store.get_document(ctx, doc_id)  # visibility check
        if doc["kind"] not in ("pdf", "image"):
            return None
        png = run_render(store.get_blob(ctx, doc_id), page_no, self.settings, self.root / "tmp")
        self.audit.record(ctx.user_id, "view_page_image", "ok" if png else "unavailable", case_id=ctx.case_id,
                          target=doc_id, page=page_no)
        return png

    def coverage(self, ctx: CaseAccessContext) -> dict:
        from .coverage import coverage_report

        ctx.require(Perm.VIEW)
        rep = coverage_report(self.store(ctx), ctx)
        self.audit.record(ctx.user_id, "coverage_report", "ok", case_id=ctx.case_id)
        return rep

    def export(self, ctx: CaseAccessContext, what: str, fmt: str, out_dir: Path) -> Path:
        from .export import export_report

        try:
            ctx.require(Perm.EXPORT)
        except AccessDenied:
            self.audit.record(ctx.user_id, "export", "denied", case_id=ctx.case_id, what=what)
            raise
        path, digest = export_report(self, ctx, what, fmt, Path(out_dir))
        self.audit.record(ctx.user_id, "export", "ok", case_id=ctx.case_id, what=what, fmt=fmt, sha256=digest)
        return path
