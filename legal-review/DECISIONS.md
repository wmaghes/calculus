# Decisions log

| Date | Decision | By |
|---|---|---|
| 2026-09-30 | Code lives in `legal-review/` on branch `claude/legal-doc-review-secure-boexep`. | Project owner |
| 2026-09-30 | Model backend: self-hosted local model behind a swappable interface; deterministic stub for tests. | Project owner |
| 2026-09-30 | Deployment target: single-tenant on-prem; Vault Transit or PKCS#11 HSM behind the KMS interface. | Project owner |
| 2026-09-30 | Legal-source clients are built and tested against recorded fixtures; live verification happens in the firm's environment (sandbox blocks the sites). | Project owner |
| 2026-09-30 | **Phase 5 target jurisdictions: Ohio and Michigan** (plus federal sources that bind them, e.g. the 6th Circuit). Planned sources: CourtListener (Ohio and Michigan state courts, 6th Cir., federal district courts in OH/MI), Ohio Revised Code / Ohio Administrative Code (codes.ohio.gov), Michigan Compiled Laws (legislature.mi.gov), govinfo / eCFR for federal statutes and regulations. | Project owner |
| 2026-09-30 | **Every search sent to an outside legal database requires a person to approve the exact outbound query text first.** No automatic sending, including model-suggested terms. | Project owner |
| 2026-09-30 | **Citations work like an app link:** every result opens the source page with the passage highlighted and its full location (document, doc ID, page or locator, character range) shown and copyable. DOCX keeps paragraph/Word-layout locators (no LibreOffice conversion). | Project owner |
| 2026-09-30 | Semantic search uses an offline per-case LSA model until neural embedding weights can be provisioned offline and pinned by hash (Hugging Face is unreachable from the development sandbox). | Implementation, flagged for owner |
