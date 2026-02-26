-- 06_functions_triggers.sql

-- This is the most important function in the entire system.
-- Every UIR insert fires this. The system wakes up here.

CREATE OR REPLACE FUNCTION trigger_analysis_queue()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO analysis_queue (
        uir_uid,
        trigger_type,
        geo,
        domain,
        priority,
        status,
        created_at
    ) VALUES (
        NEW.uid,
        'NEW_UIR',
        NEW.geo,
        NEW.domain,
        NEW.priority,
        'PENDING',
        NOW()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER uir_analysis_trigger
    AFTER INSERT ON intelligence_records
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analysis_queue();
