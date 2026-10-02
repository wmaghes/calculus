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

## Current local index (development run, 2026-09-30)

1,000 opinions (the most-cited with a Harvard PDF per jurisdiction; unpublished
excluded): 500 Sixth Circuit (1968-2017), 465 Supreme Court of Ohio
(1965-2016), 35 Ohio Court of Appeals (1974-2001); 24,952 chunks, 0 failed
downloads. Built from the 2026-09-30 bulk files (73.0 M dockets and 9.9 M
clusters scanned). Embedded with `dev-hash`, so the vector half is
lexical-ish, not semantic, until `--reindex` is run with bge-small.

Known text-quality limit: many Federal Reporter PDFs are two-column, and the
extracted text sometimes interleaves the columns ("alle- known harasser").
Offsets are exact against the stored text, but snippets can read oddly.

```bash
python -m cp_ingest --reindex   # re-chunk + re-embed stored opinions, no network
```

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
  one result per opinion (its best passage) with `case_name, citation,
  court, date_filed, snippet, source_url, opinion_id, chunk_id,
  snippet_start/end, other_matching_chunk_ids`, plus the embedder name, the
  disclaimer and the good-law notice.
- `GET /opinions/{id}` → full text and metadata; `snippet_start/end` from a
  search result index into `text` exactly (for highlighting).
- `GET /health`
