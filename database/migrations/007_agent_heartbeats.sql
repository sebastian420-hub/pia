-- Every agent upserts a row each poll; /health reads it. Replaces guessing from log lines.
CREATE TABLE IF NOT EXISTS agent_heartbeats (
    agent_name  TEXT PRIMARY KEY,
    agent_kind  TEXT,
    hostname    TEXT,
    last_beat   TIMESTAMPTZ NOT NULL,
    status      TEXT NOT NULL DEFAULT 'OK',
    detail      JSONB
);
