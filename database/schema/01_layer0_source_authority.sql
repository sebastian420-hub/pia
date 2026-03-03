-- 01_layer0_source_authority.sql

-- ════════════════════════════════════════════════════════════════
-- LAYER 0: SOURCE AUTHORITY
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS source_authority (
    source_name       TEXT PRIMARY KEY,
    source_type       TEXT,
    trust_score       FLOAT NOT NULL CHECK (trust_score BETWEEN 0.0 AND 1.0),
    notes             TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Seed some default high-trust sources
INSERT INTO source_authority (source_name, trust_score, notes) VALUES
('ADS-B Aviation Feed', 0.95, 'Direct physical telemetry from aircraft transponders'),
('AIS Maritime Feed', 0.90, 'Direct physical telemetry from maritime vessels'),
('USGS Seismic Feed', 0.99, 'Scientific geological sensor data')
ON CONFLICT (source_name) DO NOTHING;