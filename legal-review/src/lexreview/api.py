"""HTTP API (Phase 1: minimal, JSON only).

* Session token from an HttpOnly, Secure, SameSite=Strict cookie or an
  `Authorization: Bearer` header. Cookie-authenticated state-changing
  requests also need a matching X-CSRF-Token header (double submit).
* Strict security headers on every response (CSP default-src 'none', no
  framing, no caching, no referrer).
* Errors are generic JSON reason codes. Exception text never reaches clients.
* Served only over TLS 1.3 (see serve()).
"""

from __future__ import annotations

import secrets
import ssl

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .app import App
from .authz import Perm
from .citations import Rejected, verify_quote
from .errors import AccessDenied, AuthError, LexReviewError, NotFound
from .safelog import log_event

SECURITY_HEADERS = {
    # No script-src at all: the UI has no JavaScript. Styles and page images
    # are same-origin only.
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
COOKIE = "lr_session"
CSRF_COOKIE = "lr_csrf"


class LoginBody(BaseModel):
    username: str
    password: str
    totp: str | None = None


class SearchBody(BaseModel):
    query: str
    top_k: int = 50


class MarkBody(BaseModel):
    doc_id: str
    page: int | None = None
    label: str
    query_id: str | None = None


class QuoteBody(BaseModel):
    doc_id: str
    page: int
    quote: str


def create_api(app: App) -> FastAPI:
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @api.middleware("http")
    async def headers(request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 - never leak exception text
            log_event("api_error", level=40, error_type=type(exc).__name__)
            response = JSONResponse({"error": "internal_error"}, status_code=500)
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response

    @api.exception_handler(LexReviewError)
    async def lr_error(_request: Request, exc: LexReviewError):
        status = 401 if isinstance(exc, AuthError) else 403 if isinstance(exc, AccessDenied) else 404 if isinstance(exc, NotFound) else 400
        return JSONResponse({"error": exc.code if status != 403 else "access_denied"}, status_code=status)

    def principal(request: Request, state_changing: bool = False):
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return app.principal(auth[7:].strip())
        token = request.cookies.get(COOKIE)
        if not token:
            raise AuthError()
        if state_changing:
            sent, cookie = request.headers.get("x-csrf-token", ""), request.cookies.get(CSRF_COOKIE, "")
            if not cookie or not secrets.compare_digest(sent, cookie):
                raise AuthError("csrf_failed")
        return app.principal(token)

    @api.post("/login")
    def login(body: LoginBody):
        token = app.login(body.username, body.password, body.totp)
        resp = JSONResponse({"ok": True, "token": token})
        resp.set_cookie(COOKIE, token, httponly=True, secure=True, samesite="strict")
        resp.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(24), httponly=False, secure=True, samesite="strict")
        return resp

    @api.post("/logout")
    def logout(request: Request):
        p = principal(request, state_changing=True)  # noqa: F841 - validates CSRF
        token = request.cookies.get(COOKIE) or request.headers.get("authorization", "")[7:]
        app.logout(token)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE)
        return resp

    @api.get("/cases/{case_id}/coverage")
    def coverage(case_id: str, request: Request):
        ctx = app.authorize(principal(request), case_id, Perm.VIEW)
        return app.coverage(ctx)

    @api.get("/cases/{case_id}/documents")
    def documents(case_id: str, request: Request):
        ctx = app.authorize(principal(request), case_id, Perm.VIEW)
        docs = app.store(ctx).list_documents(ctx)
        app.audit.record(ctx.user_id, "list_documents", "ok", case_id=case_id, count=len(docs))
        return {"documents": docs}

    @api.get("/cases/{case_id}/documents/{doc_id}/pages/{page_no}")
    def page(case_id: str, doc_id: str, page_no: int, request: Request):
        ctx = app.authorize(principal(request), case_id, Perm.VIEW)
        pg = app.view_page(ctx, doc_id, page_no)
        # Returned as JSON data; clients must render it as text, never HTML.
        return {"doc_id": pg.doc_id, "page": pg.page_no, "locator": pg.locator, "text": pg.text,
                "ocr": pg.ocr, "ocr_conf": pg.ocr_conf}

    @api.post("/cases/{case_id}/verify-quote")
    def verify(case_id: str, body: QuoteBody, request: Request):
        ctx = app.authorize(principal(request, state_changing=True), case_id, Perm.VIEW)
        res = verify_quote(app.store(ctx), ctx, body.doc_id, body.page, body.quote)
        app.audit.record(ctx.user_id, "verify_quote", "ok" if not isinstance(res, Rejected) else "rejected",
                         case_id=case_id, target=body.doc_id)
        if isinstance(res, Rejected):
            return {"verified": False, "reason": res.reason}
        return {"verified": True, "doc_id": res.doc_id, "page": res.page_no, "locator": res.locator,
                "char_start": res.char_start, "char_end": res.char_end, "text": res.exact_text}

    @api.post("/cases/{case_id}/search")
    def search(case_id: str, body: SearchBody, request: Request):
        ctx = app.authorize(principal(request, state_changing=True), case_id, Perm.SEARCH)
        return app.search(ctx, body.query, body.top_k)

    @api.post("/cases/{case_id}/marks")
    def mark(case_id: str, body: MarkBody, request: Request):
        ctx = app.authorize(principal(request, state_changing=True), case_id, Perm.MARK)
        return {"mark_id": app.mark(ctx, body.doc_id, body.page, body.label, body.query_id)}

    from .web import create_ui

    api.include_router(create_ui(app))
    return api


def tls13_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain(certfile, keyfile)
    return ctx


def build_server(app: App, host: str, port: int, certfile: str, keyfile: str):
    """uvicorn server that only speaks TLS 1.3."""
    import uvicorn

    config = uvicorn.Config(create_api(app), host=host, port=port, ssl_certfile=certfile, ssl_keyfile=keyfile,
                            log_config=None, access_log=False, server_header=False, date_header=False)
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_3
    return uvicorn.Server(config)
