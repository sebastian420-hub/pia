-- Migration 007: a line is drawn only from what an article says.
--   events.is_root        GDELT IsRootEvent: the event is the article's main event
--   events.outlets        every outlet that carried the same (pair, action, day) wire event
--   events.weight_class   'material' | 'verbal' (verbal wire rows never draw a line alone)
--   relations.verified_count / wire_count / verified_topics: article-read vs wire events per (pair, kind)
ALTER TABLE events ADD COLUMN IF NOT EXISTS is_root boolean;
ALTER TABLE events ADD COLUMN IF NOT EXISTS outlets jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE events ADD COLUMN IF NOT EXISTS weight_class text;
ALTER TABLE relations ADD COLUMN IF NOT EXISTS verified_count integer NOT NULL DEFAULT 0;
ALTER TABLE relations ADD COLUMN IF NOT EXISTS wire_count integer NOT NULL DEFAULT 0;
ALTER TABLE relations ADD COLUMN IF NOT EXISTS verified_topics jsonb NOT NULL DEFAULT '{}'::jsonb;
UPDATE events SET weight_class = 'material' WHERE origin = 'llm' AND weight_class IS NULL;
