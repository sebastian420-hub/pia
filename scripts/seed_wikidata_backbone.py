"""
Loads the Wikidata backbone (~50k items) into the knowledge web.

    python scripts/seed_wikidata_backbone.py            # fetch from Wikidata (≈ 1 h, polite pacing)
    python scripts/seed_wikidata_backbone.py --offline  # load data/wikidata_backbone.jsonl only

Each SPARQL query is small and paged; fetched items are cached in data/wikidata_backbone.jsonl
so a fresh database can be seeded offline. Safe to re-run (upserts by Q-id).
"""
import argparse
import json
import os
import sys
import time

sys.path.append(os.path.join(os.getcwd(), "src"))

from loguru import logger

from pia.core.database import DatabaseManager
from pia.kg import wikidata
from pia.kg.resolver import Resolver

CACHE = os.path.join("data", "wikidata_backbone.jsonl")

# (label, SPARQL returning ?item). Keep each under ~10k rows.
QUERIES = [
    ("sovereign states", "SELECT ?item WHERE { ?item wdt:P31 wd:Q3624078 . }"),
    ("capitals", "SELECT ?item WHERE { ?c wdt:P31 wd:Q3624078 ; wdt:P36 ?item . }"),
    ("heads of state", "SELECT ?item WHERE { ?c wdt:P31 wd:Q3624078 ; wdt:P35 ?item . }"),
    ("heads of government", "SELECT ?item WHERE { ?c wdt:P31 wd:Q3624078 ; wdt:P6 ?item . }"),
    ("international organizations", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q484652 ; wikibase:sitelinks ?n . FILTER(?n >= 15) }"),
    ("intergovernmental organizations", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q245065 ; wikibase:sitelinks ?n . FILTER(?n >= 10) }"),
    ("armed forces", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q61883 ; wikibase:sitelinks ?n . FILTER(?n >= 5) }"),
    ("armed groups", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q17149090 ; wikibase:sitelinks ?n . FILTER(?n >= 5) }"),
    ("political parties (notable)", "SELECT ?item WHERE { ?item wdt:P31 wd:Q7278 ; wikibase:sitelinks ?n . FILTER(?n >= 12) }"),
    ("government agencies (notable)", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q327333 ; wikibase:sitelinks ?n . FILTER(?n >= 15) }"),
    ("companies (notable)", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q4830453 ; wikibase:sitelinks ?n . FILTER(?n >= 25) }"),
    ("news organizations", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q1193236 ; wikibase:sitelinks ?n . FILTER(?n >= 15) }"),
    ("cities > 300k", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q515 ; wdt:P1082 ?p . FILTER(?p > 300000) }"),
    ("warships (notable)", "SELECT ?item WHERE { ?item wdt:P31/wdt:P279* wd:Q1229765 ; wikibase:sitelinks ?n . FILTER(?n >= 5) }"),
    ("politicians (very notable)", "SELECT ?item WHERE { ?item wdt:P106 wd:Q82955 ; wikibase:sitelinks ?n . FILTER(?n >= 60) }"),
    ("business people (notable)", "SELECT ?item WHERE { ?item wdt:P106 wd:Q43845 ; wikibase:sitelinks ?n . FILTER(?n >= 40) }"),
    ("military officers (notable)", "SELECT ?item WHERE { ?item wdt:P106 wd:Q189290 ; wikibase:sitelinks ?n . FILTER(?n >= 30) }"),
]


def collect_qids() -> list:
    qids = []
    for label, q in QUERIES:
        try:
            rows = wikidata.sparql(q, timeout=120)
        except Exception as e:
            logger.error(f"{label}: {e}")
            continue
        ids = [r["item"].rsplit("/", 1)[-1] for r in rows]
        logger.info(f"{label}: {len(ids)}")
        qids.extend(ids)
        time.sleep(1)
    return list(dict.fromkeys(qids))


def fetch_to_cache(qids: list):
    os.makedirs("data", exist_ok=True)
    done = set()
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["qid"])
                except Exception:
                    pass
    todo = [q for q in qids if q not in done]
    logger.info(f"{len(done)} cached, {len(todo)} to fetch")
    with open(CACHE, "a") as f:
        for i in range(0, len(todo), 50):
            batch = todo[i:i + 50]
            try:
                parsed = wikidata.get_entities(batch)
            except Exception as e:
                logger.warning(f"batch {i}: {e}; retrying once")
                time.sleep(5)
                try:
                    parsed = wikidata.get_entities(batch)
                except Exception as e2:
                    logger.error(f"batch {i} failed: {e2}")
                    continue
            for p in parsed.values():
                f.write(json.dumps(p) + "\n")
            f.flush()
            if (i // 50) % 20 == 0:
                logger.info(f"fetched {i + len(batch)}/{len(todo)}")


def load_cache(db):
    resolver = Resolver(db)
    n = 0
    with open(CACHE) as f:
        for line in f:
            try:
                p = json.loads(line)
            except Exception:
                continue
            resolver.upsert_wikidata(p)
            n += 1
            if n % 1000 == 0:
                logger.info(f"loaded {n}")
    logger.success(f"backbone loaded: {n} items")
    # second pass: static relations whose targets arrived later in the file
    rows = db.execute_query("SELECT entity_id, metadata->'pending_relations' AS pend FROM entities WHERE metadata ? 'pending_relations'", fetch=True) or []
    logger.info(f"{len(rows)} entities with pending relations; re-linking")
    with open(CACHE) as f:
        by_qid = {}
        for line in f:
            try:
                p = json.loads(line); by_qid[p["qid"]] = p
            except Exception:
                pass
    relinked = 0
    for r in rows:
        ent = db.execute_query("SELECT qid FROM entities WHERE entity_id = %s", (r["entity_id"],), fetch=True)[0]
        p = by_qid.get(ent["qid"])
        if p:
            resolver._store_static_relations(r["entity_id"], p.get("relations", []))
            relinked += 1
    logger.success(f"relinked {relinked}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="load the cached jsonl without calling Wikidata")
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N q-ids")
    args = ap.parse_args()
    db = DatabaseManager()
    wikidata.set_db(db)   # share the Wikidata rate limit with the running agents
    if not args.offline:
        qids = collect_qids()
        if args.limit:
            qids = qids[:args.limit]
        logger.info(f"{len(qids)} unique q-ids")
        fetch_to_cache(qids)
    load_cache(db)
    db.close()
