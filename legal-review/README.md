# lexreview — citation-backed discovery review assistant

**Status: development build, Phases 1-2 of 5 done (ingestion + security
foundation; hybrid search + reviewer web app). Synthetic data only. Not
approved for real client data.** Decisions are logged in [DECISIONS.md](DECISIONS.md).

lexreview helps attorneys, paralegals and reviewers organize large discovery
productions. It produces **leads for human review**, never conclusions. Every
passage it shows is tied to a document ID, a page (or explicit locator), and
exact text that code has verified exists at that location.

Before any real data is used, read [SECURITY.md](SECURITY.md) (residual risks
and open items) and [PENTEST_AND_COUNSEL_REVIEW.md](PENTEST_AND_COUNSEL_REVIEW.md).
Nothing in this repository claims the system is "secure" or "leak-proof".

## What Phases 1-2 do

| Capability | Where |
|---|---|
| Parse PDF (text + OCR), DOCX, XLSX, email (.eml, incl. attachments), images, text | `src/lexreview/ingest/formats.py` |
| Parsers run in a sandboxed subprocess (rlimits, timeout, `unshare -n`, no core dumps, private tmp) | `ingest/sandbox.py`, `ingest/worker.py` |
| Page-true text with explicit locators; page-bounded chunks with char offsets | `casestore.py`, `chunking.py` |
| Coverage ledger: every file ends as indexed / low-confidence / ocr_failed / corrupted / password_protected / unsupported / too_large / rejected_unsafe / timeout / duplicate | `coverage.py` |
| Citation verifier: quote must exist on the cited page (fabrications rejected) | `citations.py` |
| Per-case SQLCipher DB + AES-256-GCM blobs, per-case DEK wrapped by per-case KEK in a KMS; crypto-shred | `casestore.py`, `crypto.py`, `kms/` |
| argon2id + TOTP MFA, lockout, hashed server-side sessions | `auth.py` |
| Per-case RBAC + document restriction labels, enforced inside SQL; sealed access contexts | `authz.py`, `app.py` |
| Append-only HMAC hash-chained audit log with external anchoring | `audit.py` |
| Content-free application logging | `safelog.py` |
| Default-deny in-process egress guard (loopback only to allowlisted ports) | `netguard.py` |
| Approved-synthetic-data guard (signed manifest + hashes; no bypass) | `datasafety.py` |
| Permission-checked, watermarked, audited exports (CSV/PDF) | `export.py` |
| JSON API (TLS 1.3 only, strict headers, CSRF) and CLI | `api.py`, `cli.py` |
| **Phase 2:** hybrid search: BM25 (SQLite FTS5) + semantic (per-case LSA, exact cosine), reciprocal rank fusion | `search/hybrid.py`, `search/embed.py` |
| Permission filtering inside both the SQL and the vector mask, before ranking | `casestore.py`, `search/embed.py` |
| Every result re-verified against stored page text; cited with doc, page/locator, char range and a viewer link | `search/hybrid.py` |
| Confidence bands from absolute evidence (term coverage + semantic similarity + OCR quality); "Not found in the reviewed documents." | `search/hybrid.py` |
| Reviewer web app: search, jump-to-passage viewer with highlight, copyable location, original page image (rendered in the sandbox), Relevant/Not relevant marks | `web.py` |
| Queries stored only inside the encrypted case DB; audit keeps a keyed digest | `casestore.py`, `app.py` |

Not yet built (later phases): extraction/timeline (3), cited Q&A and
instruction-driven ranking with the local model (4), legal-authority leads
for Ohio and Michigan with human-approved outbound queries (5).

## Quick start (synthetic data)

Requirements: Python 3.11+, Tesseract 5 (`apt-get install tesseract-ocr`),
Linux (for `unshare -n` parser network isolation).

