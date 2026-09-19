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
CLASS_CACHE = os.path.join("data", "wikidata_classes.jsonl")   # class_qid → kind, so a reload needs no class walks

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


def import_class_cache(db):
    """wikidata_classes from data/wikidata_classes.jsonl (written by export_class_cache)."""
    if not os.path.exists(CLASS_CACHE):
        return 0
    rows = []
    with open(CLASS_CACHE) as f:
        for line in f:
            try:
                d = json.loads(line)
                rows.append((d["class_qid"], d.get("label"), d["kind"]))
            except Exception:
                continue
    if rows:
        db.execute_values("INSERT INTO wikidata_classes (class_qid, label, kind) VALUES %s ON CONFLICT (class_qid) DO NOTHING", rows)
    return len(rows)


def export_class_cache(db):
    rows = db.execute_query("SELECT class_qid, label, kind FROM wikidata_classes", fetch=True) or []
    with open(CLASS_CACHE, "w") as f:
        for r in rows:
            f.write(json.dumps({"class_qid": r["class_qid"], "label": r["label"], "kind": r["kind"]}) + "\n")
    return len(rows)


def load_cache(db):
    """
    Two phases so a reload is minutes, not hours:
      1. every item is upserted with the kind its P31 classes already give (KNOWN_CLASS_KINDS +
         wikidata_classes); classes nobody knows are provisionally UNKNOWN — no network calls
      2. the distinct unknown classes are walked on Wikidata once each, cached in
         wikidata_classes (and data/wikidata_classes.jsonl), and the affected entities re-typed
    """
    from pia.kg.ontology import KNOWN_CLASS_KINDS
    resolver = Resolver(db)
    n_classes = import_class_cache(db)
    known = dict(KNOWN_CLASS_KINDS)
    for r in db.execute_query("SELECT class_qid, kind FROM wikidata_classes", fetch=True) or []:
        known[r["class_qid"]] = r["kind"]
    logger.info(f"{len(known)} classes known ({n_classes} from {CLASS_CACHE})")

    items, unknown = [], set()
    with open(CACHE) as f:
        for line in f:
            try:
                p = json.loads(line)
            except Exception:
                continue
            items.append(p)
            for cls in p.get("p31", [])[:5]:
                if cls not in known:
                    unknown.add(cls)
    # phase 1: provisional kinds, no network
    resolver._class_cache.update(known)
    resolver._class_cache.update({c: "UNKNOWN" for c in unknown})
    n = 0
    for p in items:
        resolver.upsert_wikidata(p)
        n += 1
        if n % 5000 == 0:
            logger.info(f"loaded {n}/{len(items)}")
    logger.success(f"backbone loaded: {n} items; {len(unknown)} classes still to classify")

    # second pass: static relations whose targets arrived later in the file
    rows = db.execute_query("SELECT entity_id, metadata->'pending_relations' AS pend FROM entities WHERE metadata ? 'pending_relations'", fetch=True) or []
    logger.info(f"{len(rows)} entities with pending relations; re-linking")
    by_qid = {p["qid"]: p for p in items}
    relinked = 0
    for r in rows:
        ent = db.execute_query("SELECT qid FROM entities WHERE entity_id = %s", (r["entity_id"],), fetch=True)[0]
        p = by_qid.get(ent["qid"])
        if p:
            resolver._store_static_relations(r["entity_id"], p.get("relations", []))
            relinked += 1
    logger.success(f"relinked {relinked}")

    # phase 2: classify the unknown classes (network, ~1 req/s shared limit), then re-type entities
    if unknown:
        logger.info(f"classifying {len(unknown)} classes on Wikidata (joint walk) …")
        todo = sorted(unknown)
        for i in range(0, len(todo), 500):
            kinds = wikidata.classify_classes(todo[i:i + 500])
            db.execute_values("INSERT INTO wikidata_classes (class_qid, kind) VALUES %s ON CONFLICT (class_qid) DO UPDATE SET kind = EXCLUDED.kind",
                              list(kinds.items()))
            known.update(kinds)
            logger.info(f"classified {min(i + 500, len(todo))}/{len(todo)}")
            retype_unknown(db, items, known)
            export_class_cache(db)
    logger.info(f"class cache written: {export_class_cache(db)} classes → {CLASS_CACHE}")


def retype_unknown(db, items, known):
    """Entities still UNKNOWN whose P31 now maps to a kind."""
    changed = 0
    for p in items:
        for cls in p.get("p31", [])[:5]:
            k = known.get(cls)
            if k and k != "UNKNOWN":
                res = db.execute_query("UPDATE entities SET kind = %s WHERE qid = %s AND kind = 'UNKNOWN' RETURNING 1", (k, p["qid"]), fetch=True)
                changed += 1 if res else 0
                break
    if changed:
        logger.info(f"re-typed {changed} entities")
    return changed


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
