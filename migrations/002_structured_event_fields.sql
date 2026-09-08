BEGIN;

ALTER TABLE gov_doc_events
    ADD COLUMN IF NOT EXISTS company_name TEXT,
    ADD COLUMN IF NOT EXISTS entity_name TEXT,
    ADD COLUMN IF NOT EXISTS department_name TEXT,
    ADD COLUMN IF NOT EXISTS amount_value NUMERIC,
    ADD COLUMN IF NOT EXISTS amount_currency TEXT,
    ADD COLUMN IF NOT EXISTS amount_type TEXT,
    ADD COLUMN IF NOT EXISTS event_date DATE;

CREATE INDEX IF NOT EXISTS gov_doc_events_event_date_idx
    ON gov_doc_events (event_date DESC);
CREATE INDEX IF NOT EXISTS gov_doc_events_amount_idx
    ON gov_doc_events (amount_value DESC) WHERE amount_value IS NOT NULL;
CREATE INDEX IF NOT EXISTS gov_doc_events_company_idx
    ON gov_doc_events (company_name) WHERE company_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS gov_doc_events_department_idx
    ON gov_doc_events (department_name) WHERE department_name IS NOT NULL;

COMMIT;