```bash
cd legal-review
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements-dev.lock && pip install --no-deps -e .

# Secrets are passed by reference only (env:NAME or file:/path), never inline.
export LEXREVIEW_DATA_ROOT=$PWD/.lexreview-data
export LEXREVIEW_APPROVED_DATA_DIR=$PWD/testdata/synthetic
export LEXREVIEW_MANIFEST_KEY_REF=env:LR_MANIFEST_KEY
export LEXREVIEW_DEV_KMS_MASTER_REF=env:LR_DEV_KMS_MASTER    # dev-only KMS
export LR_MANIFEST_KEY=$(python -c "import os;print(os.urandom(32).hex())")
export LR_DEV_KMS_MASTER=$(python -c "import os;print(os.urandom(32).hex())")

python scripts/make_synthetic_corpus.py --out testdata/synthetic
lexreview init
lexreview bootstrap-admin --username admin          # prints a TOTP secret ONCE
lexreview login --username admin                    # password + TOTP
lexreview case-create --name "Synthetic matter"     # prints case id
lexreview user-add --username pat                   # prints user id + TOTP secret
lexreview case-add-member <case> <user_id> paralegal
# log in as pat, then:
lexreview ingest <case> testdata/synthetic/docs
lexreview coverage <case>
lexreview docs <case>
lexreview page <case> <doc_id> <page>
lexreview verify-quote <case> <doc_id> <page> "exact passage"
lexreview search <case> "find everything about temperature excursions in April"
lexreview mark <case> <doc_id> relevant --page 4
lexreview export <case> coverage pdf --out ./exports

# Reviewer web app (TLS 1.3 only). Use certificates from the firm PKI.
lexreview serve --port 8443 --cert cert.pem --key key.pem
# then open https://<host>:8443/ui/
```

In the web app, every search result's location is a link: it opens the page
with the passage highlighted, shows the location line (document | doc ID |
page or locator | character range | OCR confidence) ready to copy, a direct
link to that exact spot, and the original page image for PDFs and scans.

The sysadmin creates users and cases but has **no access to case data**
unless explicitly added as a member.

## Tests

```bash
python -m pytest -q          # ~2 minutes; generates the synthetic corpus once
./scripts/security_checks.sh # pip-audit, bandit, SBOM, Trojan Source scan
```

Adversarial suites: `test_isolation.py` (cross-case, forged contexts,
restriction labels, crypto-shred, no plaintext at rest), `test_citations.py`
(fabricated / altered / wrong-page quotes), `test_ingest.py` (corrupted,
password-protected, zip bomb, decompression bomb, huge, timeout, memory
limit), `test_logging.py` (canary strings never reach logs), `test_network.py`
(egress guard, local-proxy bypass, parser network namespace),
`test_api_tls.py` (TLS 1.2 refused, headers, CSRF, error leakage),
`test_search.py` (verified citations, permission-filtered retrieval,
cross-case search, not-found, FTS syntax injection, recall),
`test_web.py` (XSS from hostile documents, CSRF, jump-to-passage),
`test_datasafety.py`, `test_audit.py`, `test_auth.py`, `test_export.py`.

Prompt-injection tests start in Phase 4 (there is no model call yet); the
injection documents are already in the corpus and are ingested as inert text.
Recall evaluation (`test_search.py::test_recall_on_labeled_synthetic_set`)
prints a report; latest run: temperature-excursions instruction 13/13
known-relevant documents found, insurance-claim instruction 5/6 (missed: a
scanned delivery receipt that never mentions the claim). The labeled set is
small and synthetic; these numbers do not predict performance on real data.

## Layout

```
legal-review/
  src/lexreview/        application code
  tests/                pytest suites (synthetic corpus generated per run)
  scripts/              corpus generator, security checks
  deploy/               example network egress policy
  THREAT_MODEL.md  SECURITY.md  PENTEST_AND_COUNSEL_REVIEW.md
  requirements.lock  requirements-dev.lock   (hash-pinned)
```
