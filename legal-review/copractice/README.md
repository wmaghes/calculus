# Copractice: privacy-first precedent research

The precedent-research tab of lexreview. Describe a legal issue; Copractice
returns relevant passages from a **local** index of public court opinions,
each with case name, citation, court, date and a link to the full opinion.

**Research aid for attorneys, not legal advice.** Good-law status is not
checked; confirm every authority with a citator.

Status: build-plan steps 1-4 (scaffold, schema, ingest, search API). No LLM,
no redaction, no frontend yet (steps 5-10).

## Data flow and privacy

```
CourtListener public bulk files ──(ingest, HTTPS, logged)──▶ local Postgres (public opinions only)
                                                                   │
issue statement ──▶ POST /search (local) ──▶ full-text + local embeddings + RRF ──▶ results
```

- Only public opinions are indexed. Nothing about a client matter is stored
  here beyond a matter title and a pointer to the lexreview case; client
  documents stay in lexreview's per-case encrypted store.
- Search runs entirely on this machine: the issue statement is embedded
  locally and matched in local Postgres. No query, opinion text or client
  text is sent to any external service.
- The only outbound traffic is the ingest downloading public bulk files from
  CourtListener. Every request is written to `audit_log` (destination +
  hash), which is append-only and hash-chained.
- Searches are audited without their text (only size and result count).
- The API has **no authentication yet**. It listens on loopback only and
  must sit behind lexreview's authenticated app before multi-user use.

## Data sources

| What | Where | Notes |
|---|---|---|
| Courts, dockets, case metadata, citations | CourtListener bulk CSVs (`courts-`, `dockets-`, `opinion-clusters-`, `citations-`) | Streamed and filtered on the fly; never saved whole |
| Opinion text | CourtListener-hosted Harvard Caselaw PDFs (`harvard_pdf/<cluster_id>.pdf`) | Parsed in a sandboxed subprocess. Covers roughly pre-2018 opinions |
| Jurisdictions | `ingest/jurisdictions.json` | Ohio (Supreme Court, Court of Appeals) and the 6th Circuit; add courts by config |

Not used yet: the full `opinions-` CSV (54 GB; needed for post-2018
opinions) and the Caselaw Access Project site (static.case.law), which was
unreachable from the development environment.

## Setup (Docker Compose)

```bash
cp .env.example .env          # set POSTGRES_PASSWORD; point EMBED_MODEL_DIR at a local bge-small-en-v1.5
docker compose up -d db api
docker compose run --rm api python -m cp_ingest --sample 1000
curl -s localhost:8000/search -H 'content-type: application/json' \
  -d '{"query": "employee signed a two-year non-compete and was terminated without cause", "top_k": 5}'
```

The embedding model must be downloaded once into `EMBED_MODEL_DIR` (e.g.
`BAAI/bge-small-en-v1.5`); the app never downloads it. `EMBED_BACKEND=dev-hash`
runs without the model but is **not semantic** (tests/dev only); every
search response names the embedder in use.

## Development

```bash
cd backend && pip install -e ".[dev]"
python -m pytest -q     # needs a local Postgres 16 + pgvector (TEST_DATABASE_ADMIN_URL)
```

## API

- `POST /search` `{query, top_k≤50, courts?, date_from?, date_to?}` →
  results with `case_name, citation, court, date_filed, snippet,
  source_url, opinion_id, chunk_id, snippet_start/end`, plus the embedder
  name, the disclaimer and the good-law notice.
- `GET /opinions/{id}` → full text and metadata; `snippet_start/end` from a
  search result index into `text` exactly (for highlighting).
- `GET /health`
