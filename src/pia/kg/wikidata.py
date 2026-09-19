"""
Polite Wikidata client: search, batched entity fetch, SPARQL, and P31 → kind classification.
Never called in a tight loop without the resolver's caches in front of it.
"""
import os
import time
from typing import Dict, Iterable, List, Optional

import requests
from loguru import logger

from pia.kg.ontology import KIND_ROOTS, KNOWN_CLASS_KINDS, WIKIDATA_RELATION_PROPERTIES

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = os.getenv("WIKIDATA_USER_AGENT", "PIA-knowledge-web/1.0 (https://github.com/sebastian420-hub/pia)")
MIN_INTERVAL = float(os.getenv("WIKIDATA_MIN_INTERVAL_SEC", "0.6"))   # ≤ ~2 req/s

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
_last_call = 0.0
_db = None            # when set, all PIA processes share one rate limit through Postgres
_LOCK_KEY = 815191    # arbitrary advisory-lock id


def set_db(db):
    """Share the Wikidata rate limit across processes (analysts, maintenance, seed script)."""
    global _db
    _db = db


def _pace():
    """Waits so that, across every PIA process, Wikidata sees ≤ 1 request per MIN_INTERVAL."""
    global _last_call
    if _db is not None:
        try:
            with _db.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
                    try:
                        cur.execute("SELECT EXTRACT(EPOCH FROM (clock_timestamp() - last_call)) FROM rate_limits WHERE name = 'wikidata'")
                        row = cur.fetchone()
                        elapsed = float(row[0]) if row and row[0] is not None else MIN_INTERVAL
                        if elapsed < MIN_INTERVAL:
                            time.sleep(MIN_INTERVAL - elapsed)
                        cur.execute("INSERT INTO rate_limits (name, last_call) VALUES ('wikidata', clock_timestamp()) "
                                    "ON CONFLICT (name) DO UPDATE SET last_call = clock_timestamp()")
                    finally:
                        cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
            return
        except Exception as e:  # never let the limiter break a lookup
            logger.debug(f"shared pace failed ({e}); local pacing")
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _get(params: dict, timeout: int):
    """GET with backoff on 429/5xx (honours Retry-After)."""
    for attempt in range(4):
        _pace()
        r = _session.get(API, params=params, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After") or (5 * (attempt + 1)))
            logger.warning(f"wikidata {r.status_code}; sleeping {wait:.0f}s")
            time.sleep(min(wait, 60))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def search(text: str, lang: str = "en", limit: int = 5) -> List[Dict]:
    """wbsearchentities: [{id, label, description, match}]"""
    r = _get({"action": "wbsearchentities", "search": text, "language": lang,
              "uselang": "en", "type": "item", "limit": limit, "format": "json"}, timeout=20)
    return [{"qid": s["id"], "label": s.get("label"), "description": s.get("description", ""),
             "match": (s.get("match") or {}).get("text")} for s in r.json().get("search", [])]


def _claim_values(entity: dict, prop: str) -> List:
    out = []
    for claim in (entity.get("claims") or {}).get(prop, []):
        snak = claim.get("mainsnak") or {}
        if snak.get("snaktype") != "value":
            continue
        # skip deprecated / ended statements for roles
        if claim.get("rank") == "deprecated":
            continue
        quals = claim.get("qualifiers") or {}
        if "P582" in quals:  # end time present -> historical; keep but flag
            out.append((snak["datavalue"]["value"], True))
        else:
            out.append((snak["datavalue"]["value"], False))
    return out


def get_entities(qids: Iterable[str]) -> Dict[str, dict]:
    """wbgetentities in batches of 50 → {qid: parsed}"""
    qids = [q for q in dict.fromkeys(qids) if q]
    result = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        r = _get({"action": "wbgetentities", "ids": "|".join(batch),
                  "props": "labels|descriptions|aliases|claims|sitelinks",
                  "languages": "en|en-gb|de|fr|es|it|pt|nl", "format": "json"}, timeout=40)
        for qid, ent in (r.json().get("entities") or {}).items():
            if "missing" in ent:
                continue
            result[qid] = parse_entity(ent)
    return result


def parse_entity(ent: dict) -> dict:
    qid = ent["id"]
    labels = ent.get("labels") or {}
    label = next((labels[lg]["value"] for lg in ("en", "en-gb", "de", "fr", "es", "it", "pt", "nl") if lg in labels and labels[lg].get("value")), None) \
        or next((v.get("value") for v in labels.values() if v.get("value")), qid)
    desc = (ent.get("descriptions") or {}).get("en", {}).get("value")
    aliases = [a["value"] for a in (ent.get("aliases") or {}).get("en", [])]
    p31 = [v["id"] for v, _ in _claim_values(ent, "P31") if isinstance(v, dict) and "id" in v]
    coords = None
    for v, _ in _claim_values(ent, "P625"):
        if isinstance(v, dict) and "latitude" in v:
            coords = (v["latitude"], v["longitude"])
            break
    country = next((v["id"] for v, _ in _claim_values(ent, "P17") if isinstance(v, dict) and "id" in v), None)
    iso3 = next((v for v, _ in _claim_values(ent, "P298") if isinstance(v, str)), None)
    iso2 = next((v for v, _ in _claim_values(ent, "P297") if isinstance(v, str)), None)
    relations = []
    for prop, (kind, rel_label, directed) in WIKIDATA_RELATION_PROPERTIES.items():
        for v, ended in _claim_values(ent, prop):
            if isinstance(v, dict) and "id" in v:
                relations.append({"property": prop, "kind": kind, "label": rel_label, "target_qid": v["id"], "ended": ended})
    return {
        "qid": qid, "label": label, "description": desc, "aliases": aliases, "p31": p31,
        "coords": coords, "country_qid": country, "sitelinks": len(ent.get("sitelinks") or {}),
        "iso3": iso3, "iso2": iso2, "relations": relations,
    }


def sparql(query: str, timeout: int = 90) -> List[dict]:
    _pace()
    r = _session.get(SPARQL, params={"query": query}, headers={"Accept": "application/sparql-results+json"}, timeout=timeout)
    r.raise_for_status()
    rows = r.json()["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in rows]


def _superclasses(qids: List[str]) -> Dict[str, List[str]]:
    """P279 (subclass of) targets for each class, via the entity API (fast, cacheable)."""
    out: Dict[str, List[str]] = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        r = _get({"action": "wbgetentities", "ids": "|".join(batch), "props": "claims", "format": "json"}, timeout=30)
        for qid, ent in (r.json().get("entities") or {}).items():
            out[qid] = [v["id"] for v, _ in _claim_values(ent, "P279") if isinstance(v, dict) and "id" in v]
    return out


_ROOT_KIND = {q: kind for kind, qs in KIND_ROOTS for q in qs}
_class_memo: Dict[str, str] = {}


def classify_classes(class_qids: List[str], max_depth: int = 7) -> Dict[str, str]:
    """
    Many classes at once: one joint breadth-first walk over 'subclass of', so a backbone reload
    needs a few hundred requests instead of one walk per class. -> {class_qid: kind|UNKNOWN}
    """
    result: Dict[str, str] = {}
    frontier: Dict[str, List[str]] = {}          # class -> its current frontier of ancestors
    seen: Dict[str, set] = {}
    for c in dict.fromkeys(class_qids):
        if c in KNOWN_CLASS_KINDS:
            result[c] = KNOWN_CLASS_KINDS[c]
        elif c in _class_memo:
            result[c] = _class_memo[c]
        else:
            frontier[c] = [c]
            seen[c] = {c}
    parent_cache: Dict[str, List[str]] = {}
    try:
        for _ in range(max_depth):
            need = sorted({q for fr in frontier.values() for q in fr if q not in parent_cache})
            for i in range(0, len(need), 50):
                parent_cache.update(_superclasses(need[i:i + 50]))
            nxt: Dict[str, List[str]] = {}
            for c, fr in frontier.items():
                new = []
                hit = None
                for q in fr:
                    for p in parent_cache.get(q, []):
                        if p in _ROOT_KIND or p in KNOWN_CLASS_KINDS:
                            hit = _ROOT_KIND.get(p) or KNOWN_CLASS_KINDS[p]
                            break
                        if p not in seen[c]:
                            seen[c].add(p)
                            new.append(p)
                    if hit:
                        break
                if hit:
                    result[c] = hit
                    _class_memo[c] = hit
                elif new:
                    nxt[c] = new[:60]
            frontier = nxt
            if not frontier:
                break
    except Exception as e:
        logger.warning(f"classify_classes: {e}")
    for c in frontier:                            # ran out of depth or failed: unknown for now
        result.setdefault(c, "UNKNOWN")
    for c in class_qids:
        result.setdefault(c, "UNKNOWN")
    return result


def classify_class(class_qid: str, max_depth: int = 7) -> Optional[str]:
    """
    kind for a P31 class by walking 'subclass of' upwards (breadth-first, ≤ max_depth levels)
    until a known root is met. Uses the entity API, not SPARQL (which times out on P279*).
    """
    if class_qid in KNOWN_CLASS_KINDS:
        return KNOWN_CLASS_KINDS[class_qid]
    if class_qid in _class_memo:
        return _class_memo[class_qid]
    frontier, seen = [class_qid], {class_qid}
    try:
        for _ in range(max_depth):
            parents = _superclasses(frontier)
            nxt = []
            for qid in frontier:
                for p in parents.get(qid, []):
                    if p in _ROOT_KIND or p in KNOWN_CLASS_KINDS:
                        kind = _ROOT_KIND.get(p) or KNOWN_CLASS_KINDS[p]
                        _class_memo[class_qid] = kind
                        return kind
                    if p not in seen:
                        seen.add(p)
                        nxt.append(p)
            if not nxt:
                break
            frontier = nxt[:60]
    except Exception as e:
        logger.warning(f"classify_class {class_qid}: {e}")
        return None
    _class_memo[class_qid] = "UNKNOWN"
    return "UNKNOWN"
