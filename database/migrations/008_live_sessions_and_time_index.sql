-- Live sessions: time-boxed activation of ON_DEMAND sources (the US relay).
CREATE TABLE IF NOT EXISTS live_sessions (
    session_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    stopped_at  TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    started_by  TEXT,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_live_sessions_active ON live_sessions(expires_at) WHERE stopped_at IS NULL;

-- Timeline queries (from/to + domain/priority facets)
CREATE INDEX IF NOT EXISTS idx_uir_time_domain_prio ON intelligence_records(created_at, domain, priority);
