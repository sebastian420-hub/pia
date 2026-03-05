from pia.core.database import DatabaseManager
import json

db = DatabaseManager()
results = {
    "failed_jobs": db.execute_query("SELECT queue_id, uir_uid, error_message FROM analysis_queue WHERE status = 'FAILED'", fetch=True),
    "entities_schema": db.execute_query("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'entities'", fetch=True)
}
print(json.dumps(results, indent=2, default=str))
