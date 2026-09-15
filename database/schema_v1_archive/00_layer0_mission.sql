-- 00_layer0_mission.sql

-- ════════════════════════════════════════════════════════════════
-- LAYER 0: MISSION CONTROL
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS mission_focus (
    focus_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category          TEXT NOT NULL,
    keywords          TEXT[],
    target_entities   TEXT[],
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    
    -- MULTI-TENANCY
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);

-- Note: We do not enable RLS on mission_focus at the DB level for agents, 
-- because agents need to see ALL active missions to ingest data properly.
-- RLS on this table will be handled at the API level (the UI only sees its own missions).
