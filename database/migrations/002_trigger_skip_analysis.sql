-- ════════════════════════════════════════════════════════════════
-- THE HEARTBEAT: every new report queues one analysis job and notifies live listeners.
-- News agents insert the report only after the article body has been fetched, so the
-- analyst always sees the fullest text available.
-- ════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION trigger_analysis_queue()
RETURNS TRIGGER AS $$
BEGIN
    -- Bulk sources (GDELT) carry their own events and skip the LLM analyst.
    IF COALESCE(NEW.metadata->>'skip_analysis', 'false') = 'true' THEN
        RETURN NEW;   -- no analyst job, no live notification: these rows only back events
    END IF;
    INSERT INTO analysis_queue (uir_uid, trigger_type, priority, status, client_id)
    VALUES (NEW.uid, 'NEW_UIR', COALESCE(NEW.priority, 'NORMAL'), 'PENDING', NEW.client_id);

    PERFORM pg_notify('new_intelligence', json_build_object(
        'uid', NEW.uid,
        'source_type', NEW.source_type,
        'source_id', NEW.source_id,
        'priority', NEW.priority,
        'domain', NEW.domain,
        'headline', NEW.content_headline,
        'created_at', to_char(NEW.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
        'geo', CASE WHEN NEW.geo IS NOT NULL
                    THEN json_build_object('lat', ST_Y(NEW.geo), 'lon', ST_X(NEW.geo)) ELSE NULL END
    )::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS uir_analysis_trigger ON intelligence_records;
CREATE TRIGGER uir_analysis_trigger
    AFTER INSERT ON intelligence_records
    FOR EACH ROW EXECUTE FUNCTION trigger_analysis_queue();
