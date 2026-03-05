from pia.core.database import DatabaseManager
import json

db = DatabaseManager()
def get_val(query):
    res = db.execute_query(query, fetch=True)
    if res and isinstance(res[0], dict):
        return list(res[0].values())[0]
    return res[0][0] if res else 0

results = {
    "uir_count": get_val("SELECT count(*) FROM intelligence_records"),
    "entities_count": get_val("SELECT count(*) FROM entities"),
    "jobs_summary": db.execute_query("SELECT status, count(*) FROM analysis_queue GROUP BY status", fetch=True),
    "seismic_count": get_val("SELECT count(*) FROM seismic_events"),
    "recent_entities": db.execute_query("SELECT name, entity_type, created_at FROM entities ORDER BY created_at DESC LIMIT 10", fetch=True)
}
print(json.dumps(results, indent=2, default=str))
