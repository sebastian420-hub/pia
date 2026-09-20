-- Migration 008: living verbs. Families are fixed; verbs grow on their own (see docs/design/living_verbs_plan.md).
--   verbs           the catalogue: canonical phrase, family, default stance, status, examples, embedding
--   verb_aliases    other phrasings that map to a verb ("bombed" → strike)
--   events          predicate (the article's words), verb_id, family, stance (−3…+3), modality, polarity,
--                   verifier_verdict / verifier_stance (independent check before a line is drawn)
--   entity_briefs   3–5 sentences of "what is happening", written from verified quotes only
CREATE TABLE IF NOT EXISTS verbs (
    verb_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verb           TEXT NOT NULL UNIQUE,                          -- canonical phrase, lower case: "call for a boycott of"
    family         TEXT NOT NULL,                                 -- kg.verbs.FAMILIES
    default_stance SMALLINT NOT NULL DEFAULT 0 CHECK (default_stance BETWEEN -3 AND 3),
    status         TEXT NOT NULL DEFAULT 'auto' CHECK (status IN ('seed','auto','curated','merged','rejected')),
    merged_into    UUID REFERENCES verbs(verb_id),
    cameo_codes    TEXT[] NOT NULL DEFAULT '{}',                  -- GDELT codes that map here
    examples       JSONB NOT NULL DEFAULT '[]'::jsonb,            -- up to 5 quotes
    embedding      VECTOR(1536),
    seen_count     INTEGER NOT NULL DEFAULT 0,
    created_by     TEXT NOT NULL DEFAULT 'model',                 -- seed | model | human
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_verbs_family ON verbs(family, status);

CREATE TABLE IF NOT EXISTS verb_aliases (
    alias      TEXT PRIMARY KEY,                                   -- lower case phrase
    verb_id    UUID NOT NULL REFERENCES verbs(verb_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE events ADD COLUMN IF NOT EXISTS predicate        TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS verb_id          UUID REFERENCES verbs(verb_id) ON DELETE SET NULL;
ALTER TABLE events ADD COLUMN IF NOT EXISTS family           TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS stance           SMALLINT CHECK (stance BETWEEN -3 AND 3);
ALTER TABLE events ADD COLUMN IF NOT EXISTS modality         TEXT CHECK (modality IN ('asserted','intended','claimed','hypothetical','denied'));
ALTER TABLE events ADD COLUMN IF NOT EXISTS polarity         BOOLEAN;
ALTER TABLE events ADD COLUMN IF NOT EXISTS verifier_verdict TEXT CHECK (verifier_verdict IN ('yes','partly','no'));
ALTER TABLE events ADD COLUMN IF NOT EXISTS verifier_stance  SMALLINT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS verified_at      TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_events_verb ON events(verb_id);
CREATE INDEX IF NOT EXISTS idx_events_verdict ON events(verifier_verdict) WHERE origin = 'llm';

CREATE TABLE IF NOT EXISTS entity_briefs (
    entity_id    UUID PRIMARY KEY REFERENCES entities(entity_id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    events_hash  TEXT NOT NULL,                                     -- hash of the verified event ids it was written from
    model        TEXT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE events ADD COLUMN IF NOT EXISTS verifier_note TEXT;
