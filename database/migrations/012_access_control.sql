-- 012: access control — users, per-user tokens, visibility on sources, grants, audit log.
-- One rule: a row is as visible as its source. Everything present today stays public.

CREATE TABLE IF NOT EXISTS users (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    email       TEXT UNIQUE,
    role        TEXT NOT NULL CHECK (role IN ('viewer', 'analyst', 'admin')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disabled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS api_tokens (
    token_hash   TEXT PRIMARY KEY,                       -- sha256 of the token; the token itself is shown once
    user_id      UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    label        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);

ALTER TABLE sources ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'public'
    CHECK (visibility IN ('public', 'org', 'restricted'));

CREATE TABLE IF NOT EXISTS source_grants (
    source_id  TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    granted_by UUID REFERENCES users(user_id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, user_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id       BIGSERIAL PRIMARY KEY,
    at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id  UUID,
    action   TEXT NOT NULL,          -- login | read_restricted | write | delete | admin
    object   TEXT,                   -- path or object id
    detail   JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, at DESC);

-- listings must say where they came from, like every other row: backfill from what we know
UPDATE entities SET listings = (
    SELECT jsonb_agg(CASE WHEN l ? 'source' THEN l
                          WHEN l->>'list' = 'PEP' THEN l || '{"source": "opensanctions_peps"}'::jsonb
                          ELSE l || '{"source": "opensanctions_sanctions"}'::jsonb END)
    FROM jsonb_array_elements(listings) l)
WHERE listings <> '[]'::jsonb AND EXISTS (SELECT 1 FROM jsonb_array_elements(listings) l WHERE NOT (l ? 'source'));

-- human reporters are private by default
UPDATE sources SET visibility = 'restricted' WHERE kind = 'HUMAN' AND source_id LIKE 'reporter:%';

-- (recorded by scripts/validate_system.py as 012_access_control.sql)
