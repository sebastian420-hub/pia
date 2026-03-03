-- 06_functions_triggers.sql

-- ════════════════════════════════════════════════════════════════
-- THE HEARTBEAT TRIGGER
-- ════════════════════════════════════════════════════════════════
-- This is the most important function in the entire system.
-- Every INSERT into intelligence_records automatically queues analysis.
-- This is what makes the system react without being asked.

CREATE OR REPLACE FUNCTION trigger_analysis_queue()
RETURNS TRIGGER AS $$
BEGIN
    -- 1. Insert into the persistent analysis queue for the Analyst Agent
    INSERT INTO analysis_queue (
        uir_uid,
        trigger_uid,
        trigger_type,
        target_id,
        target_type,
        geo,
        domain,
        priority,
        status,
        created_at,
        client_id
    ) VALUES (
        NEW.uid,
        NEW.uid,
        'NEW_UIR',
        NEW.uid,
        'UIR',
        NEW.geo,
        NEW.domain,
        COALESCE(NEW.priority, 'NORMAL'),
        'PENDING',
        NOW(),
        NEW.client_id
    );

    -- 2. Emit a real-time notification via pg_notify
    -- External listeners (like Redis pub/sub bridge) consume this for instant alerts
    PERFORM pg_notify(
        'new_intelligence',
        json_build_object(
            'uid', NEW.uid,
            'source_type', NEW.source_type,
            'priority', NEW.priority,
            'domain', NEW.domain,
            'headline', NEW.content_headline,
            'geo', CASE
                WHEN NEW.geo IS NOT NULL
                THEN json_build_object(
                    'lat', ST_Y(NEW.geo),
                    'lon', ST_X(NEW.geo)
                )
                ELSE NULL
            END
        )::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to Layer 2
DROP TRIGGER IF EXISTS uir_analysis_trigger ON intelligence_records;
CREATE TRIGGER uir_analysis_trigger
    AFTER INSERT ON intelligence_records
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analysis_queue();
