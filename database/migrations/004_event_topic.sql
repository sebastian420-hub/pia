-- Migration 004: what an event is about.
--   events.topic   controlled list (pia.kg.ontology.TOPICS): nuclear, sanctions, trade, territory, military …
--   events.code    the raw CAMEO code for GDELT events ("051"), so evidence can say what GDELT coded
--   relations.topics  {"diplomacy": 26, "military": 19} computed by kg.relations.rebuild
ALTER TABLE events ADD COLUMN IF NOT EXISTS topic text;
ALTER TABLE events ADD COLUMN IF NOT EXISTS code text;
CREATE INDEX IF NOT EXISTS events_topic_idx ON events (topic);
ALTER TABLE relations ADD COLUMN IF NOT EXISTS topics jsonb NOT NULL DEFAULT '{}'::jsonb;
