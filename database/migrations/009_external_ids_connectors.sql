-- Migration 009: connectors. Any source hands the engine the same shapes (entity / fact / event /
-- document); hard identifiers from other systems land in external_ids so sources enrich the same node.
CREATE TABLE IF NOT EXISTS external_ids (
    source_id   TEXT NOT NULL REFERENCES sources(source_id),
    external_id TEXT NOT NULL,
    entity_id   UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    kind        TEXT NOT NULL DEFAULT 'id',        -- ftm | passport | company_reg | phone | case | …
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_external_ids_entity ON external_ids(entity_id);

-- structured facts from connectors sit next to Wikidata facts in relations
ALTER TABLE relations DROP CONSTRAINT IF EXISTS relations_source_check;
ALTER TABLE relations ADD CONSTRAINT relations_source_check CHECK (source IN ('events','wikidata','cooccurrence','connector'));
ALTER TABLE relations ADD COLUMN IF NOT EXISTS via_source TEXT;                 -- the connector's source_id
ALTER TABLE relations ADD COLUMN IF NOT EXISTS record_ref TEXT;                 -- the connector's own pointer (proof)
ALTER TABLE relations ADD COLUMN IF NOT EXISTS properties JSONB NOT NULL DEFAULT '{}'::jsonb;   -- program, reason, authority …

-- events from connectors (structured rows) need no verifier; their trust is the source's
ALTER TABLE events DROP CONSTRAINT IF EXISTS events_origin_check;
ALTER TABLE events ADD CONSTRAINT events_origin_check CHECK (origin IN ('llm','gdelt','sensor','human','connector'));
ALTER TABLE events ADD COLUMN IF NOT EXISTS record_ref TEXT;

-- entity properties from structured sources (birth date, nationality, registration …)
ALTER TABLE entities ADD COLUMN IF NOT EXISTS properties JSONB NOT NULL DEFAULT '{}'::jsonb;
-- lists an entity is on (sanctions / PEP / watchlist), kept denormalised for the card
ALTER TABLE entities ADD COLUMN IF NOT EXISTS listings JSONB NOT NULL DEFAULT '[]'::jsonb;

-- connector runs
CREATE TABLE IF NOT EXISTS connector_runs (
    run_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   TEXT NOT NULL REFERENCES sources(source_id),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status      TEXT NOT NULL DEFAULT 'running',
    stats       JSONB NOT NULL DEFAULT '{}'::jsonb,
    note        TEXT
);
