BEGIN;

CREATE TABLE IF NOT EXISTS gov_doc_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    raw_published TEXT NOT NULL DEFAULT '',
    published_at TIMESTAMPTZ NOT NULL,
    payload_hash TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_name, external_id, payload_hash)
);

CREATE INDEX IF NOT EXISTS gov_doc_events_published_idx
    ON gov_doc_events (published_at DESC);

CREATE INDEX IF NOT EXISTS gov_doc_events_category_published_idx
    ON gov_doc_events (category, published_at DESC);

CREATE INDEX IF NOT EXISTS gov_doc_events_external_id_idx
    ON gov_doc_events (source_name, external_id);

CREATE TABLE IF NOT EXISTS gov_doc_source_state (
    source_name TEXT PRIMARY KEY,
    cursor JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_success_at TIMESTAMPTZ,
    last_error_at TIMESTAMPTZ,
    last_error TEXT,
    last_item_count INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
