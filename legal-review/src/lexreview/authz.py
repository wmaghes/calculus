"""Role-based, per-case authorization.

The only way to touch case data is through a CaseAccessContext, and the only
way to get one is App.authorize() (see app.py), which checks an authenticated
session against the case membership table and writes an audit record either
way. Contexts carry an unforgeable seal: code that builds one by hand gets
a context every store rejects.

Document-level restrictions: a document may carry a restriction label
(e.g. "aeo" for attorneys' eyes only, "privileged"). A user sees such a
document only if they hold an explicit grant for that label on that case.
No role gets restricted labels implicitly, including case_admin.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from enum import Enum

from .errors import AccessDenied


class Perm(str, Enum):
    VIEW = "view"              # open documents and pages
    SEARCH = "search"          # search, Q&A, timelines
    INGEST = "ingest"
    EXPORT = "export"
    MARK = "mark"              # record relevant/not-relevant
    MANAGE = "manage"          # memberships, grants, restriction labels
    VIEW_AUDIT = "view_audit"
    DESTROY = "destroy"        # crypto-shred the case
    LEGAL_PROPOSE = "legal_propose"  # draft an outside legal-database search
    LEGAL_APPROVE = "legal_approve"  # approve the exact text of an outside search


class Role(str, Enum):
    CASE_ADMIN = "case_admin"
    ATTORNEY = "attorney"
    PARALEGAL = "paralegal"
    REVIEWER = "reviewer"      # e.g. interns / contract reviewers


ROLE_PERMS: dict[Role, frozenset[Perm]] = {
    Role.CASE_ADMIN: frozenset(Perm),
    Role.ATTORNEY: frozenset({Perm.VIEW, Perm.SEARCH, Perm.EXPORT, Perm.MARK, Perm.INGEST,
                              Perm.LEGAL_PROPOSE, Perm.LEGAL_APPROVE}),
    Role.PARALEGAL: frozenset({Perm.VIEW, Perm.SEARCH, Perm.EXPORT, Perm.MARK, Perm.INGEST, Perm.LEGAL_PROPOSE}),
    Role.REVIEWER: frozenset({Perm.VIEW, Perm.SEARCH, Perm.MARK}),
}

# Process-local secret. A context's seal is an HMAC over ALL of its fields,
# so a hand-built context, or a real one with any field changed (e.g. via
# dataclasses.replace(ctx, case_id=...)), is rejected.
_SEAL_KEY = secrets.token_bytes(32)


def _seal(user_id: str, case_id: str, role: "Role", perms: frozenset, grants: frozenset, session_id: str) -> bytes:
    msg = "\x1f".join([user_id, case_id, role.value, ",".join(sorted(p.value for p in perms)),
                       ",".join(sorted(grants)), session_id])
    return hmac.new(_SEAL_KEY, msg.encode(), hashlib.sha256).digest()


@dataclass(frozen=True)
class CaseAccessContext:
    user_id: str
    case_id: str
    role: Role
    perms: frozenset[Perm]
    grants: frozenset[str]
    session_id: str
    _seal: bytes = field(repr=False, compare=False, default=b"")

    def require(self, perm: Perm) -> None:
        verify_context(self)
        if perm not in self.perms:
            raise AccessDenied()

    def can_see_label(self, label: str | None) -> bool:
        return label is None or label in self.grants


def issue_context(user_id: str, case_id: str, role: Role, grants: frozenset[str], session_id: str) -> CaseAccessContext:
    """Only App.authorize() calls this, after the membership check."""
    perms = ROLE_PERMS[role]
    return CaseAccessContext(user_id, case_id, role, perms, grants, session_id,
                             _seal(user_id, case_id, role, perms, grants, session_id))


def verify_context(ctx: object, case_id: str | None = None) -> CaseAccessContext:
    if not isinstance(ctx, CaseAccessContext):
        raise AccessDenied("forged_context")
    try:
        expected = _seal(ctx.user_id, ctx.case_id, Role(ctx.role), ctx.perms, ctx.grants, ctx.session_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise AccessDenied("forged_context") from exc
    if not hmac.compare_digest(ctx._seal, expected):
        raise AccessDenied("forged_context")
    if case_id is not None and ctx.case_id != case_id:
        raise AccessDenied("cross_case")
    return ctx
