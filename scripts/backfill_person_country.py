"""
Persons in the backbone were loaded without a country (P27 citizenship was not parsed). This
fetches P27 for every PERSON entity with a Q-id and no country_qid, in batches of 50, and updates
the row and the local cache line. Idempotent.
"""
import json
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger

from pia.core.database import DatabaseManager
from pia.kg import wikidata

CACHE = os.path.join("data", "wikidata_backbone.jsonl")


def main():
    db = DatabaseManager()
    wikidata.set_db(db)
    try:
        rows = db.execute_query("SELECT entity_id, qid FROM entities WHERE kind = 'PERSON' AND qid IS NOT NULL AND country_qid IS NULL", fetch=True) or []
        qids = [r["qid"] for r in rows]
        logger.info(f"{len(qids)} persons without a country")
        found = {}
        for i in range(0, len(qids), 50):
            for qid, parsed in wikidata.get_entities(qids[i:i + 50]).items():
                if parsed.get("country_qid"):
                    found[qid] = parsed["country_qid"]
            logger.info(f"{min(i + 50, len(qids))}/{len(qids)} fetched, {len(found)} with a country")
        for r in rows:
            c = found.get(r["qid"])
            if c:
                db.execute_query("UPDATE entities SET country_qid = %s WHERE entity_id = %s", (c, r["entity_id"]))
        # keep the offline cache in step so a reload does not lose this
        if os.path.exists(CACHE) and found:
            tmp = CACHE + ".tmp"
            with open(CACHE) as fin, open(tmp, "w") as fout:
                for line in fin:
                    try:
                        d = json.loads(line)
                    except Exception:
                        fout.write(line)
                        continue
                    if d.get("qid") in found and not d.get("country_qid"):
                        d["country_qid"] = found[d["qid"]]
                        line = json.dumps(d, ensure_ascii=False) + "\n"
                    fout.write(line)
            os.replace(tmp, CACHE)
        logger.success(f"person countries: {len(found)} set")
    finally:
        db.close()


if __name__ == "__main__":
    main()
