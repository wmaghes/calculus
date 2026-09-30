# Security notes, residual risks and open items

This system is **not** claimed to be secure or leak-proof. It has controls
that reduce specific risks, tests that exercise those controls, and the known
gaps listed below. It is a development build that refuses to read anything
except the signed synthetic test corpus.

## Controls in place (Phase 1)

- **At rest:** per-case SQLCipher 4 (AES-256) database and AES-256-GCM blobs
  (AAD binds each blob to its case and document). The DEK comes from
  `os.urandom` and is stored only wrapped by a per-case KEK in the KMS.
  HKDF-derived subkeys per purpose. Owner-only file modes (umask 077).
- **Crypto-shred:** deleting a case destroys its KEK in the KMS, then
  overwrites the wrapped DEK and deletes the files. Test: a restored
  "backup" of the case files cannot be opened.
- **In transit:** API serves TLS 1.3 only (a TLS 1.2 handshake is refused in tests).
- **AuthN:** argon2id; TOTP MFA required (config refuses to disable it in
  production); single-use TOTP codes; lockout after 5 failures; 256-bit
  session tokens stored as SHA-256; 30-min idle / 8-h absolute expiry.
- **AuthZ:** per-case roles; restriction labels need explicit grants (even
  case admins); visibility enforced inside SQL; HMAC-sealed access contexts;
  sysadmin has no implicit case access.
- **Audit:** append-only, HMAC hash chain; records logins, access denials,
  ingestion per document, page and document views, coverage reports,
  exports (with file SHA-256), grants, restriction changes, case destruction.
  No content, file names or query text.
- **Egress:** in-process default-deny guard on DNS and connect; loopback
  only to allowlisted ports; parsers in an empty network namespace.
- **Logging:** content-free by construction (see `safelog.py`), verified
  with canary strings.
- **Parsing:** subprocess with CPU/memory/file-size/open-file limits,
  timeout, no core dumps, private tmp dir removed afterwards; zip-bomb and
  image-bomb limits; magic-byte detection (extensions ignored).
- **Supply chain:** hash-pinned locks, pip-audit (no known vulnerabilities
  at time of writing), bandit (clean after triage), SBOM, Trojan Source scan.

## Controls added in Phase 2

- Search results are permission-filtered inside the SQL (FTS) and the
  vector mask before ranking; restricted documents never appear in results,
  document counts or "documents searched".
- Every result's snippet is re-checked against the stored page text at its
  offsets before display (integrity failures are counted and dropped).
- User text never reaches FTS5 as syntax (quoted terms only).
- Vector index and LSA model are per case, serialized without pickle, and
  sealed with the case's vector key (AES-256-GCM).
- Query text is stored only in the encrypted case DB; the audit log has an
  HMAC digest and the query ID. Searches are POSTs, so queries never land in
  URLs, history or proxy logs.
- Web UI: no JavaScript; CSP without script-src; all document text escaped;
  no links or images generated from document content; CSRF on every form;
  page images rendered from the original inside the parser sandbox, never
  cached (Cache-Control: no-store).

## Issues found and fixed during Phase 1

1. **Access-context seal bypass.** The first design sealed contexts with a
   constant, so `dataclasses.replace(ctx, case_id=other)` produced a valid
   context for another case. Fixed: seal is an HMAC over every field.
   Regression test in `test_isolation.py`.
2. **Egress guard bypass via loopback proxy.** The guard trusted all
   loopback traffic, and an HTTP client honoured `HTTPS_PROXY` pointing to a
   local forward proxy, so traffic left the host. Fixed: loopback allowed
   only to explicitly allowlisted ports. Regression test in `test_network.py`.
3. **World-readable data files.** SQLCipher created `case.db`/`control.db`
   as 0644 (content was encrypted). Fixed with umask 077 plus a test.
4. **Bidirectional control characters in source** (Trojan Source pattern)
   were introduced by an editing tool into a regex. Replaced with escapes;
   now scanned in `security_checks.sh`.
5. **Decompression bomb accepted.** Pillow only raises above 2× its pixel
   limit. The limit is now enforced before decoding.

## Issues found and fixed during Phase 2

6. **Deadlock** between the index cache and the store cache (non-reentrant
   lock); the first search after ingestion hung. Fixed with a re-entrant lock.
7. **CPU-limit kills reported as generic parse errors.** A parser killed by
   the CPU-seconds rlimit now appears in coverage as `timeout`.
8. **CSRF placeholder could be injected by document text.** A fixed
   `{csrf}` marker was replaced after rendering, so a document containing it
   would have shown the user's token in page text. Now a random per-process
   placeholder.
9. **Over-confident bands.** Bands based on rank position labelled an
   unrelated query's hits "strong". Now based on absolute evidence, with a
   semantic similarity floor and an out-of-vocabulary discount.

## Residual risks (known, not solved)

