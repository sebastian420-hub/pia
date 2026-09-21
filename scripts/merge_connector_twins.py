"""
Connector entities that the web already knew under another name — "Open Joint Stock Company Rosneft
Oil Company" (OpenSanctions, local) and "Rosneft" (Wikidata Q1141123) — become one node: the sanctions
listings and facts move onto the Wikidata item. Only unambiguous twins: one alias, one same-kind Wikidata
item, the alias a real name (two words, eight letters); never people. Idempotent. Run after a connector load; the ingestor now does this
at load time, so this is for what landed before.
"""
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger

from pia.core.database import DatabaseManager
from pia.kg.names import merge
from pia.kg.normalize import bare_name


BUSINESS_WORDS = r"\m(company|corporation|bank|airline|enterprise|manufacturer|conglomerate|firm|producer|holding|operator|insurer|retailer|shipping|telecommunications|business|subsidiary|brand)\M"


def main(dry: bool):
    db = DatabaseManager()
    rows = db.execute_query("""
        WITH twins AS (
            SELECT l.entity_id AS loser, l.name AS lname, l.kind, w.entity_id AS keeper, w.name AS kname, w.qid, a.alias
            FROM entities l
            JOIN entity_aliases a ON a.entity_id = l.entity_id
            JOIN entity_aliases b ON b.alias_norm = a.alias_norm
            JOIN entities w ON w.entity_id = b.entity_id AND w.qid IS NOT NULL AND w.resolution = 'RESOLVED' AND w.kind = l.kind
                 AND (w.country_qid IS NULL OR l.country_qid IS NULL OR w.country_qid = l.country_qid)   -- an Iranian academy is not the US one
            WHERE l.resolution = 'LOCAL' AND (l.origin LIKE 'opensanctions%%' OR l.origin = 'gleif') AND l.qid IS NULL
              AND l.kind <> 'PERSON' AND array_length(string_to_array(a.alias_norm, ' '), 1) >= 2 AND length(a.alias_norm) >= 8
        )
        SELECT loser, lname, kind, keeper, kname, qid, MIN(alias) AS alias
        FROM twins GROUP BY loser, lname, kind, keeper, kname, qid
    """, fetch=True) or []
    # rule B: the name minus its corporate-form words is a name the web knows ("… Rosneft Oil Company" → Rosneft)
    locals_ = db.execute_query("""
        SELECT entity_id, name, kind, country_qid FROM entities
        WHERE resolution = 'LOCAL' AND origin LIKE 'opensanctions%%' AND qid IS NULL AND kind <> 'PERSON'
    """, fetch=True) or []
    for l in locals_:
        bare = bare_name(l["name"])
        if len(bare) < 6 or bare == l["name"].lower():
            continue
        # the keeper must be a proper noun (not the concept "investment bank"), and a one-word bare name
        # ("Rosneft", not "Endurance" the ship or "Bourbon" the house) must name something described as a business
        hits = db.execute_query("""
            SELECT DISTINCT w.entity_id AS keeper, w.name AS kname, w.qid FROM entity_aliases b JOIN entities w ON w.entity_id = b.entity_id
            WHERE b.alias_norm = %s AND w.qid IS NOT NULL AND w.resolution = 'RESOLVED' AND w.kind = %s
              AND (w.country_qid IS NULL OR %s IS NULL OR w.country_qid = %s)
              AND left(w.name, 1) = upper(left(w.name, 1)) AND left(w.name, 1) <> lower(left(w.name, 1))
              AND (%s OR (w.kind = 'ORG' AND COALESCE(w.description, '') ~* %s))
        """, (bare, l["kind"], l["country_qid"], l["country_qid"], " " in bare, BUSINESS_WORDS), fetch=True) or []
        for h in hits:
            rows.append({"loser": l["entity_id"], "lname": l["name"], "kind": l["kind"], "keeper": h["keeper"], "kname": h["kname"],
                         "qid": h["qid"], "alias": f"bare:{bare}"})
    # generic institutional names ("Ministry of Home Affairs", "Central Bank") exist in every country: they
    # join only when both sides say the same country; and nothing joins a country's own name
    import re
    GENERIC = re.compile(r"^(ministry|department|office|bureau|council|central bank|bank|national|federal|state|government|republic|kingdom|people'?s) ", re.I)
    country_names = {r["alias_norm"] for r in (db.execute_query(
        "SELECT a.alias_norm FROM entity_aliases a JOIN entities e ON e.entity_id = a.entity_id WHERE e.kind = 'COUNTRY'", fetch=True) or [])}
    countries = {str(r["entity_id"]): r["country_qid"] for r in (db.execute_query("SELECT entity_id, country_qid FROM entities WHERE country_qid IS NOT NULL", fetch=True) or [])}
    kept = []
    for r in rows:
        alias = str(r["alias"]).replace("bare:", "").lower()
        if alias in country_names:
            continue
        if GENERIC.match(alias) or GENERIC.match(r["lname"]):
            lc, kc = countries.get(str(r["loser"])), countries.get(str(r["keeper"]))
            if not lc or not kc or lc != kc:
                continue
        kept.append(r)
    rows = kept
    # one keeper per loser only
    by_loser = {}
    for r in rows:
        by_loser.setdefault(str(r["loser"]), []).append(r)
    done = skipped = 0
    for loser, cands in by_loser.items():
        keepers = {str(c["keeper"]) for c in cands}
        if len(keepers) != 1:
            skipped += 1
            continue
        c = cands[0]
        logger.info(f"{c['lname']!r} → {c['kname']} ({c['qid']}) via {c['alias']!r}")
        if not dry:
            merge(db, loser, str(c["keeper"]), c["lname"], f"connector twin via {c['alias']}")
        done += 1
    logger.success(f"{'would merge' if dry else 'merged'} {done}, ambiguous skipped {skipped}")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
