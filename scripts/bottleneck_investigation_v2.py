from pia.core.database import DatabaseManager
import json

db = DatabaseManager()

def get_row(query):
    res = db.execute_query(query, fetch=True)
    return res[0] if res else None

def get_val(query):
    res = db.execute_query(query, fetch=True)
    if res and isinstance(res[0], dict):
        return list(res[0].values())[0]
    return res[0][0] if res else None

results = {
    "sample_relationship": get_row("SELECT relationship_id, evidence_uids FROM entity_relationships LIMIT 1"),
    "constraint_def": get_val("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'entities_entity_type_check'")
}

if results["sample_relationship"]:
    rel = results["sample_relationship"]
    results["type_of_evidence_uids"] = str(type(rel.get("evidence_uids")))

print(json.dumps(results, indent=2, default=str))
