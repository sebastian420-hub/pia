"""
GLEIF connector: the official register of legal entities (3.4M LEIs) and who consolidates whom.

Not "load everything": seed and grow. The seed is every LEI the web already holds (OpenSanctions
leiCode, Wikidata P1278); the relationship file (24 MB, daily) is walked `hops` steps up and down the
consolidation edges from the seed; only the LEI records of that grown set are fetched (public JSON:API,
no key, 200 per page, cached on disk). Facts keep GLEIF's own words: "directly consolidated by",
"ultimately consolidated by", "international branch of" — accounting consolidation, not a percentage.
Fund edges (IS_FUND-MANAGED_BY, IS_SUBFUND_OF) are off by default. Data is CC0.
"""
import csv
import io
import json
import os
import time
import zipfile
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set

import requests
from loguru import logger

from pia.connectors.base import Connector, Entity, Fact, Item

API = "https://api.gleif.org/api/v1"
GOLDEN = "https://goldencopy.gleif.org/api/v2/golden-copies/publishes"
HEADERS = {"Accept": "application/vnd.api+json", "User-Agent": "PIA-gleif-connector/1.0"}

CONSOLIDATION = {"IS_DIRECTLY_CONSOLIDATED_BY": "directly consolidated by",
                 "IS_ULTIMATELY_CONSOLIDATED_BY": "ultimately consolidated by",
                 "IS_INTERNATIONAL_BRANCH_OF": "international branch of"}
FUNDS = {"IS_FUND-MANAGED_BY": "fund managed by", "IS_SUBFUND_OF": "sub-fund of", "IS_FEEDER_TO": "feeder fund of"}


