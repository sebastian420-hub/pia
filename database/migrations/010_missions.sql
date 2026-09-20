-- Migration 010: missions — "collect broadly, look narrowly".
-- A mission is a collection plan (area, countries, sources, watchlist, topics, alert rules, default view).
-- Broad collection continues; relevance scores per mission decide what the picture shows.
CREATE TABLE IF NOT EXISTS missions (
    mission_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL UNIQUE,
    description  TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT FALSE,          -- the one the screens follow (single user)
    area         GEOMETRY(MultiPolygon, 4326),            -- NULL = anywhere
    countries    TEXT[] NOT NULL DEFAULT '{}',            -- Q-ids
    languages    TEXT[] NOT NULL DEFAULT '{en}',
    feeds        TEXT[] NOT NULL DEFAULT '{}',            -- RSS URLs the mission adds to collection
    sources      TEXT[] NOT NULL DEFAULT '{}',            -- source_ids it cares about (connectors, outlets)
    watchlist    UUID[] NOT NULL DEFAULT '{}',            -- entity_ids
    topics       TEXT[] NOT NULL DEFAULT '{}',            -- kg.ontology.TOPICS
    alert_rules  JSONB NOT NULL DEFAULT '{"watchlist_hostile": true, "watchlist_pair": true, "new_entity_in_area": 3}'::jsonb,
    default_view JSONB NOT NULL DEFAULT '{}'::jsonb,      -- {"lon":..,"lat":..,"height":..,"window":"7d"}
    model        TEXT,                                    -- stronger extraction model for mission reads (optional)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS missions_one_active ON missions ((is_active)) WHERE is_active;

-- relevance of a thing to a mission (recomputed hourly for active missions, last 30 days)
CREATE TABLE IF NOT EXISTS mission_relevance (
    mission_id  UUID NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('report','entity','event')),
    ref_id      UUID NOT NULL,
    score       REAL NOT NULL,
    reasons     TEXT[] NOT NULL DEFAULT '{}',
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (mission_id, kind, ref_id)
);
CREATE INDEX IF NOT EXISTS idx_mission_relevance_score ON mission_relevance(mission_id, kind, score DESC);

-- what a mission has already noticed (so alerts fire once)
CREATE TABLE IF NOT EXISTS mission_memory (
    mission_id  UUID NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    key         TEXT NOT NULL,                            -- 'hostile:<event_id>' | 'pair:<a>|<b>' | 'entity:<id>'
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (mission_id, key)
);

INSERT INTO missions (name, description, is_active) VALUES ('General', 'Everything, no focus', TRUE) ON CONFLICT (name) DO NOTHING;

-- the old thin mission_focus goes; reports keep mission_id (now a missions.mission_id)
DROP TABLE IF EXISTS mission_focus;

-- mission alerts are reports written by the system itself
INSERT INTO sources (source_id, label, kind, trust) VALUES ('pia', 'PIA missions', 'SYSTEM', 1.0) ON CONFLICT DO NOTHING;
