-- ════════════════════════════════════════════════════════════════
-- MISSION FOCUS (what the agency is watching)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE mission_focus (
    focus_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category          TEXT NOT NULL,
    keywords          TEXT[],
    target_entities   TEXT[],
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);

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
