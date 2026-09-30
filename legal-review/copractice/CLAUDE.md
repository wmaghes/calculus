# Copractice: privacy-first precedent retrieval

Copractice is the precedent-research tab of lexreview. It finds relevant case
law in a LOCAL index of public opinions and returns verified citations.

## The privacy rule (non-negotiable)
Public case law is the only thing indexed. Client facts never leave the
user's environment except as an anonymized issue summary that the user has
approved, sent to a zero-retention model API (or a local model). Nothing
else leaves: no opinion text, query text or client text goes to an embedding
API or any other external service.

## Architecture decisions
- Python 3.12, FastAPI backend, Postgres 16 + pgvector (metadata, full-text
  and vectors in one database), React (Vite) frontend (step 5), Docker Compose.
- Only PUBLIC opinions go into this Postgres database. Client matter content
  stays in lexreview's per-case encrypted store (SQLCipher, per-case keys).
  The `matters` table here holds only an id, a title chosen by the user and
  a reference to the lexreview case; no facts. If matter content is ever
  stored here, it must be encrypted per matter first (lexreview KMS).
- Ingest: CourtListener public bulk data. Case metadata from the
  opinion-clusters and dockets CSVs (streamed, never fully downloaded);
  opinion text from the per-case Harvard Caselaw PDFs CourtListener hosts
  (`harvard_pdf/<cluster_id>.pdf`), parsed in a sandboxed subprocess.
  Jurisdictions are config (`ingest/jurisdictions.json`).
- Embeddings run locally only (sentence-transformers, bge-small-en-v1.5,
  384 dims) from a local model directory; never downloaded at request time.
  A `dev-hash` embedder exists ONLY for tests and environments without the
  weights; it is not semantic and is labelled as such in every response.
- Hybrid search: Postgres full-text (websearch_to_tsquery, ts_rank_cd) +
  pgvector cosine (HNSW), merged with reciprocal rank fusion (k=60).
  Optional cross-encoder rerank: not yet built.
- LLM calls (step 7+) go through `backend/app/llm_client.py` only; all text
  passes `backend/app/privacy/redact.py` first; every outbound payload is
  written to `audit_log`.
- `audit_log` is append-only (UPDATE/DELETE blocked by trigger) and
  hash-chained. Every outbound network call (including ingest downloads) is
  logged with destination and payload hash, never payload text.
- No secrets in code; configuration via `.env` (see `.env.example`).

## Working rules (from the owner)
- Small steps; run tests after each and report results before moving on.
- Ask before adding any dependency that makes network calls with user data.
- UI shows: "Research aid for attorneys, not legal advice."