| # | Risk | Notes / mitigation direction |
|---|---|---|
| R1 | **Plaintext in memory.** While a case is open, its DEK and decrypted pages are in process memory; swap or a memory dump exposes them. | Disable swap or use encrypted swap; restrict ptrace; short-lived worker processes. |
| R2 | **Parser sandbox is partial.** rlimits + network namespace only. No seccomp, no filesystem isolation (the worker can read files the service user can read). A parser RCE could read other cases' *encrypted* files and the dev KMS directory. | Production: nsjail/bubblewrap/gVisor with read-only root, no access to data root, seccomp. **Pentest priority.** |
| R3 | **Parser temp files.** OCR page images are written to a per-job temp dir (under `data_root/tmp`) in plaintext for the duration of the job. | Mount `data_root/tmp` as tmpfs (RAM), or encrypted scratch. |
| R4 | **Dev KMS is not an HSM.** KEKs are files sealed under a master key from an env/file secret. Overwrite-and-unlink does not guarantee erasure on SSD/COW/journaled storage. | Production must use Vault Transit (adapter exists, tested only against a mock) or an HSM. |
| R5 | **Crypto-shred scope.** KEK destruction makes wrapped DEKs unusable, but: a DEK already in memory remains until process exit; KMS backups that still contain the KEK defeat shredding; exports already made are plaintext outside the system. | KMS backup policy; restart after destruction; export register. |
| R6 | **Sysadmin with host root + KMS access** can read everything. Audit can be truncated at the tail unless anchored externally. | Separation of duties between host admins and KMS admins; ship audit anchors to WORM/SIEM on a schedule. |
| R7 | **Authorized users can exfiltrate** by copy/paste, screenshots or exports. Watermarks and audit deter and trace; they do not prevent. | Export volume alerts (open item); DLP on endpoints. |
| R8 | **Metadata in the clear.** The audit log is plaintext JSON (IDs, actions, timestamps, counts). File sizes and document counts are visible from the encrypted store's file sizes. | Encrypt audit at rest in production if IDs are considered sensitive. |
| R9 | **OCR can be wrong yet "verified".** The verifier checks quotes against *stored* text; if OCR misread the page, a misread quote still verifies. | OCR confidence is shown per page; low-confidence pages flagged; reviewers must check the page image *(viewer arrives in Phase 2)*. |
| R10 | **DOCX has no real pages.** Locators are Word's last-rendered breaks (approximate), explicit breaks, or paragraph ranges. Citations to DOCX say which. | Optional LibreOffice rendering to PDF (larger attack surface) if true page numbers are required. |
| R11 | **Unsupported formats**: legacy .doc/.xls, Outlook .msg, .mbox, ZIP archives, PST. Recorded as `unsupported` in coverage (never silent), but not searchable. | Add parsers with licensing review (common .msg library is GPL). |
| R12 | **In-process egress guard is not a firewall.** Native code, subprocesses, or ctypes can bypass it. | Network-layer default-deny is required (`deploy/nftables.example`). |
| R13 | **Performance.** OCR is single-threaded per file; a noisy 1-page scan took ~84 s on 4 CPU cores. Thousands of scanned pages will take hours. Ingestion is sequential. | Parallel worker pool with the same sandboxing. |
| R14 | **Duplicate detection is exact (SHA-256)**; near-duplicates are indexed separately. | Near-dup detection in Phase 2/3 if wanted. |
| R15 | Formula cells in XLSX show cached values; never-calculated workbooks show blanks. | Noted in document metadata. |
| R16 | **Semantic model is LSA, not neural.** It handles co-occurrence but misses many paraphrases, so recall on real productions will be lower than keyword+neural hybrids. | Provision a neural embedding model offline, pinned by SHA-256 (open item). |
| R17 | **Restricted documents shape the case's LSA model.** The model is trained on all of a case's chunks; a user without a grant cannot see restricted text or hits, but the term associations learned from it slightly influence their semantic ranking of visible documents. | Train separate models per restriction level if counsel considers this material. |
| R18 | **Index rebuild cost.** The semantic index is rebuilt over the whole case after each ingestion run; very large cases will make this slow. Exact (brute-force) search uses ~4 bytes x 200 dims per chunk of RAM while a case is open. | Incremental indexing / per-batch models. |
| R19 | **Query history is retained indefinitely** in the encrypted case DB (work product). | Retention policy (counsel item). |
| R20 | The page viewer renders original pages in the sandbox on every view (no cache); on huge scans this is slow. | Pre-render into encrypted blobs if needed. |

## Open items before any real data

0. Neural embedding model provisioned offline and pinned by hash (R16).
1. OIDC/SAML adapter to the firm IdP with enforced MFA (local TOTP is dev-grade).
2. Vault Transit (or HSM) integration test against a real instance; key policies; KMS backup/destroy procedure.
3. Production parser sandbox (see R2) and tmpfs scratch (R3).
4. Network-layer default-deny egress, verified from inside the deployment.
5. Scheduled audit anchoring to write-once storage; alerting on denials, lockouts, export volume.
6. TLS certificates from the firm PKI; HSTS preload decision; reverse proxy config.
7. Backup design: only encrypted files; restore test; interaction with crypto-shred and litigation holds (see counsel list).
8. Independent penetration test and counsel review (`PENTEST_AND_COUNSEL_REVIEW.md`).
9. A deliberate code change to enable non-synthetic data (there is no flag).

## Reporting
Report suspected vulnerabilities privately to the project owner. Do not
include document content in reports.