class GleifConnector(Connector):
    def __init__(self, db, hops: int = 2, funds: bool = False, cache_dir: Optional[str] = None,
                 rr_path: Optional[str] = None, seed: Optional[Set[str]] = None, iso2_to_qid: Optional[Dict[str, str]] = None):
        self.db, self.hops, self.funds = db, hops, funds
        self.cache_dir = cache_dir or os.getenv("GLEIF_CACHE", "/app/data/gleif")
        self.rr_path = rr_path
        self._seed = seed
        self.source = {"source_id": "gleif", "label": "GLEIF · LEI register", "kind": "DATASET", "trust": 0.95,
                       "homepage": "https://www.gleif.org"}
        if iso2_to_qid is None and db is not None:
            rows = db.execute_query("SELECT metadata->>'iso2' AS iso2, qid FROM entities WHERE kind = 'COUNTRY' AND metadata ? 'iso2'", fetch=True) or []
            iso2_to_qid = {r["iso2"].upper(): r["qid"] for r in rows if r["iso2"]}
        self.iso2 = iso2_to_qid or {}
        self.edges = dict(CONSOLIDATION, **(FUNDS if funds else {}))

    # ── seed ──
    def seed(self) -> Set[str]:
        if self._seed is not None:
            return set(self._seed)
        rows = self.db.execute_query("SELECT DISTINCT upper(regexp_replace(external_id, '^lei:', '')) AS lei FROM external_ids WHERE kind = 'lei'", fetch=True) or []
        return {r["lei"] for r in rows if r["lei"] and len(r["lei"]) == 20}

    # ── relationships ──
    def relationship_rows(self) -> Iterable[Dict]:
        """Rows of the RR golden copy (a CSV inside a zip); downloaded fresh unless rr_path is given."""
        if self.rr_path:
            f = open(self.rr_path, "rb")
            data = f.read(); f.close()
        else:
            meta = requests.get(f"{GOLDEN}/rr/latest", timeout=60, headers=HEADERS).json()
            url = meta["data"]["full_file"]["csv"]["url"]
            logger.info(f"gleif: relationship file {url}")
            data = requests.get(url, timeout=600).content
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = [n for n in z.namelist() if n.endswith(".csv")][0]
            with z.open(name) as fh:
                for row in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8")):
                    yield row

    def grow(self, seed: Set[str], rows: Iterable[Dict]):
        """Walk `hops` steps of the chosen edges from the seed. Returns (grown set, kept edge rows)."""
        up: Dict[str, List[Dict]] = defaultdict(list)     # child → edges to parents
        down: Dict[str, List[Dict]] = defaultdict(list)   # parent → edges to children
        for r in rows:
            t = r.get("Relationship.RelationshipType")
            if t not in self.edges or r.get("Relationship.RelationshipStatus") not in ("ACTIVE", "INACTIVE"):
                continue
            a, b = r.get("Relationship.StartNode.NodeID", "").upper(), r.get("Relationship.EndNode.NodeID", "").upper()
            if len(a) != 20 or len(b) != 20:
                continue
            e = {"child": a, "parent": b, "type": t, "status": r.get("Relationship.RelationshipStatus"),
                 "start": r.get("Relationship.Period.1.startDate") or None, "end": r.get("Relationship.Period.1.endDate") or None,
                 "ref": r.get("Registration.ValidationReference") or None, "validation": r.get("Registration.ValidationSources") or None}
            up[a].append(e)
            down[b].append(e)
        grown, frontier, kept = set(seed), set(seed), []
        seen_edges = set()
        for _ in range(self.hops):
            nxt = set()
            for lei in frontier:
                for e in up.get(lei, []) + down.get(lei, []):
                    key = (e["child"], e["parent"], e["type"])
                    if key not in seen_edges:
                        seen_edges.add(key); kept.append(e)
                    for other in (e["child"], e["parent"]):
                        if other not in grown:
                            nxt.add(other)
            grown |= nxt
            frontier = nxt
            if not frontier:
                break
        return grown, kept

    # ── LEI records ──
    def _cached(self, lei: str) -> Optional[Dict]:
        p = os.path.join(self.cache_dir, lei[:2], lei + ".json")
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400:
            with open(p) as f:
                return json.load(f)
        return None

    def _store(self, lei: str, rec: Dict):
        d = os.path.join(self.cache_dir, lei[:2])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, lei + ".json"), "w") as f:
            json.dump(rec, f)

    def records(self, leis: Set[str]) -> Iterable[Dict]:
        todo = []
        for lei in sorted(leis):
            c = self._cached(lei)
            if c:
                yield c
            else:
                todo.append(lei)
        logger.info(f"gleif: {len(leis) - len(todo)} records cached, {len(todo)} to fetch")
        for i in range(0, len(todo), 200):
            batch = todo[i:i + 200]
            for attempt in range(4):
                r = requests.get(f"{API}/lei-records", params={"filter[lei]": ",".join(batch), "page[size]": 200}, headers=HEADERS, timeout=60)
                if r.status_code == 429:
                    time.sleep(15 * (attempt + 1)); continue
                r.raise_for_status()
                break
            for rec in (r.json().get("data") or []):
                self._store(rec["id"], rec)
                yield rec
            time.sleep(1.1)     # ≤ 60 requests a minute

    # ── items ──
    def entity_from(self, rec: Dict) -> Entity:
        a = rec["attributes"]; e = a["entity"]
        legal = (e.get("legalName") or {}).get("name") or rec["id"]
        others = [o.get("name") for o in (e.get("otherNames") or []) if o.get("name")]
        translit = [o.get("name") for o in (e.get("transliteratedOtherNames") or []) if o.get("name")]
        latin = [n for n in others + translit if n and all(ord(ch) < 0x250 for ch in n)]
        name = latin[0] if latin and not all(ord(ch) < 0x250 for ch in legal) else legal
        aliases = [n for n in [legal] + others + translit if n and n != name]
        addr = e.get("legalAddress") or {}
        hq = e.get("headquartersAddress") or {}
        cc = (addr.get("country") or "").upper()
        props = {"lei_status": e.get("status"), "registration_status": (a.get("registration") or {}).get("status"),
                 "legal_form": (e.get("legalForm") or {}).get("id"), "registered_as": e.get("registeredAs"),
                 "jurisdiction": e.get("jurisdiction"), "category": e.get("category"), "city": addr.get("city"),
                 "hq_city": hq.get("city"), "hq_country": hq.get("country"), "creation_date": e.get("creationDate")}
        other_ids = [("lei", rec["id"])]
        if e.get("registeredAs"):
            other_ids.append(("registration", e["registeredAs"]))
        if a.get("bic"):
            other_ids += [("bic", b) for b in a["bic"][:3]]
        return Entity(external_id=rec["id"], kind="ORG", name=name[:200], aliases=aliases[:30], country_qid=self.iso2.get(cc),
                      properties={k: v for k, v in props.items() if v}, other_ids=other_ids)

    def pull(self, since: Optional[datetime] = None) -> Iterable[Item]:
        seed = self.seed()
        logger.info(f"gleif: seed {len(seed)} LEIs, {self.hops} hops, funds {'on' if self.funds else 'off'}")
        grown, edges = self.grow(seed, self.relationship_rows())
        logger.info(f"gleif: grown to {len(grown)} LEIs with {len(edges)} edges")
        have = set()
        for rec in self.records(grown):
            have.add(rec["id"])
            yield self.entity_from(rec)
        # one fact per pair: "directly consolidated by" already implies "ultimately"; the ultimate edge is kept only
        # where it is the sole link (a parent reached through intermediates)
        direct = {(e["child"], e["parent"]) for e in edges if e["type"] == "IS_DIRECTLY_CONSOLIDATED_BY"}
        for e in edges:
            if e["type"] == "IS_ULTIMATELY_CONSOLIDATED_BY" and (e["child"], e["parent"]) in direct:
                continue
            if e["child"] in have and e["parent"] in have:
                yield Fact(subject_external_id=e["child"], predicate=self.edges[e["type"]], object_external_id=e["parent"],
                           family="NEUTRAL·ownership", valid_from=(e["start"] or "")[:10] or None, valid_to=(e["end"] or "")[:10] or None,
                           record_ref=e["ref"] or f"gleif:{e['child']}>{e['parent']}",
                           properties={"status": e["status"], "validation": e["validation"], "relationship": e["type"]})
