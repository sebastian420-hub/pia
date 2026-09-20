-- ════════════════════════════════════════════════════════════════
-- MISSIONS (collect broadly, look narrowly) — see migrations/010_missions.sql for the columns' meaning
-- ════════════════════════════════════════════════════════════════
CREATE TABLE missions (
    mission_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL UNIQUE,
    description  TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT FALSE,
    area         GEOMETRY(MultiPolygon, 4326),
    countries    TEXT[] NOT NULL DEFAULT '{}',
    languages    TEXT[] NOT NULL DEFAULT '{en}',
    feeds        TEXT[] NOT NULL DEFAULT '{}',
    sources      TEXT[] NOT NULL DEFAULT '{}',
    watchlist    UUID[] NOT NULL DEFAULT '{}',
    topics       TEXT[] NOT NULL DEFAULT '{}',
    alert_rules  JSONB NOT NULL DEFAULT '{"watchlist_hostile": true, "watchlist_pair": true, "new_entity_in_area": 3}'::jsonb,
    default_view JSONB NOT NULL DEFAULT '{}'::jsonb,
    model        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX missions_one_active ON missions ((is_active)) WHERE is_active;
CREATE TABLE mission_relevance (
    mission_id  UUID NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('report','entity','event')),
    ref_id      UUID NOT NULL,
    score       REAL NOT NULL,
    reasons     TEXT[] NOT NULL DEFAULT '{}',
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (mission_id, kind, ref_id)
);
CREATE INDEX idx_mission_relevance_score ON mission_relevance(mission_id, kind, score DESC);
CREATE TABLE mission_memory (
    mission_id  UUID NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (mission_id, key)
);
INSERT INTO missions (name, description, is_active) VALUES ('General', 'Everything, no focus', TRUE);

-- ════════════════════════════════════════════════════════════════
-- SOURCES: one row per outlet / feed / dataset. Trust is per source.
-- ════════════════════════════════════════════════════════════════
CREATE TABLE sources (
    source_id     TEXT PRIMARY KEY,          -- domain or dataset id: 'bbc.co.uk', 'gdelt', 'usgs'
    label         TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('NEWS','AGENCY','GOVERNMENT','SENSOR','DATASET','HUMAN','SYSTEM')),
    trust         FLOAT NOT NULL DEFAULT 0.5 CHECK (trust BETWEEN 0.0 AND 1.0),
    country_qid   TEXT,
    language      TEXT,
    homepage      TEXT,
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO sources (source_id, label, kind, trust, country_qid, language, homepage) VALUES
('bbc.co.uk',      'BBC News',          'NEWS',    0.85, 'Q145', 'en', 'https://www.bbc.co.uk'),
('aljazeera.com',  'Al Jazeera',        'NEWS',    0.75, 'Q846', 'en', 'https://www.aljazeera.com'),
('nytimes.com',    'The New York Times','NEWS',    0.85, 'Q30',  'en', 'https://www.nytimes.com'),
('theverge.com',   'The Verge',         'NEWS',    0.60, 'Q30',  'en', 'https://www.theverge.com'),
('gdelt',          'GDELT Project',     'DATASET', 0.55, NULL,   NULL, 'https://www.gdeltproject.org'),
('usgs',           'USGS Earthquake Hazards Program', 'SENSOR', 0.99, 'Q30', 'en', 'https://earthquake.usgs.gov'),
('wikidata',       'Wikidata',          'DATASET', 0.80, NULL,   NULL, 'https://www.wikidata.org'),
('upload',         'Uploaded document', 'HUMAN',   0.70, NULL,   NULL, NULL),
('director',       'Director tasking',  'HUMAN',   0.90, NULL,   NULL, NULL),
('simulated',      'Simulated sensor (demo data)', 'SYSTEM', 0.10, NULL, NULL, NULL);
