-- ════════════════════════════════════════════════════════════════
-- THE KNOWLEDGE WEB
--   entities  : real things with a stable identity (Wikidata Q-id when one exists)
--   aliases   : every name a thing is known by
--   mentions  : which entity appears in which report, in which role
--   events    : what happened (actor, action, target, where, when, source, quote)
--   relations : computed summaries of events + Wikidata's static facts; never written by the LLM
-- ════════════════════════════════════════════════════════════════

CREATE TABLE entities (
    entity_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qid               TEXT,                                -- 'Q30'; NULL for PIA-local entities
    kind              TEXT NOT NULL DEFAULT 'UNKNOWN'
                      CHECK (kind IN ('PERSON','ORG','COUNTRY','PLACE','VESSEL','AIRCRAFT','EVENT','UNKNOWN')),
    name              TEXT NOT NULL,                       -- canonical label
    description       TEXT,
    resolution        TEXT NOT NULL DEFAULT 'LOCAL'
                      CHECK (resolution IN ('RESOLVED','LOCAL','NEEDS_REVIEW','REJECTED')),
    origin            TEXT NOT NULL DEFAULT 'llm',         -- 'wikidata' | 'geonames' | 'llm' | 'gdelt' | 'human'
    country_qid       TEXT,                                -- P17
    primary_geo       GEOMETRY(Point, 4326),
    sitelinks         INTEGER DEFAULT 0,                   -- Wikidata popularity proxy
    mention_count     INTEGER NOT NULL DEFAULT 0,
    first_seen        TIMESTAMPTZ DEFAULT NOW(),
    last_seen         TIMESTAMPTZ DEFAULT NOW(),
    wikidata_synced_at TIMESTAMPTZ,
    watch_status      TEXT DEFAULT 'PASSIVE' CHECK (watch_status IN ('PASSIVE','MONITORING','ACTIVE','CRITICAL')),
    threat_score      FLOAT DEFAULT 0.0 CHECK (threat_score BETWEEN 0.0 AND 1.0),
    embedding         VECTOR(1536),
    metadata          JSONB,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX entities_qid_uq ON entities(qid) WHERE qid IS NOT NULL;
CREATE INDEX idx_entity_kind       ON entities(kind, mention_count DESC);
CREATE INDEX idx_entity_resolution ON entities(resolution) WHERE resolution <> 'RESOLVED';
CREATE INDEX idx_entity_geo        ON entities USING GIST(primary_geo) WHERE primary_geo IS NOT NULL;
CREATE INDEX idx_entity_name_trgm  ON entities USING GIN (name gin_trgm_ops);
CREATE INDEX idx_entity_embedding  ON entities USING diskann(embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX idx_entity_watch      ON entities(watch_status, threat_score DESC) WHERE watch_status <> 'PASSIVE';

CREATE TABLE entity_aliases (
    entity_id   UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    alias_norm  TEXT NOT NULL,                             -- see kg.normalize()
    lang        TEXT NOT NULL DEFAULT 'en',
    source      TEXT NOT NULL DEFAULT 'wikidata',          -- 'wikidata' | 'geonames' | 'llm' | 'human'
    PRIMARY KEY (entity_id, alias_norm)
);
CREATE INDEX idx_alias_norm      ON entity_aliases(alias_norm);
CREATE INDEX idx_alias_norm_trgm ON entity_aliases USING GIN (alias_norm gin_trgm_ops);

-- What Wikidata's search answered for a name (so the same name is never looked up twice a day)
CREATE TABLE resolution_cache (
    query_norm   TEXT PRIMARY KEY,
    candidates   JSONB NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- P31 class → kind, learned once per class through SPARQL (subclass-of walk), then cached
CREATE TABLE wikidata_classes (
    class_qid    TEXT PRIMARY KEY,
    label        TEXT,
    kind         TEXT NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE mentions (
    report_uid  UUID NOT NULL REFERENCES intelligence_records(uid) ON DELETE CASCADE,
    entity_id   UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    surface     TEXT,                                      -- as written: 'the US', 'Beijing'
    role        TEXT NOT NULL DEFAULT 'MENTIONED' CHECK (role IN ('ACTOR','TARGET','LOCATION','GOVERNMENT','MENTIONED')),
    confidence  FLOAT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (report_uid, entity_id, role)
);
CREATE INDEX idx_mentions_entity ON mentions(entity_id, created_at DESC);

CREATE TABLE events (
    event_id       UUID NOT NULL DEFAULT gen_random_uuid(),
    event_time     TIMESTAMPTZ NOT NULL,
    time_precision TEXT NOT NULL DEFAULT 'day' CHECK (time_precision IN ('minute','hour','day','month')),
    action         TEXT NOT NULL,                          -- kg.ontology.ACTIONS
    actor_id       UUID REFERENCES entities(entity_id) ON DELETE SET NULL,
    target_id      UUID REFERENCES entities(entity_id) ON DELETE SET NULL,
    location_id    UUID REFERENCES entities(entity_id) ON DELETE SET NULL,
    geo            GEOMETRY(Point, 4326),
    report_uid     UUID REFERENCES intelligence_records(uid) ON DELETE SET NULL,
    source_id      TEXT REFERENCES sources(source_id),
    origin         TEXT NOT NULL CHECK (origin IN ('llm','gdelt','sensor','human')),
    quote          TEXT,
    confidence     FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    tone           FLOAT,                                  -- -10 (hostile) .. +10 (cooperative)
    external_id    TEXT,                                   -- GDELT GlobalEventID etc.
    kind           TEXT,                                   -- relation kind it feeds: HOSTILE | COOPERATIVE | ROLE | OWNERSHIP | NULL
    topic          TEXT,                                   -- kg.ontology.TOPICS: what the event is about
    code           TEXT,                                   -- raw CAMEO code for GDELT events ("051")
    dedup_key      TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_time, event_id)
);
SELECT create_hypertable('events', 'event_time', chunk_time_interval => INTERVAL '7 days');
CREATE UNIQUE INDEX events_dedup  ON events(dedup_key, event_time);
CREATE INDEX idx_events_actor     ON events(actor_id, event_time DESC);
CREATE INDEX idx_events_target    ON events(target_id, event_time DESC);
CREATE INDEX idx_events_action    ON events(action, event_time DESC);
CREATE INDEX idx_events_topic     ON events(topic);
CREATE INDEX idx_events_kind      ON events(kind);
CREATE INDEX idx_events_geo       ON events USING GIST(geo) WHERE geo IS NOT NULL;
CREATE INDEX idx_events_report    ON events(report_uid);

CREATE TABLE relations (
    a_id         UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    b_id         UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('HOSTILE','COOPERATIVE','ROLE','OWNERSHIP','MEMBERSHIP','LOCATED','MENTIONED_WITH')),
    source       TEXT NOT NULL CHECK (source IN ('events','wikidata','cooccurrence')),
    property     TEXT,                                     -- Wikidata P-id when source = 'wikidata'
    label        TEXT,                                     -- human label ('head of state', 'attacked')
    directed     BOOLEAN NOT NULL DEFAULT FALSE,           -- a → b meaningful (ROLE: a holds role in b)
    first_seen   TIMESTAMPTZ,
    last_seen    TIMESTAMPTZ,
    event_count  INTEGER NOT NULL DEFAULT 0,
    weight       FLOAT NOT NULL DEFAULT 0,                 -- events: Σ confidence·exp(-age/90d); wikidata: 1
    topics       JSONB NOT NULL DEFAULT '{}'::jsonb,        -- {"diplomacy": 26, "military": 19} (events only)
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (a_id, b_id, kind, source)
);
CREATE INDEX idx_relations_b      ON relations(b_id);
CREATE INDEX idx_relations_weight ON relations(weight DESC);

-- ════════════════════════════════════════════════════════════════
-- ANALYSIS QUEUE (one job per report; drained by the analyst swarm)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE analysis_queue (
    queue_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    uir_uid           UUID NOT NULL REFERENCES intelligence_records(uid) ON DELETE CASCADE,
    trigger_type      TEXT NOT NULL DEFAULT 'NEW_UIR',
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN ('CRITICAL','HIGH','NORMAL','LOW')),
    status            TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING','PROCESSING','DONE','FAILED')),
    retry_count       INTEGER NOT NULL DEFAULT 0,
    assigned_agent    TEXT,
    assigned_at       TIMESTAMPTZ,
    processed_at      TIMESTAMPTZ,
    result_cluster    UUID,
    error_message     TEXT,
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);
CREATE INDEX idx_queue_pending ON analysis_queue(priority DESC, created_at ASC) WHERE status = 'PENDING';
CREATE INDEX idx_queue_status  ON analysis_queue(status, created_at DESC);
CREATE INDEX idx_queue_retry   ON analysis_queue(processed_at) WHERE status IN ('PROCESSING','FAILED');

-- ════════════════════════════════════════════════════════════════
-- HUMAN FEEDBACK on a claim (event) or an identity decision (entity)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE ai_feedback (
    feedback_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id         UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    event_id          UUID,
    entity_id         UUID,
    feedback_type     TEXT NOT NULL CHECK (feedback_type IN ('CONFIRMED','REJECTED_HALLUCINATION','REJECTED_WRONG_ACTION','MERGED','SPLIT')),
    human_correction  TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ai_feedback_recent ON ai_feedback(created_at DESC);
