-- Live event payload carries created_at so the UI can show a Zulu time without a second request.
CREATE OR REPLACE FUNCTION trigger_analysis_queue()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO analysis_queue (
        uir_uid, trigger_uid, trigger_type, target_id, target_type, geo, domain, priority, status, created_at, client_id
    ) VALUES (
        NEW.uid, NEW.uid, 'NEW_UIR', NEW.uid, 'UIR', NEW.geo, NEW.domain,
        COALESCE(NEW.priority, 'NORMAL'), 'PENDING', NOW(), NEW.client_id
    );

    PERFORM pg_notify(
        'new_intelligence',
        json_build_object(
            'uid', NEW.uid,
            'source_type', NEW.source_type,
            'priority', NEW.priority,
            'domain', NEW.domain,
            'headline', NEW.content_headline,
            'created_at', to_char(NEW.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
            'geo', CASE WHEN NEW.geo IS NOT NULL
                        THEN json_build_object('lat', ST_Y(NEW.geo), 'lon', ST_X(NEW.geo))
                        ELSE NULL END
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
