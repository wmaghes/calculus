"""Reviewer web UI (server-rendered HTML, no JavaScript).

Every search result is a link that opens the source page with the cited
passage highlighted and its full location spelled out (document, doc ID,
page/locator, character range, OCR confidence), plus the original page image
for PDFs and images.

Safety rules for this module:
* All document-derived text goes through html.escape. Nothing from a
  document is ever emitted as markup, a link, or an image source.
* No JavaScript at all; CSP allows only same-origin styles and images.
* Searches are POSTs, so query text never lands in URLs, browser history
  or proxy logs. Viewer URLs contain only IDs and offsets.
* Every form carries a CSRF token (double-submit cookie).
"""

from __future__ import annotations

import functools
import html
import secrets
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .app import App
from .authz import Perm
from .errors import AccessDenied, AuthError, LexReviewError, NotFound

COOKIE = "lr_session"
CSRF_COOKIE = "lr_csrf"
E = html.escape
# Forms are rendered with this placeholder, replaced by the CSRF field at the
# end. It is random per process so document text can never contain it.
PH = "csrf-placeholder-" + secrets.token_hex(16)

CSS = """
:root{--bg:#fbfbf8;--fg:#1d1d1b;--muted:#5f5f5a;--line:#d9d8d0;--accent:#1f4e79;--hl:#ffe58a;--warn:#8a3b00;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--line:#3a3935;--accent:#8cb8e6;--hl:#6b5a12;--warn:#f0a36b;--card:#1f1f1d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header b{font-size:16px}main{max-width:1100px;margin:0 auto;padding:16px}
a{color:var(--accent)}.muted{color:var(--muted)}.warn{color:var(--warn)}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin:12px 0}
.banner{border-left:4px solid var(--warn);padding:8px 12px;background:var(--card);margin:12px 0}
pre{white-space:pre-wrap;word-wrap:break-word;font:13px/1.55 ui-monospace,Menlo,Consolas,monospace;margin:0}
mark{background:var(--hl);color:inherit;padding:0 1px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
.band{font-size:12px;padding:1px 6px;border-radius:3px;border:1px solid var(--line)}
.strong{border-color:#2e7d32}.moderate{border-color:#b08900}.weak{border-color:var(--line)}
input[type=text],input[type=password],textarea{width:100%;padding:8px;border:1px solid var(--line);border-radius:4px;background:var(--bg);color:var(--fg);font:inherit}
button{padding:7px 14px;border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:4px;font:inherit;cursor:pointer}
button.secondary{background:transparent;color:var(--accent)}
.loc{font:13px ui-monospace,Menlo,Consolas,monospace;user-select:all;background:var(--bg);border:1px dashed var(--line);padding:6px;border-radius:4px;overflow-wrap:anywhere}
img.page{max-width:100%;border:1px solid var(--line)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media (max-width:800px){.grid{grid-template-columns:1fr}}
nav.pager{display:flex;gap:12px;margin:8px 0}
"""

NOTICE = "Leads for attorney review, not conclusions. Verify every item against the source."


def _page(title: str, body: str, user: str | None = None) -> str:
    who = f'<span class="muted">{E(user)}</span> <form method="post" action="/ui/logout" style="display:inline">{PH}<button class="secondary">Log out</button></form>' if user else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(title)} - lexreview</title><link rel="stylesheet" href="/ui/static/app.css"></head><body>'
            f'<header><b><a href="/ui/" style="text-decoration:none">lexreview</a></b><span class="muted">{E(NOTICE)}</span>'
            f'<span style="margin-left:auto">{who}</span></header><main>{body}</main></body></html>')


