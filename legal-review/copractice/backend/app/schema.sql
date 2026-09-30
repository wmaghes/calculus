-- Copractice schema. Public case law only; see CLAUDE.md.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS courts (
    id            text PRIMARY KEY,          -- CourtListener court id, e.g. 'ohio', 'ohioctapp', 'ca6'
    name          text NOT NULL,
    jurisdiction  text NOT NULL              -- config key, e.g. 'ohio', 'ca6'
);

CREATE TABLE IF NOT EXISTS opinions (
    id                   bigserial PRIMARY KEY,
    source               text NOT NULL,      -- 'courtlistener'
    cluster_id           bigint NOT NULL,
    case_name            text NOT NULL,
    citation             text,               -- e.g. '123 Ohio St. 3d 45; 2009-Ohio-1234'
    court_id             text NOT NULL REFERENCES courts(id),
    date_filed           date,
    judges               text,
    docket_id            bigint,
    docket_number        text,
    precedential_status  text,
    citation_count       integer,
    source_url           text NOT NULL,      -- canonical CourtListener URL
    text_url             text,               -- where the text was fetched from
    text_sha256          text NOT NULL,
    text_chars           integer NOT NULL,
    ingested_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, cluster_id)
);
CREATE INDEX IF NOT EXISTS opinions_court_date ON opinions (court_id, date_filed);

-- Full opinion text kept once, so quotes can be verified against the whole opinion.
CREATE TABLE IF NOT EXISTS opinion_texts (
    opinion_id  bigint PRIMARY KEY REFERENCES opinions(id) ON DELETE CASCADE,
    text        text NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id           bigserial PRIMARY KEY,
    opinion_id   bigint NOT NULL REFERENCES opinions(id) ON DELETE CASCADE,
    position     integer NOT NULL,           -- 0-based order within the opinion
    char_start   integer NOT NULL,           -- offsets into opinion_texts.text
    char_end     integer NOT NULL,
    text         text NOT NULL,
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding    vector(384),
    embed_model  text,
    UNIQUE (opinion_id, position),
    CHECK (char_start >= 0 AND char_end > char_start)
);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);

-- A matter is only a label + a pointer to the lexreview case. No client facts here.
CREATE TABLE IF NOT EXISTS matters (
    id                 uuid PRIMARY KEY,
    title              text NOT NULL CHECK (length(title) <= 200),
    lexreview_case_id  text,
    created_by         text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);

-- Append-only, hash-chained audit log. Records outbound calls (destination +
-- payload hash, never payload text), searches (query digest), ingest runs.
CREATE TABLE IF NOT EXISTS audit_log (
    id              bigserial PRIMARY KEY,
    at              timestamptz NOT NULL DEFAULT now(),
    actor           text NOT NULL,
    action          text NOT NULL,
    outbound        boolean NOT NULL DEFAULT false,
    destination     text,
    payload_sha256  text,
    payload_bytes   integer,
    detail          jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash       text NOT NULL,
    hash            text NOT NULL
);
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_immutable();

-- Ingest progress, so runs are resumable and idempotent.
CREATE TABLE IF NOT EXISTS ingest_state (
    key         text PRIMARY KEY,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ingest_candidates (
    cluster_id           bigint PRIMARY KEY,
    court_id             text NOT NULL,
    case_name            text NOT NULL,
    date_filed           date,
    judges               text,
    docket_id            bigint,
    docket_number        text,
    precedential_status  text,
    citation_count       integer,
    slug                 text,
    pdf_path             text NOT NULL,
    citation             text,
    status               text NOT NULL DEFAULT 'pending'   -- pending | done | failed:<reason>
);
