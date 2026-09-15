-- Retry bookkeeping for the analyst swarm (FAILED jobs are retried up to N times;
-- PROCESSING jobs older than the stale window are re-claimed).
ALTER TABLE analysis_queue ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_queue_retry ON analysis_queue(processed_at) WHERE status IN ('PROCESSING','FAILED');