def create_ui(app: App) -> APIRouter:
    ui = APIRouter(prefix="/ui")

    def csrf_field(request: Request) -> str:
        return f'<input type="hidden" name="csrf" value="{E(request.cookies.get(CSRF_COOKIE, ""))}">'

    def render(request: Request, title: str, body: str, user: str | None, status: int = 200) -> HTMLResponse:
        return HTMLResponse(_page(title, body, user).replace(PH, csrf_field(request)), status_code=status)

    async def form(request: Request, check_csrf: bool = True) -> dict[str, str]:
        raw = (await request.body())[:200_000].decode("utf-8", "replace")
        data = {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
        if check_csrf:
            cookie = request.cookies.get(CSRF_COOKIE, "")
            if not cookie or not secrets.compare_digest(data.get("csrf", ""), cookie):
                raise AuthError("csrf_failed")
        return data

    def principal(request: Request):
        return app.principal(request.cookies.get(COOKIE, ""))

    def username(p) -> str:
        row = app.control.execute("SELECT username FROM users WHERE user_id=?", (p.user_id,)).fetchone()
        return row[0] if row else p.user_id

    def guarded(fn):
        @functools.wraps(fn)  # keeps the signature so FastAPI binds path/query params
        async def wrapper(request: Request, **kw):
            try:
                return await fn(request, **kw)
            except AuthError:
                return RedirectResponse("/ui/login", status_code=303)
            except AccessDenied:
                return render(request, "Access denied", '<div class="card">You do not have access to this.</div>', None, 403)
            except NotFound:
                return render(request, "Not found", '<div class="card">Not found.</div>', None, 404)
            except LexReviewError as exc:
                return render(request, "Error", f'<div class="card">Request refused ({E(exc.code)}).</div>', None, 400)
        return wrapper

    # ---------------------------------------------------------------- static
    @ui.get("/static/app.css")
    async def css():
        return Response(CSS, media_type="text/css")

    # ---------------------------------------------------------------- login
    @ui.get("/login")
    async def login_form(request: Request):
        token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(24)
        body = ('<div class="card" style="max-width:420px"><h2>Sign in</h2><form method="post" action="/ui/login">'
                f'<input type="hidden" name="csrf" value="{E(token)}">'
                '<p><label>Username<input type="text" name="username" autocomplete="username"></label></p>'
                '<p><label>Password<input type="password" name="password" autocomplete="current-password"></label></p>'
                '<p><label>Authenticator code<input type="text" name="totp" inputmode="numeric" autocomplete="one-time-code"></label></p>'
                '<button>Sign in</button></form></div>')
        resp = HTMLResponse(_page("Sign in", body))
        resp.set_cookie(CSRF_COOKIE, token, httponly=False, secure=True, samesite="strict")
        return resp

    @ui.post("/login")
    async def login(request: Request):
        try:
            f = await form(request)
            token = app.login(f.get("username", ""), f.get("password", ""), f.get("totp", ""))
        except AuthError:
            return HTMLResponse(_page("Sign in", '<div class="card">Sign-in failed. <a href="/ui/login">Try again</a>.</div>'), status_code=401)
        resp = RedirectResponse("/ui/", status_code=303)
        resp.set_cookie(COOKIE, token, httponly=True, secure=True, samesite="strict")
        resp.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(24), httponly=False, secure=True, samesite="strict")
        return resp

    @ui.post("/logout")
    @guarded
    async def logout(request: Request):
        await form(request)
        app.logout(request.cookies.get(COOKIE, ""))
        resp = RedirectResponse("/ui/login", status_code=303)
        resp.delete_cookie(COOKIE)
        return resp

    # ---------------------------------------------------------------- cases
    @ui.get("/")
    @guarded
    async def home(request: Request):
        p = principal(request)
        cases = app.cases_for(p)
        rows = "".join(f'<tr><td><a href="/ui/cases/{E(c["case_id"])}">{E(c["display_name"])}</a></td>'
                       f'<td class="muted">{E(c["case_id"])}</td><td>{E(c["role"])}</td></tr>' for c in cases)
        body = ('<h2>Your cases</h2>' + (f'<table><tr><th>Case</th><th>ID</th><th>Your role</th></tr>{rows}</table>'
                                         if cases else '<p class="muted">You are not a member of any case.</p>'))
        return render(request, "Cases", body, username(p))

    def coverage_block(rep: dict, case_id: str) -> str:
        gaps = "".join(f'<tr><td><a href="/ui/cases/{E(case_id)}/docs/{E(g["doc_id"])}">{E(g["source_name"])}</a></td>'
                       f'<td class="warn">{E(g["status"])}</td><td>{E(g["explanation"])}</td></tr>' for g in rep["not_searchable"])
        low = "".join(f'<tr><td><a href="/ui/cases/{E(case_id)}/docs/{E(g["doc_id"])}">{E(g["source_name"])}</a></td>'
                      f'<td>low-confidence OCR</td><td>{E(g["reason"] or "")}</td></tr>' for g in rep["low_confidence"])
        withheld = (f'<p>{rep["documents_withheld_by_restriction"]} document(s) are withheld from you by restriction labels.</p>'
                    if rep["documents_withheld_by_restriction"] else "")
        return (f'<div class="banner"><b>Coverage:</b> {rep["documents_searchable"]} of {rep["documents_total_visible"]} visible '
                f'documents are searchable; <b>{rep["documents_not_searchable"]} are NOT</b>.{withheld}'
                + (f'<details><summary>Files not searched or needing manual review</summary><table>{gaps}{low}</table></details>' if gaps or low else "")
                + '</div>')

    def search_form(case_id: str, q: str = "") -> str:
        return (f'<form method="post" action="/ui/cases/{E(case_id)}/search" class="card">{PH}'
                f'<label>Search this case (plain English)<textarea name="q" rows="2">{E(q)}</textarea></label>'
                '<p><button>Search</button></p></form>')

    @ui.get("/cases/{case_id}")
    @guarded
    async def case_home(request: Request, case_id: str):
        p = principal(request)
        ctx = app.authorize(p, case_id, Perm.VIEW)
        rep = app.coverage(ctx)
        docs = app.store(ctx).list_documents(ctx)
        app.audit.record(ctx.user_id, "list_documents", "ok", case_id=case_id, count=len(docs))
        rows = "".join(f'<tr><td><a href="/ui/cases/{E(case_id)}/docs/{E(d["doc_id"])}">{E(d["source_name"])}</a></td>'
                       f'<td>{E(d["status"])}</td><td>{d["page_count"]}</td></tr>' for d in docs)
        body = (f'<h2>Case {E(case_id)}</h2>' + coverage_block(rep, case_id) + search_form(case_id)
                + f'<details class="card"><summary>All documents ({len(docs)})</summary><table><tr><th>Document</th><th>Status</th><th>Pages</th></tr>{rows}</table></details>')
        return render(request, "Case", body, username(p))

    @ui.post("/cases/{case_id}/search")
    @guarded
    async def search(request: Request, case_id: str):
        f = await form(request)
        p = principal(request)
        ctx = app.authorize(p, case_id, Perm.SEARCH)
        q = f.get("q", "")
        res = app.search(ctx, q, top_k=50)
        parts = [f'<h2>Search results</h2>', search_form(case_id, q), coverage_block(res["coverage"], case_id),
                 f'<p class="muted">{res["documents_searched"]} searchable documents searched. '
                 f'{res["total_passages"]} passages in {len(res["documents"])} documents matched; top {len(res["results"])} passages shown. '
                 f'Semantic backend: {E(res["semantic_backend"])}.</p>']
        if res["not_found"]:
            parts.append('<div class="card"><b>Not found in the reviewed documents.</b></div>')
        rows = []
        for h in res["results"]:
            snippet = h["snippet"] if len(h["snippet"]) <= 500 else h["snippet"][:500] + " ..."
            ocr = f'<br><span class="warn">OCR text, confidence {h["ocr_conf"]}</span>' if h["ocr"] else ""
            rows.append(
                f'<tr><td><span class="band {E(h["band"])}">{E(h["band"])}</span></td>'
                f'<td><a href="{E(h["link"])}">{E(h["source_name"])}</a><br><span class="muted">{E(h["locator"])} '
                f'&middot; chars {h["char_start"]}&ndash;{h["char_end"]}</span>{ocr}</td>'
                f'<td><pre>{E(snippet)}</pre></td>'
                f'<td>{mark_form(case_id, h["doc_id"], h["page_no"], res["query_id"])}</td></tr>')
        if rows:
            parts.append('<table><tr><th>Confidence</th><th>Location (click to open)</th><th>Passage</th><th>Your review</th></tr>'
                         + "".join(rows) + "</table>")
        return render(request, "Search", "".join(parts), username(p))

    def mark_form(case_id: str, doc_id: str, page_no: int, query_id: str | None) -> str:
        qid = f'<input type="hidden" name="query_id" value="{E(query_id)}">' if query_id else ""
        return (f'<form method="post" action="/ui/cases/{E(case_id)}/marks">{PH}{qid}'
                f'<input type="hidden" name="doc_id" value="{E(doc_id)}"><input type="hidden" name="page" value="{int(page_no)}">'
                '<button name="label" value="relevant">Relevant</button> '
                '<button class="secondary" name="label" value="not_relevant">Not relevant</button></form>')

    @ui.post("/cases/{case_id}/marks")
    @guarded
    async def add_mark(request: Request, case_id: str):
        f = await form(request)
        p = principal(request)
        ctx = app.authorize(p, case_id, Perm.MARK)
        page = int(f["page"]) if f.get("page", "").isdigit() else None
        app.mark(ctx, f.get("doc_id", ""), page, f.get("label", ""), f.get("query_id") or None)
        target = f"/ui/cases/{quote(case_id)}/docs/{quote(f.get('doc_id', ''))}" + (f"/pages/{page}" if page else "")
        return RedirectResponse(target + "?marked=1", status_code=303)

    # ---------------------------------------------------------------- viewer
    @ui.get("/cases/{case_id}/docs/{doc_id}")
    @guarded
    async def doc_first_page(request: Request, case_id: str, doc_id: str):
        return RedirectResponse(f"/ui/cases/{quote(case_id)}/docs/{quote(doc_id)}/pages/1", status_code=303)

    @ui.get("/cases/{case_id}/docs/{doc_id}/pages/{page_no}")
    @guarded
    async def viewer(request: Request, case_id: str, doc_id: str, page_no: int, hl: str | None = None):
        p = principal(request)
        ctx = app.authorize(p, case_id, Perm.VIEW)
        doc = app.view_document(ctx, doc_id)
        if doc["page_count"] == 0:
            body = (f'<h2>{E(doc["source_name"])}</h2><div class="banner warn">This file has no searchable text: '
                    f'{E(doc["status"])} ({E(doc["reason"] or "")}). Review the original manually.</div>')
            return render(request, "Document", body, username(p))
        pg = app.view_page(ctx, doc_id, page_no)
        text = pg.text
        start = end = None
        if hl:
            try:
                a, b = (int(x) for x in hl.split("-", 1))
                if 0 <= a < b <= len(text):
                    start, end = a, b
            except ValueError:
                pass
        if start is not None:
            shown = f'{E(text[:start])}<mark id="hl">{E(text[start:end])}</mark>{E(text[end:])}'
        else:
            shown = E(text)
        base = f"/ui/cases/{quote(case_id)}/docs/{quote(doc_id)}/pages"
        nav = '<nav class="pager">' + (f'<a href="{base}/{page_no - 1}">&larr; previous</a>' if page_no > 1 else "") \
            + f'<span class="muted">page unit {page_no} of {doc["page_count"]}</span>' \
            + (f'<a href="{base}/{page_no + 1}">next &rarr;</a>' if page_no < doc["page_count"] else "") + "</nav>"
        loc_text = (f'{doc["source_name"]} | doc {doc_id} | {pg.locator}'
                    + (f' | chars {start}-{end}' if start is not None else "")
                    + (f' | OCR confidence {pg.ocr_conf}' if pg.ocr else ""))
        link = f'{base}/{page_no}' + (f'?hl={start}-{end}#hl' if start is not None else "")
        location = (f'<div class="card"><b>Location</b> (select to copy)<div class="loc">{E(loc_text)}</div>'
                    f'<p class="muted">Direct link: <a href="{E(link)}">{E(link)}</a></p>'
                    + (f'<p class="warn">This page text came from OCR (confidence {pg.ocr_conf}). Compare with the page image.</p>' if pg.ocr else "")
                    + (f'<p class="muted">Page units for {E(doc["kind"])} files are defined by the locator above, not printed page numbers.</p>' if doc["kind"] not in ("pdf", "image") else "")
                    + "</div>")
        marks = app.store(ctx).marks_for(ctx, doc_id)
        mark_rows = "".join(f'<li>{E(m["label"])} by {E(m["user_id"])}' + (f' (page {m["page_no"]})' if m["page_no"] else "") + '</li>' for m in marks)
        review = (f'<div class="card"><b>Review</b>{mark_form(case_id, doc_id, page_no, None)}'
                  + (f'<ul>{mark_rows}</ul>' if mark_rows else '<p class="muted">No marks yet.</p>') + '</div>')
        image = (f'<div><h3>Original page</h3><img class="page" alt="Original page image" src="{base}/{page_no}/image"></div>'
                 if doc["kind"] in ("pdf", "image") else "")
        body = (f'<h2>{E(doc["source_name"])}</h2>' + location + nav
                + f'<div class="grid"><div class="card"><h3>Extracted text</h3><pre>{shown}</pre></div>{image}</div>'
                + nav + review)
        return render(request, "Document", body, username(p))

    @ui.get("/cases/{case_id}/docs/{doc_id}/pages/{page_no}/image")
    @guarded
    async def page_image(request: Request, case_id: str, doc_id: str, page_no: int):
        p = principal(request)
        ctx = app.authorize(p, case_id, Perm.VIEW)
        png = app.page_image(ctx, doc_id, page_no)
        if png is None:
            raise NotFound()
        return Response(png, media_type="image/png")

    return ui
