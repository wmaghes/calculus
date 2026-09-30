# Threat model

Scope: lexreview as designed for single-tenant on-prem deployment at a law
firm, holding discovery productions that must be assumed **sealed and
privileged**. This document covers the whole planned system. Controls marked
*(Phase N)* are not built yet.

## Assets

| Asset | Why it matters |
|---|---|
| Source documents and extracted text | Privileged, sealed, PII. Disclosure can breach protective orders and privilege. |
| Derived data: chunks, FTS index, embeddings *(P2)*, entities/timelines *(P3)*, answers *(P4)* | Reconstructs the source. Treated as equally sensitive. |
| Queries and reviewer marks | Reveal attorney strategy (work product). |
| Case membership / restriction labels | Who may see what; tampering = unauthorized access. |
| Keys: KEKs (KMS), DEKs (wrapped), audit HMAC key, session tokens | Compromise defeats encryption or accountability. |
| Audit log | Evidence of who accessed what; must resist tampering. |

## Actors

External attacker (network, stolen media or backups); malicious or curious
insider (reviewer, attorney, sysadmin); hostile document author (opposing
party planting content in a production); compromised dependency or model
weights; the model provider (only if a hosted backend is ever enabled).

## Trust boundaries

1. Browser/CLI ↔ API (TLS 1.3, session auth).
2. API/service ↔ per-case store (sealed `CaseAccessContext`, one DB and key per case).
3. Service ↔ parser sandbox (untrusted file bytes in, JSON out).
4. Service ↔ KMS (Vault/HSM; dev-only file KMS).
5. Service ↔ model backend *(P4)* (localhost only, no tools).
6. Service ↔ legal-authority gateway ↔ internet *(P5)* (allowlisted hosts, human-approved queries).

## Threats and controls (STRIDE by area)

### 1. Data theft (external)
| Threat | Control | Status |
|---|---|---|
| Stolen disk, backup or snapshot | SQLCipher (AES-256) per case; AES-256-GCM blobs; DEK wrapped by KMS; owner-only file modes | Built, tested (`test_no_plaintext_at_rest`, `test_data_files_owner_only`) |
| Sniffing | TLS 1.3 only on the API | Built, tested (TLS 1.2 handshake refused) |
| Malicious file exploits a parser | Separate process, rlimits, timeout, `unshare -n`, no core dumps, stderr discarded, zip/image bomb limits | Built, tested. **Not** a full sandbox (no seccomp, shared filesystem view) |
| XSS / CSRF / clickjacking | JSON-only API; CSP `default-src 'none'`; frame-ancestors none; SameSite=Strict cookies + CSRF token | Built for the Phase 1 API. UI arrives in Phase 2 |
| IDOR on doc IDs | Random IDs; every lookup filtered by case store + visibility SQL; "not found" identical for "exists but hidden" | Built, tested |
| SSRF / document-triggered fetches | No component fetches URLs from documents; egress guard | Built (guard), tested |

### 2. Insider misuse
| Threat | Control | Status |
|---|---|---|
| Reviewer browses cases they are not on | Membership check in `authorize`; denial audited | Built, tested |
| Reviewer sees attorneys'-eyes-only docs | Restriction labels need explicit grants; applied inside SQL; withheld count only | Built, tested |
| Sysadmin reads case data | Sysadmin role has no case access by default; data encrypted under KMS-held keys | Built. A sysadmin with host root **and** KMS access can still read everything (residual) |
| Bulk export | EXPORT permission; watermark with user/time/export id; audit with SHA-256 of file | Built, tested. Volume alerting: open item |
| Audit tampering | HMAC hash chain; key held via KMS; external anchor for truncation | Built, tested. Scheduled anchoring: deployment item |
| Forged or modified access context in code | Context sealed with HMAC over all fields | Built, tested (found and fixed a bypass during Phase 1) |

### 3. Prompt injection *(model arrives in Phase 4)*
Documents are untrusted. The corpus already contains injection documents
(exfiltration URLs, markdown image beacons, fake citations, "reveal system
prompt"). Planned controls: no tools and no network for the model; nonce-
delimited document blocks; strict JSON output; every quote verified by
`citations.verify_quote` before display; unverified claims dropped; output
rendered as escaped text with links defanged and images removed. Phase 1
already ensures injected text is stored as inert data, HTML/script stripped
from emails, terminal control characters stripped from CLI output, and CSV
formula injection neutralized in exports.

### 4. Cross-case leakage
One DB, one blob dir, one DEK/KEK per case. No global index or cache.
Stores refuse contexts for other cases. Tested: cross-case authorize, doc-ID
access, store/context mismatch, API cross-case, quote verification across
cases, crypto-shred of one case leaving others intact.

### 5. Model-provider exposure
Default model backend will be local (localhost, allowlisted port). No hosted
adapter exists. If one is added it must refuse to start without an explicit
ZDR attestation, and its host must be added to the egress allowlist.

### 6. Supply chain
Minimal runtime dependency set (13 direct packages). Hash-pinned locks,
`pip-audit`, `bandit`, CycloneDX SBOM, Trojan Source scan
(`scripts/security_checks.sh`). Permissive licenses (PyMuPDF avoided: AGPL).
Model/embedding weights *(P2/P4)* will be pinned by SHA-256 and loaded offline.

### 7. Integrity: silent gaps and fabricated citations
Coverage ledger for every file, surfaced with every output. Citation
verifier with documented normalization. "Not found in the reviewed
documents" when nothing verifies *(P4)*. Legal authority re-fetched from
the source by ID *(P5)*.

### 8. Logging and error leakage
Structured event logger with field allowlist and value filter; all other log
records rewritten; tracebacks reduced to exception type; uncaught exceptions
print type only; API errors are reason codes; parser stderr discarded;
uvicorn access log disabled. Tested with canary strings.

## Out of scope / assumptions
Endpoint security of reviewers' machines; physical security; the firm's IdP
and MFA enrolment process; OS hardening; backup systems (must store only the
encrypted files; KMS backups must follow the firm's key-destruction policy).
