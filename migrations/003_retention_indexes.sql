BEGIN;

CREATE INDEX IF NOT EXISTS gov_doc_events_undated_first_seen_idx
    ON gov_doc_events (first_seen_at DESC)
    WHERE event_date IS NULL;

COMMIT;
