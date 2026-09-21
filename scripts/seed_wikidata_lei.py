"""
Wikidata knows the LEI (P1278) of ~40k organisations. This puts those LEIs on our backbone ORGs as hard ids
(external_ids source 'wikidata', kind 'lei'), so GLEIF's register joins the nodes the news already uses.
Tries one SPARQL query first; falls back to the entity API in batches of 50. Idempotent.
"""
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger

from pia.core.database import DatabaseManager
from pia.kg import wikidata


def main():
    db = DatabaseManager()
    db.execute_query("INSERT INTO sources (source_id, label, kind, trust) VALUES ('wikidata', 'Wikidata', 'DATASET', 0.8) ON CONFLICT DO NOTHING")
    rows = db.execute_query("SELECT entity_id, qid FROM entities WHERE kind = 'ORG' AND qid IS NOT NULL AND resolution = 'RESOLVED'", fetch=True) or []
    by_qid = {r["qid"]: str(r["entity_id"]) for r in rows}
    found = {}
    try:
        for r in wikidata.sparql("SELECT ?item ?lei WHERE { ?item wdt:P1278 ?lei }", timeout=120):
            qid = r["item"].rsplit("/", 1)[-1]
            if qid in by_qid:
                found[qid] = r["lei"]
        logger.info(f"sparql: {len(found)} of our ORGs have an LEI")
    except Exception as e:
        logger.warning(f"sparql failed ({e}); walking {len(by_qid)} items through the entity API")
        qids = list(by_qid)
        for i in range(0, len(qids), 50):
            try:
                ents = wikidata.get_entities(qids[i:i + 50], raw=True)
            except Exception as e2:
                logger.warning(f"batch {i}: {e2}")
                continue
            for qid, ent in ents.items():
                for v, _ in wikidata._claim_values(ent, "P1278"):
                    if isinstance(v, str) and len(v) == 20:
                        found[qid] = v
                        break
            if i % 1000 == 0:
                logger.info(f"{i}/{len(qids)} — {len(found)} LEIs")
    n = 0
    for qid, lei in found.items():
        db.execute_query("""
            INSERT INTO external_ids (source_id, external_id, entity_id, kind) VALUES ('wikidata', %s, %s, 'lei')
            ON CONFLICT (source_id, external_id) DO NOTHING
        """, (lei.upper(), by_qid[qid]))
        n += 1
    logger.success(f"{n} LEIs on backbone organisations")
    db.close()


if __name__ == "__main__":
    main()
