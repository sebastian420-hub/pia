"""
Connectors: one way in for any source.

A connector turns *its* source's format into four shapes the engine already understands:

  Entity    a thing with the source's own id (passport, register number, FtM id …)
  Fact      subject — predicate — object, valid for a period, with a record pointer (proof)
  Event     actor — predicate — target at a time (structured rows: payments, calls, crossings)
  Document  text to be read by the analysts like an article

The framework (Ingestor) does identity (external id → entity, then Wikidata, then name), verbs
(predicates go through the catalogue), provenance (source_id + record_ref), trust (the source's),
and hands Documents to the normal reader / verifier path. Facts and Events from structured
sources are marked origin = 'connector' and skip the verifier: a row is a row.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple, Union

from loguru import logger

from pia.kg.normalize import bare_name, normalize
from pia.kg.verbs import VerbCatalogue, guard_family


@dataclass
class Entity:
    external_id: str
    kind: str                                  # PERSON | ORG | COUNTRY | PLACE | VESSEL | AIRCRAFT | EVENT | UNKNOWN
    name: str
    aliases: List[str] = field(default_factory=list)
    description: Optional[str] = None
    country_qid: Optional[str] = None
    geo: Optional[Tuple[float, float]] = None   # (lat, lon)
    properties: Dict = field(default_factory=dict)
    wikidata_qid: Optional[str] = None
    other_ids: List[Tuple[str, str]] = field(default_factory=list)   # (kind, value): ("passport", "X1234")
    listings: List[Dict] = field(default_factory=list)                # [{"list": "OFAC SDN", "since": "2019-04-08", "program": "IRGC"}]


@dataclass
class Identifier:
    """A hard identifier for an entity that arrives as its own record (FtM Passport / Identification)."""
    holder_external_id: str
    kind: str          # passport | id | tax | registration | imo | mmsi | wallet
    value: str
    properties: Dict = field(default_factory=dict)


@dataclass
class Fact:
    subject_external_id: str
    predicate: str                             # "sanctioned by", "owned by", "director of"
    object_external_id: Optional[str] = None
    object_name: Optional[str] = None          # when the object is not an entity of the source (an authority name)
    family: str = "NEUTRAL·ownership"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    record_ref: str = ""
    properties: Dict = field(default_factory=dict)


@dataclass
class Event:
    actor_external_id: str
    predicate: str
    target_external_id: Optional[str]
    time: datetime
    family: str = "NEUTRAL·statement"
    stance: int = 0
    topic: str = "other"
    place: Optional[Tuple[float, float]] = None
    quote: Optional[str] = None
    record_ref: str = ""
    confidence: float = 0.8


@dataclass
class Document:
    external_id: str
    title: str
    text: str
    published: Optional[datetime] = None
    url: Optional[str] = None
    language: str = "en"
    domain: str = "POLITICAL"
    source_type: str = "OSINT"                 # HUMINT for human reports
    mission_id: Optional[str] = None
    geo: Optional[Tuple[float, float]] = None  # (lat, lon)
    extra: Dict = field(default_factory=dict)  # lands in metadata


Item = Union[Entity, Fact, Event, Document, Identifier]


class Connector:
    """Subclass: set `source` and implement `pull()`."""
    source: Dict = {"source_id": "", "label": "", "kind": "DATASET", "trust": 0.9, "homepage": None}

    def pull(self, since: Optional[datetime] = None) -> Iterable[Item]:
        raise NotImplementedError


class Ingestor:
    """Writes connector items into the store. Idempotent by (source_id, external_id) and record_ref."""

    def __init__(self, db, resolver, verbs: Optional[VerbCatalogue] = None):
        self.db = db
        self.resolver = resolver
        self.verbs = verbs or VerbCatalogue(db)
        self._cache: Dict[Tuple[str, str], str] = {}

    def ensure_source(self, source: Dict):
        self.db.execute_query("""
            INSERT INTO sources (source_id, label, kind, trust, homepage) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source_id) DO UPDATE SET label = EXCLUDED.label, trust = EXCLUDED.trust, homepage = EXCLUDED.homepage
        """, (source["source_id"], source["label"], source.get("kind", "DATASET"), source.get("trust", 0.9), source.get("homepage")))

    # ── identity ──
    def entity_for(self, source_id: str, external_id: str) -> Optional[str]:
        key = (source_id, external_id)
        if key in self._cache:
            return self._cache[key]
        row = self.db.execute_query("SELECT entity_id FROM external_ids WHERE source_id = %s AND external_id = %s", key, fetch=True)
        if row:
            self._cache[key] = str(row[0]["entity_id"])
            return self._cache[key]
        return None

    def upsert_entity(self, source_id: str, e: Entity) -> str:
        """external id → existing entity; else Wikidata Q-id; else name resolution (local only); else new local entity."""
        eid = self.entity_for(source_id, e.external_id)
        if not eid and e.wikidata_qid:
            ent = self.resolver.ensure_qid(e.wikidata_qid)
            eid = str(ent["entity_id"]) if ent else None
        if not eid:
            # the name, then the aliases ("Open Joint Stock Company Rosneft Oil Company" is also "PJSC Rosneft"):
            # the first that the web already knows under the same kind wins. Aliases count only when they are
            # a real name (two words, eight letters — never "DEC", "Bas", "Altair"), and never for people: a
            # sanctioned "Muhammad Ali" is not the boxer, and kunyas ("Abu Bakr") name many men
            tries = [e.name]
            if e.kind != "PERSON":
                tries += [a for a in e.aliases if len(a.split()) >= 2 and len(a) >= 8]
                bare = bare_name(e.name)
                if len(bare) >= 6 and bare != normalize(e.name):
                    tries.append(bare)
            for name in tries:
                ent = self.resolver.resolve(name, kind_hint=e.kind, role="MENTIONED",
                                            context={"country_qid": e.country_qid}, local_only=True)
                # a typed entity must match its kind; an untyped name ("Iran" as an event actor) takes whatever the web knows
                if ent and ent.get("resolution") == "RESOLVED" and (e.kind == "UNKNOWN" or ent.get("kind") == e.kind):
                    eid = str(ent["entity_id"])
                    break
        if not eid:
            geo = f"SRID=4326;POINT({e.geo[1]} {e.geo[0]})" if e.geo else None
            row = self.db.execute_query("""
                INSERT INTO entities (kind, name, description, resolution, origin, country_qid, primary_geo, metadata, properties)
                VALUES (%s, %s, %s, 'LOCAL', %s, %s, %s::geometry, %s::jsonb, %s::jsonb) RETURNING entity_id
            """, (e.kind, e.name[:200], e.description, source_id, e.country_qid, geo,
                  '{"connector": "%s"}' % source_id, _json(e.properties)), fetch=True)
            eid = str(row[0]["entity_id"])
        else:
            self.db.execute_query("""
                UPDATE entities SET properties = properties || %s::jsonb,
                       description = COALESCE(description, %s), country_qid = COALESCE(country_qid, %s)
                WHERE entity_id = %s
            """, (_json(e.properties), e.description, e.country_qid, eid))
        # ids and aliases
        for kind, value in [("ftm" if source_id.startswith("opensanctions") else "id", e.external_id)] + list(e.other_ids):
            self.db.execute_query("""
                INSERT INTO external_ids (source_id, external_id, entity_id, kind) VALUES (%s, %s, %s, %s)
                ON CONFLICT (source_id, external_id) DO NOTHING
            """, (source_id, value, eid, kind))
        names = [n for n in {e.name, *e.aliases} if n and normalize(n)]
        if names:
            self.db.execute_values(
                "INSERT INTO entity_aliases (entity_id, alias, alias_norm, source) VALUES %s ON CONFLICT (entity_id, alias_norm) DO NOTHING",
                [(eid, n[:200], normalize(n)) for n in names], template=f"(%s, %s, %s, '{source_id}')")
        if e.listings:
            self.db.execute_query("""
                UPDATE entities SET listings = (
                    SELECT COALESCE(jsonb_agg(DISTINCT x), '[]'::jsonb) FROM jsonb_array_elements(listings || %s::jsonb) x)
                WHERE entity_id = %s
            """, (_json(e.listings), eid))
        self._cache[(source_id, e.external_id)] = eid
        return eid

    # ── facts ──
    def upsert_fact(self, source_id: str, f: Fact) -> bool:
        a = self.entity_for(source_id, f.subject_external_id)
        if not a:
            return False
        b = self.entity_for(source_id, f.object_external_id) if f.object_external_id else None
        if not b and f.object_name:
            b = self._authority(source_id, f.object_name)
        if not b or a == b:
            return False
        family = guard_family(f.family, 0)
        kind = {"NEUTRAL·ownership": "OWNERSHIP", "NEUTRAL·role": "ROLE"}.get(family, "MEMBERSHIP")
        vid, verb, _ = self.verbs.canonical(f.predicate, family, 0)
        label = f.predicate.strip().lower()[:60]          # facts keep the source's wording ("sanctioned by")
        if f.properties.get("listing"):
            self.db.execute_query("""
                UPDATE entities SET listings = (
                    SELECT COALESCE(jsonb_agg(DISTINCT x), '[]'::jsonb) FROM jsonb_array_elements(listings || %s::jsonb) x)
                WHERE entity_id = %s
            """, (_json([f.properties["listing"]]), a))
        self.db.execute_query("""
            INSERT INTO relations (a_id, b_id, kind, source, label, directed, first_seen, last_seen, event_count, weight,
                                   via_source, record_ref, properties, updated_at)
            VALUES (%s, %s, %s, 'connector', %s, TRUE, %s, %s, 1, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (a_id, b_id, kind, source) DO UPDATE SET
                label = EXCLUDED.label, first_seen = LEAST(relations.first_seen, EXCLUDED.first_seen),
                last_seen = GREATEST(relations.last_seen, EXCLUDED.last_seen), weight = EXCLUDED.weight,
                via_source = EXCLUDED.via_source, record_ref = EXCLUDED.record_ref,
                properties = relations.properties || EXCLUDED.properties, updated_at = NOW()
        """, (a, b, kind, label, _date(f.valid_from), _date(f.valid_to), 1.0 if not f.valid_to else 0.5,
              source_id, f.record_ref, _json(f.properties)))
        return True

    def _authority(self, source_id: str, name: str) -> Optional[str]:
        """An object named only by text (a sanctioning authority): resolve to a known ORG/COUNTRY or a local one."""
        key = (source_id, "name:" + normalize(name))
        if key in self._cache:
            return self._cache[key]
        ent = self.resolver.resolve(name, kind_hint="ORG", role="MENTIONED", local_only=True)
        if ent and ent.get("resolution") == "RESOLVED":
            eid = str(ent["entity_id"])
        else:
            row = self.db.execute_query("""
                INSERT INTO entities (kind, name, resolution, origin, metadata) VALUES ('ORG', %s, 'LOCAL', %s, '{"authority": true}'::jsonb)
                RETURNING entity_id
            """, (name[:200], source_id), fetch=True)
            eid = str(row[0]["entity_id"])
            self.db.execute_query("INSERT INTO entity_aliases (entity_id, alias, alias_norm, source) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                                  (eid, name[:200], normalize(name), source_id))
        self._cache[key] = eid
        return eid

    # ── events ──
    def upsert_event(self, source_id: str, ev: Event) -> bool:
        a = self.entity_for(source_id, ev.actor_external_id)
        t = self.entity_for(source_id, ev.target_external_id) if ev.target_external_id else None
        if not a:
            return False
        family = guard_family(ev.family, ev.stance)
        vid, verb, _ = self.verbs.canonical(ev.predicate, family, ev.stance)
        kind = "HOSTILE" if ev.stance <= -1 else "COOPERATIVE" if ev.stance >= 1 else None
        geo = f"SRID=4326;POINT({ev.place[1]} {ev.place[0]})" if ev.place else None
        import hashlib
        dedup = hashlib.sha1(f"{source_id}|{ev.record_ref or ''}|{a}|{t or ''}|{verb}|{ev.time.date()}".encode()).hexdigest()
        self.db.execute_query("""
            INSERT INTO events (event_time, time_precision, action, kind, actor_id, target_id, geo, source_id, origin, quote,
                                confidence, tone, topic, weight_class, predicate, verb_id, family, stance, modality, polarity,
                                record_ref, dedup_key)
            VALUES (%s, 'day', 'OTHER', %s, %s, %s, %s::geometry, %s, 'connector', %s, %s, %s, %s, 'material',
                    %s, %s, %s, %s, 'asserted', TRUE, %s, %s)
            ON CONFLICT (dedup_key, event_time) DO NOTHING
        """, (ev.time, kind, a, t, geo, source_id, ev.quote, ev.confidence, float(ev.stance * 3), ev.topic,
              ev.predicate[:80], vid, family, ev.stance, ev.record_ref, dedup))
        return True

    # ── documents ──
    def upsert_document(self, source_id: str, d: Document) -> bool:
        import hashlib
        h = hashlib.sha256(f"{source_id}|{d.external_id}".encode()).hexdigest()
        meta = dict(d.extra, connector=source_id, external_id=d.external_id)
        geo = f"SRID=4326;POINT({d.geo[1]} {d.geo[0]})" if d.geo else None
        rows = self.db.execute_query("""
            INSERT INTO intelligence_records (source_type, source_id, source_agent, source_name, source_url, published_at, content_hash,
                                              content_headline, content_summary, content_raw, body_status, body_fetched_at, domain, priority,
                                              confidence, language, metadata, mission_id, geo, geo_precision, geo_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'OK', NOW(), %s, %s, 0.7, %s, %s::jsonb, %s,
                    %s::geometry, CASE WHEN %s::geometry IS NULL THEN NULL ELSE 'exact' END, CASE WHEN %s::geometry IS NULL THEN NULL ELSE 'reporter' END)
            ON CONFLICT (content_hash) DO NOTHING RETURNING uid
        """, (d.source_type, source_id, f"connector:{source_id}", source_id, d.url, d.published, h, d.title[:300], d.text[:400], d.text,
              d.domain, 'HIGH' if d.source_type == 'HUMINT' else 'NORMAL', d.language, _json(meta), d.mission_id, geo, geo, geo), fetch=True)
        return bool(rows)

    # ── run ──
    def run(self, connector: Connector, since: Optional[datetime] = None) -> Dict[str, int]:
        src = connector.source
        self.ensure_source(src)
        run = self.db.execute_query("INSERT INTO connector_runs (source_id) VALUES (%s) RETURNING run_id", (src["source_id"],), fetch=True)[0]["run_id"]
        stats = {"entities": 0, "facts": 0, "events": 0, "documents": 0, "identifiers": 0, "skipped": 0}
        pending_facts: List[Fact] = []
        pending_ids: List[Identifier] = []
        try:
            for item in connector.pull(since):
                if isinstance(item, Entity):
                    self.upsert_entity(src["source_id"], item); stats["entities"] += 1
                elif isinstance(item, Fact):
                    pending_facts.append(item)          # facts after entities: their ends may come later in the stream
                elif isinstance(item, Identifier):
                    pending_ids.append(item)
                elif isinstance(item, Event):
                    stats["events"] += int(self.upsert_event(src["source_id"], item))
                elif isinstance(item, Document):
                    stats["documents"] += int(self.upsert_document(src["source_id"], item))
                n = sum(stats.values())
                if n and n % 20000 == 0:
                    logger.info(f"{src['source_id']}: {stats}")
            for f in pending_facts:
                if self.upsert_fact(src["source_id"], f):
                    stats["facts"] += 1
                else:
                    stats["skipped"] += 1
            for i in pending_ids:
                eid = self.entity_for(src["source_id"], i.holder_external_id)
                if eid and i.value:
                    self.db.execute_query("""
                        INSERT INTO external_ids (source_id, external_id, entity_id, kind) VALUES (%s, %s, %s, %s)
                        ON CONFLICT (source_id, external_id) DO NOTHING
                    """, (src["source_id"], f"{i.kind}:{i.value}", eid, i.kind))
                    stats["identifiers"] += 1
            self.db.execute_query("UPDATE connector_runs SET finished_at = NOW(), status = 'done', stats = %s::jsonb WHERE run_id = %s", (_json(stats), run))
        except Exception as e:
            self.db.execute_query("UPDATE connector_runs SET finished_at = NOW(), status = 'failed', stats = %s::jsonb, note = %s WHERE run_id = %s", (_json(stats), str(e)[:500], run))
            raise
        logger.success(f"{src['source_id']}: {stats}")
        return stats


def _date(s: Optional[str]) -> Optional[str]:
    """Partial dates from registries ('2017', '2017-05') → a full ISO date; garbage → None."""
    if not s:
        return None
    s = str(s).strip()[:10]
    if len(s) == 4 and s.isdigit():
        return f"{s}-01-01"
    if len(s) == 7 and s[4] == "-":
        return f"{s}-01"
    return s if len(s) == 10 and s[4] == "-" and s[7] == "-" else None


def _json(x) -> str:
    import json
    return json.dumps(x, ensure_ascii=False, default=str)
