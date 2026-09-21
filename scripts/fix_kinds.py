"""Re-derive the kind of every Wikidata entity from its classes with the priority rule (country beats place)."""
import json, os, sys
sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger
from pia.core.database import DatabaseManager
from pia.kg.resolver import Resolver

db = DatabaseManager(); r = Resolver(db)
rows = db.execute_query("SELECT entity_id, qid, name, kind, metadata->'p31' AS p31 FROM entities WHERE origin = 'wikidata' AND metadata ? 'p31'", fetch=True) or []
changed = 0
for e in rows:
    p31 = e["p31"] if isinstance(e["p31"], list) else json.loads(e["p31"] or "[]")
    if not p31: continue
    k = r._kind_from_p31(p31)
    if k and k != "UNKNOWN" and k != e["kind"]:
        db.execute_query("UPDATE entities SET kind = %s, updated_at = NOW() WHERE entity_id = %s", (k, e["entity_id"]))
        logger.info(f"{e['name']} ({e['qid']}): {e['kind']} → {k}")
        changed += 1
logger.success(f"{changed} of {len(rows)} re-kinded")
