"""Command-line interface.

Passwords are read with getpass (or from stdin with --password-stdin, for
scripted synthetic-data demos). They are never taken as command-line
arguments, where they would land in shell history and `ps` output.

The session token is kept in LEXREVIEW_SESSION_FILE (default
~/.lexreview/session, mode 0600).

Document text printed to the terminal is stripped of control characters,
so a document cannot inject terminal escape sequences.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path

from .app import App
from .audit import Anchor
from .authz import Perm, Role
from .citations import Rejected, verify_quote
from .config import load_settings
from .coverage import coverage_summary_line
from .errors import LexReviewError
from .safelog import configure_logging

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def safe_terminal(text: str) -> str:
    return _CTRL.sub("�", text)


def _session_file() -> Path:
    return Path(os.environ.get("LEXREVIEW_SESSION_FILE", str(Path.home() / ".lexreview" / "session")))


def _read_password(args) -> str:
    if getattr(args, "password_stdin", False):
        return sys.stdin.readline().rstrip("\n")
    return getpass.getpass("Password: ")


def _token() -> str:
    f = _session_file()
    if not f.exists():
        raise SystemExit("not logged in (run: lexreview login)")
    return f.read_text().strip()


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    ap = argparse.ArgumentParser(prog="lexreview", description="Citation-backed discovery review (synthetic data only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    b = sub.add_parser("bootstrap-admin"); b.add_argument("--username", required=True); b.add_argument("--password-stdin", action="store_true")
    lg = sub.add_parser("login"); lg.add_argument("--username", required=True); lg.add_argument("--password-stdin", action="store_true"); lg.add_argument("--totp")
    sub.add_parser("logout")
    ua = sub.add_parser("user-add"); ua.add_argument("--username", required=True); ua.add_argument("--sysadmin", action="store_true"); ua.add_argument("--password-stdin", action="store_true")
    cc = sub.add_parser("case-create"); cc.add_argument("--name", required=True)
    am = sub.add_parser("case-add-member"); am.add_argument("case"); am.add_argument("user_id"); am.add_argument("role", choices=[r.value for r in Role])
    gr = sub.add_parser("case-grant"); gr.add_argument("case"); gr.add_argument("user_id"); gr.add_argument("label")
    ig = sub.add_parser("ingest"); ig.add_argument("case"); ig.add_argument("path"); ig.add_argument("--restriction")
    cv = sub.add_parser("coverage"); cv.add_argument("case"); cv.add_argument("--json", action="store_true")
    dl = sub.add_parser("docs"); dl.add_argument("case")
    pg = sub.add_parser("page"); pg.add_argument("case"); pg.add_argument("doc_id"); pg.add_argument("page", type=int)
    vq = sub.add_parser("verify-quote"); vq.add_argument("case"); vq.add_argument("doc_id"); vq.add_argument("page", type=int); vq.add_argument("quote")
    ex = sub.add_parser("export"); ex.add_argument("case"); ex.add_argument("what", choices=["coverage", "documents"]); ex.add_argument("fmt", choices=["csv", "pdf"]); ex.add_argument("--out", required=True)
    au = sub.add_parser("audit"); au.add_argument("action", choices=["verify", "anchor"]); au.add_argument("--anchor", help="seq:mac from a previous `audit anchor`")
    ds = sub.add_parser("case-destroy"); ds.add_argument("case"); ds.add_argument("--confirm", required=True)
    args = ap.parse_args(argv)

    try:
        settings = load_settings()
        if args.cmd == "init":
            App.initialize(settings).close()
            print("initialized")
            return 0
        app = App(settings)
        try:
            return _dispatch(app, args)
        finally:
            app.close()
    except LexReviewError as exc:
        print(f"error: {exc.code}", file=sys.stderr)
        return 2


def _dispatch(app: App, args) -> int:
    if args.cmd == "bootstrap-admin":
        uid, totp = app.bootstrap_admin(args.username, _read_password(args))
        print(json.dumps({"user_id": uid, "totp_secret_show_once": totp}))
        return 0
    if args.cmd == "login":
        token = app.login(args.username, _read_password(args), args.totp or input("TOTP code: "))
        f = _session_file()
        f.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(token)
        print("logged in")
        return 0
    if args.cmd == "logout":
        app.logout(_token())
        _session_file().unlink(missing_ok=True)
        print("logged out")
        return 0

    p = app.principal(_token())
    if args.cmd == "user-add":
        uid, totp = app.create_user(p, args.username, _read_password(args), args.sysadmin)
        print(json.dumps({"user_id": uid, "totp_secret_show_once": totp}))
    elif args.cmd == "case-create":
        print(app.create_case(p, args.name))
    elif args.cmd == "case-add-member":
        app.add_member(p, args.case, args.user_id, Role(args.role))
        print("ok")
    elif args.cmd == "case-grant":
        app.grant_label(p, args.case, args.user_id, args.label)
        print("ok")
    elif args.cmd == "ingest":
        ctx = app.authorize(p, args.case, Perm.INGEST)
        print(json.dumps(app.ingest(ctx, Path(args.path), args.restriction), indent=1))
        rep = app.coverage(app.authorize(p, args.case, Perm.VIEW))
        print(coverage_summary_line(rep))
    elif args.cmd == "coverage":
        rep = app.coverage(app.authorize(p, args.case, Perm.VIEW))
        if args.json:
            print(safe_terminal(json.dumps(rep, indent=1)))
        else:
            print(coverage_summary_line(rep))
            for k, v in rep["by_status"].items():
                print(f"  {k:24} {v}")
            for g in rep["not_searchable"]:
                print(safe_terminal(f"  NOT SEARCHABLE  {g['doc_id']}  {g['status']:20} {g['source_name']}  ({g['explanation']})"))
            for g in rep["low_confidence"]:
                print(safe_terminal(f"  LOW-CONF OCR    {g['doc_id']}  {g['source_name']}  ({g['reason']})"))
    elif args.cmd == "docs":
        ctx = app.authorize(p, args.case, Perm.VIEW)
        docs = app.store(ctx).list_documents(ctx)
        app.audit.record(ctx.user_id, "list_documents", "ok", case_id=ctx.case_id, count=len(docs))
        for d in docs:
            print(safe_terminal(f"{d['doc_id']}  {d['status']:24} pages={d['page_count']:<4} {d['source_name']}"))
    elif args.cmd == "page":
        ctx = app.authorize(p, args.case, Perm.VIEW)
        pg = app.view_page(ctx, args.doc_id, args.page)
        ocr = f"  [OCR confidence {pg.ocr_conf}]" if pg.ocr else ""
        print(safe_terminal(f"--- {pg.doc_id} page {pg.page_no} ({pg.locator}){ocr} ---\n{pg.text}"))
    elif args.cmd == "verify-quote":
        ctx = app.authorize(p, args.case, Perm.VIEW)
        res = verify_quote(app.store(ctx), ctx, args.doc_id, args.page, args.quote)
        app.audit.record(ctx.user_id, "verify_quote", "rejected" if isinstance(res, Rejected) else "ok",
                         case_id=ctx.case_id, target=args.doc_id)
        if isinstance(res, Rejected):
            print(f"NOT VERIFIED: {res.reason}")
            return 1
        print(safe_terminal(f"VERIFIED at {res.doc_id} {res.locator} chars {res.char_start}-{res.char_end}: \"{res.exact_text}\""))
    elif args.cmd == "export":
        ctx = app.authorize(p, args.case, Perm.EXPORT)
        print(app.export(ctx, args.what, args.fmt, Path(args.out)))
    elif args.cmd == "audit":
        if not p.is_sysadmin:
            raise SystemExit("sysadmin only")
        if args.action == "anchor":
            a = app.audit.anchor()
            app.audit.record(p.user_id, "audit_anchor", "ok", seq=a.seq)
            print(f"{a.seq}:{a.mac}")
        else:
            anchor = None
            if args.anchor:
                seq, mac = args.anchor.split(":")
                anchor = Anchor(int(seq), mac)
            n = app.audit.verify(anchor)
            print(f"audit log OK: {n} records verified")
    elif args.cmd == "case-destroy":
        app.destroy_case(p, args.case, args.confirm)
        print("case destroyed (KEK deleted; data unrecoverable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
