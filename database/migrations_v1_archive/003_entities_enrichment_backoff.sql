-- Enrichment agent backoff: stop retrying the same failing entity every 15 seconds.
ALTER TABLE entities ADD COLUMN IF NOT EXISTS enrichment_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS enrichment_next_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_entity_enrich ON entities(confidence, enrichment_next_at) WHERE confidence < 0.5;
