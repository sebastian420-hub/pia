"""
Identity resolution: a surface string from an article → one entity row, anchored to a
Wikidata Q-id whenever possible. Strict by design: unsure names go to NEEDS_REVIEW and
never enter the web.

Order: generic-noun filter → government seats → local alias table → resolution cache /
Wikidata search → context scoring → (optional) LLM tie-break among candidates → review.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from loguru import logger

from pia.kg import wikidata
from pia.kg.normalize import looks_generic, normalize
from pia.kg.ontology import CONTINENT_QIDS, GOVERNMENT_BODY_CLASSES, GOVERNMENT_SEATS, KINDS

KIND_COMPAT = {  # a hint from the extractor vs the kind Wikidata gives
    "PERSON": {"PERSON"}, "ORG": {"ORG", "COUNTRY"}, "COUNTRY": {"COUNTRY", "PLACE"},
    "PLACE": {"PLACE", "COUNTRY"}, "VESSEL": {"VESSEL"}, "AIRCRAFT": {"AIRCRAFT"}, "EVENT": {"EVENT"},
    "UNKNOWN": set(KINDS), None: set(KINDS),
}
CACHE_TTL = timedelta(days=7)
# "US Environmental Protection Agency" is filed under "United States …" on Wikidata
ABBREVIATIONS = {"us": "United States", "u s": "United States", "uk": "United Kingdom", "un": "United Nations",
                 "eu": "European Union", "nyc": "New York City", "la": "Los Angeles", "dc": "Washington, D.C."}
AUTO_MARGIN = 1.5
AUTO_MIN = 3.0


class Resolver:
    def __init__(self, db, llm_choose=None):
        """llm_choose(surface, context, candidates) -> index | None ; optional tie-breaker."""
        self.db = db
        self.llm_choose = llm_choose
        self._class_cache: Dict[str, str] = {}
        wikidata.set_db(db)

    # ── public ────────────────────────────────────────────────────────────────

    def resolve(self, surface: str, kind_hint: Optional[str] = None, role: str = "MENTIONED",
                context: Optional[dict] = None, local_only: bool = False) -> Optional[dict]:
        """
        Returns an entity dict (entity_id, qid, kind, name, resolution) or None (rejected).
        local_only: never call Wikidata (high-volume sources such as GDELT); unknown names return None.
        """
        context = context or {}
        surface = (surface or "").strip()
        if not surface or looks_generic(surface):
            return None
        norm = normalize(surface)

        # "Washington said" / "Beijing warned" → the country's government
        if role in ("ACTOR", "TARGET") and norm in GOVERNMENT_SEATS:
            ent = self.ensure_qid(GOVERNMENT_SEATS[norm])
            if ent:
                ent = dict(ent, role="GOVERNMENT")
                return ent

        local = self._lookup_local(norm, kind_hint, context, strict_country=local_only, role=role)
        # a small place that merely shares the name ("Scotland", a US town) must not stop the lookup that
        # would find the obvious item: weak place-only hits are re-checked against Wikidata when allowed
        weak_place = bool(local) and local.get("kind") == "PLACE" and (local.get("sitelinks") or 0) < 20 \
            and (local.get("population") or 0) < 100_000 and not local_only
        if local and not weak_place:
            return self._as_actor(local, role)
        if local_only:
            return None

        candidates = self._candidates(surface, norm)
        if weak_place and candidates:
            best = max(candidates, key=lambda c: c["parsed"].get("sitelinks") or 0)
            if (best["parsed"].get("sitelinks") or 0) > 3 * max(1, local.get("sitelinks") or 0):
                return self._as_actor(self.upsert_wikidata(best["parsed"]), role)
            return self._as_actor(local, role)
        if weak_place:
            return self._as_actor(local, role)
        if candidates is None:   # Wikidata unreachable / rate-limited: park it, retried soon by the maintenance agent
            return self._local_entity(surface, kind_hint, review=True, note="lookup failed")
        if not candidates:
            return self._local_entity(surface, kind_hint, review=True, note="no wikidata candidate")

        scored = self._score(candidates, surface, norm, kind_hint, context)
        scored.sort(key=lambda c: c["score"], reverse=True)
        best = scored[0]
        second = scored[1]["score"] if len(scored) > 1 else -99
        if best["kind"] == "UNKNOWN":
            return self._local_entity(surface, kind_hint, review=True, note="best candidate is not a person/org/place",
                                      candidates=[c["parsed"]["qid"] for c in scored[:5]])
        if best["score"] >= AUTO_MIN and best["score"] - second >= AUTO_MARGIN:
            return self._as_actor(self.upsert_wikidata(best["parsed"]), role)

        if self.llm_choose and best["score"] >= 1.0:
            idx = self.llm_choose(surface, context, [c["parsed"] for c in scored[:5]])
            if idx is not None and 0 <= idx < len(scored):
                return self.upsert_wikidata(scored[idx]["parsed"])
            if idx is None:
                return self._local_entity(surface, kind_hint, review=True, note="llm: none of the candidates",
                                          candidates=[c["parsed"]["qid"] for c in scored[:5]])

        return self._local_entity(surface, kind_hint, review=True, note="ambiguous",
                                  candidates=[c["parsed"]["qid"] for c in scored[:5]])

    def _as_actor(self, ent: Optional[dict], role: str) -> Optional[dict]:
        """
        Actor/target hygiene: a continent is never an actor; a government body (ministry, armed
        force, agency) acts as its country — the mention keeps the body, the event uses the
        country (returned under `event_entity`).
        """
        if not ent or role not in ("ACTOR", "TARGET"):
            return ent
        if ent.get("qid") in CONTINENT_QIDS:
            return None
        # a place does not act or get acted upon — its country does ("strikes on Kyiv" → Ukraine);
        # a region with no country ("West Asia") is no party at all. The mention keeps the place.
        if ent.get("kind") == "PLACE":
            if ent.get("country_qid"):
                country = self.ensure_qid(ent["country_qid"])
                if country and country.get("kind") == "COUNTRY":
                    return dict(ent, event_entity=country)
            return dict(ent, event_entity=None)
        if ent.get("kind") == "ORG" and ent.get("country_qid"):
            p31 = set((ent.get("p31") or []))
            if not p31 and ent.get("entity_id"):
                row = self.db.execute_query("SELECT metadata->'p31' AS p31 FROM entities WHERE entity_id = %s",
                                            (ent["entity_id"],), fetch=True)
                raw = row[0]["p31"] if row else None
                p31 = set(json.loads(raw) if isinstance(raw, str) else (raw or []))
            if p31 & GOVERNMENT_BODY_CLASSES:
                country = self.ensure_qid(ent["country_qid"])
                if country and country.get("kind") == "COUNTRY":
                    return dict(ent, event_entity=country)
        return ent

    def ensure_qid(self, qid: str) -> Optional[dict]:
        """Loads a Wikidata item into the store if missing; returns the entity dict."""
        rows = self.db.execute_query(
            "SELECT entity_id, qid, kind, name, resolution FROM entities WHERE qid = %s", (qid,), fetch=True)
        if rows:
            return dict(rows[0])
        fetched = wikidata.get_entities([qid])
        if qid not in fetched:
            return None
        return self.upsert_wikidata(fetched[qid])

    def upsert_wikidata(self, parsed: dict) -> dict:
        """entities + aliases + static relations (to targets already in the store)."""
        kind = self._kind_from_p31(parsed["p31"])
        geo = None
        if parsed.get("coords"):
            lat, lon = parsed["coords"]
            geo = f"SRID=4326;POINT({lon} {lat})"
        rows = self.db.execute_query("""
            INSERT INTO entities (qid, kind, name, description, resolution, origin, country_qid, primary_geo,
                                  sitelinks, wikidata_synced_at, metadata)
            VALUES (%s, %s, %s, %s, 'RESOLVED', 'wikidata', %s, %s::geometry, %s, NOW(), %s::jsonb)
            ON CONFLICT (qid) WHERE qid IS NOT NULL DO UPDATE SET
                kind = EXCLUDED.kind,
                -- never replace a real name with a bare Q-id (Wikidata labels can be empty for a moment)
                name = CASE WHEN EXCLUDED.name = EXCLUDED.qid AND entities.name <> entities.qid THEN entities.name ELSE EXCLUDED.name END,
                description = EXCLUDED.description,
                country_qid = EXCLUDED.country_qid, primary_geo = COALESCE(EXCLUDED.primary_geo, entities.primary_geo),
                sitelinks = EXCLUDED.sitelinks, wikidata_synced_at = NOW(), resolution = 'RESOLVED',
                metadata = COALESCE(entities.metadata, '{}'::jsonb) || EXCLUDED.metadata, updated_at = NOW()
            RETURNING entity_id, qid, kind, name, resolution
        """, (parsed["qid"], kind, parsed["label"], parsed.get("description"), parsed.get("country_qid"), geo,
              parsed.get("sitelinks", 0), json.dumps({k: v for k, v in {"p31": parsed["p31"][:5], "iso3": parsed.get("iso3"), "iso2": parsed.get("iso2")}.items() if v})), fetch=True)
        ent = dict(rows[0])
        eid = ent["entity_id"]

        aliases = {parsed["label"], *parsed.get("aliases", [])}
        alias_rows = [(eid, a, normalize(a)) for a in aliases if a and normalize(a)]
        self.db.execute_values(
            "INSERT INTO entity_aliases (entity_id, alias, alias_norm, source) VALUES %s ON CONFLICT (entity_id, alias_norm) DO NOTHING",
            alias_rows, template="(%s, %s, %s, 'wikidata')")

        self._store_static_relations(eid, parsed.get("relations", []))
        return ent

    # ── internals ─────────────────────────────────────────────────────────────

    def _lookup_local(self, norm: str, kind_hint, context, strict_country: bool = False, role: str = "MENTIONED") -> Optional[dict]:
        rows = self.db.execute_query("""
            SELECT e.entity_id, e.qid, e.kind, e.name, e.resolution, e.sitelinks, e.country_qid,
                   COALESCE((e.metadata->>'population')::bigint, 0) AS population,
                   COALESCE(e.metadata->'p31', '[]'::jsonb) AS p31
            FROM entity_aliases a JOIN entities e ON e.entity_id = a.entity_id
            WHERE a.alias_norm = %s AND e.resolution IN ('RESOLVED','LOCAL')
        """, (norm,), fetch=True) or []
        rows = [r for r in rows if r["kind"] in KIND_COMPAT.get(kind_hint, set(KINDS))]
        ctx_country = context.get("country_qid")
        if strict_country and ctx_country:
            # "Supreme Court" from a Pakistani story must not become the US Supreme Court
            rows = [r for r in rows if r["kind"] == "COUNTRY" or not r["country_qid"] or r["country_qid"] == ctx_country]
        if not rows:
            return None
        if len(rows) == 1:
            return dict(rows[0])
        if strict_country and not ctx_country and len({r["country_qid"] for r in rows if r["country_qid"]}) > 1 \
                and not any(r["kind"] == "COUNTRY" for r in rows):
            return None   # "House of Representatives" of eight countries, no country context: not guessable

        actor_role = role in ("ACTOR", "TARGET")

        def rank(r):
            # "China" said/did something → the country, not the region or a town of the same name.
            # GeoNames cities carry no sitelinks: a big city must still outrank a small ship or
            # company that happens to share its name ("Copenhagen").
            prominence = (r["sitelinks"] or 0) + (200 if (r["population"] or 0) >= 100_000 else 0)
            # A candidate whose known country contradicts the story loses; an unknown country is no
            # evidence either way ("Donald Trump" with no P27 yet must not lose to "Donald Trump III").
            country_fit = -1 if (ctx_country and r["country_qid"] and r["country_qid"] != ctx_country) else 0
            return (1 if (actor_role and r["kind"] == "COUNTRY") else 0, country_fit, prominence, r["population"] or 0)
        rows.sort(key=rank, reverse=True)
        return dict(rows[0])

    def _candidates(self, surface: str, norm: str) -> Optional[List[dict]]:
        cached = self.db.execute_query(
            "SELECT candidates, fetched_at FROM resolution_cache WHERE query_norm = %s", (norm,), fetch=True)
        if cached and cached[0]["fetched_at"] > datetime.now(timezone.utc) - CACHE_TTL:
            return cached[0]["candidates"]
        try:
            hits = wikidata.search(surface, limit=5)
            first = normalize(surface).split(" ", 1)[0] if " " in normalize(surface) else None
            if first in ABBREVIATIONS:
                expanded = ABBREVIATIONS[first] + " " + surface.split(" ", 1)[1]
                seen = {h["qid"] for h in hits}
                hits += [h for h in wikidata.search(expanded, limit=5) if h["qid"] not in seen]
            parsed = wikidata.get_entities([h["qid"] for h in hits]) if hits else {}
            cands = [dict(h, parsed=parsed[h["qid"]]) for h in hits if h["qid"] in parsed]
        except Exception as e:
            logger.warning(f"wikidata lookup failed for {surface!r}: {e}")
            return None
        self.db.execute_query("""
            INSERT INTO resolution_cache (query_norm, candidates, fetched_at) VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (query_norm) DO UPDATE SET candidates = EXCLUDED.candidates, fetched_at = NOW()
        """, (norm, json.dumps(cands)))
        return cands

    def _score(self, cands, surface, norm, kind_hint, context):
        out = []
        ctx_country = context.get("country_qid")
        allowed = KIND_COMPAT.get(kind_hint, set(KINDS))
        for c in cands:
            p = c["parsed"]
            kind = self._kind_from_p31(p.get("p31", []))
            s = 0.0
            names = {normalize(p["label"])} | {normalize(a) for a in p.get("aliases", [])}
            if norm in names:
                s += 3.0
            elif c.get("match") and normalize(c["match"]) == norm:
                s += 2.0
            s += min(2.0, math.log10(1 + (p.get("sitelinks") or 0)))
            if kind == kind_hint:
                s += 2.5          # exact kind match beats "compatible"
            elif kind in allowed:
                s += 1.0
            else:
                s -= 3.0
            if kind == "COUNTRY":
                s += 0.5          # a state outranks its region/civilisation for the same name
            if kind == "UNKNOWN":
                s -= 4.0          # concepts/topics ('artificial intelligence') are not entities
            if ctx_country and p.get("country_qid") == ctx_country:
                s += 1.0
            desc = (p.get("description") or "").lower()
            if any(w in desc for w in ("wikimedia", "disambiguation", "article", "category", "list of")):
                s -= 5.0
            out.append({"parsed": p, "kind": kind, "score": round(s, 2)})
        return out

    # when an item is several things at once, the most specific identity wins:
    # Canada is a "dominion" (a place) and a "country" — it is a country
    KIND_PRIORITY = ("COUNTRY", "PERSON", "ORG", "VESSEL", "AIRCRAFT", "PLACE", "EVENT")

    def _kind_from_p31(self, p31: List[str]) -> str:
        kinds = []
        for cls in p31:
            if cls in self._class_cache:
                k = self._class_cache[cls]
            else:
                row = self.db.execute_query("SELECT kind FROM wikidata_classes WHERE class_qid = %s", (cls,), fetch=True)
                if row:
                    k = row[0]["kind"]
                else:
                    k = wikidata.classify_class(cls) or "UNKNOWN"
                    self.db.execute_query(
                        "INSERT INTO wikidata_classes (class_qid, kind) VALUES (%s, %s) ON CONFLICT (class_qid) DO NOTHING", (cls, k))
                self._class_cache[cls] = k
            if k != "UNKNOWN":
                kinds.append(k)
        for k in self.KIND_PRIORITY:
            if k in kinds:
                return k
        return "UNKNOWN"

    def _store_static_relations(self, eid, relations: List[dict]):
        if not relations:
            return
        targets = {r["target_qid"] for r in relations}
        rows = self.db.execute_query("SELECT entity_id, qid FROM entities WHERE qid = ANY(%s)", (list(targets),), fetch=True) or []
        by_qid = {r["qid"]: r["entity_id"] for r in rows}
        pending = []
        for r in relations:
            tid = by_qid.get(r["target_qid"])
            if tid is None:
                pending.append(r["target_qid"])
                continue
            if tid == eid:
                continue
            self.db.execute_query("""
                INSERT INTO relations (a_id, b_id, kind, source, property, label, directed, weight, event_count, first_seen, last_seen)
                VALUES (%s, %s, %s, 'wikidata', %s, %s, TRUE, %s, 0, NOW(), NOW())
                ON CONFLICT (a_id, b_id, kind, source) DO UPDATE SET label = EXCLUDED.label, weight = EXCLUDED.weight, updated_at = NOW()
            """, (eid, tid, r["kind"], r["property"], r["label"], 0.5 if r.get("ended") else 1.0))
        if pending:
            self.db.execute_query("""
                UPDATE entities SET metadata = COALESCE(metadata,'{}'::jsonb) || jsonb_build_object('pending_relations', %s::jsonb)
                WHERE entity_id = %s
            """, (json.dumps(sorted(set(pending))[:200]), eid))

    def _local_entity(self, surface, kind_hint, review: bool, note: str = "", candidates=None) -> dict:
        norm = normalize(surface)
        existing = self.db.execute_query("""
            SELECT entity_id, qid, kind, name, resolution FROM entities
            WHERE qid IS NULL AND resolution IN ('LOCAL','NEEDS_REVIEW') AND lower(name) = lower(%s) LIMIT 1
        """, (surface,), fetch=True)
        if existing:
            return dict(existing[0])
        kind = kind_hint if kind_hint in KINDS else "UNKNOWN"
        rows = self.db.execute_query("""
            INSERT INTO entities (kind, name, resolution, origin, metadata)
            VALUES (%s, %s, %s, 'llm', %s::jsonb) RETURNING entity_id, qid, kind, name, resolution
        """, (kind, surface, "NEEDS_REVIEW" if review else "LOCAL",
              json.dumps({"note": note, "candidates": candidates or []})), fetch=True)
        ent = dict(rows[0])
        self.db.execute_query(
            "INSERT INTO entity_aliases (entity_id, alias, alias_norm, source) VALUES (%s, %s, %s, 'llm') ON CONFLICT DO NOTHING",
            (ent["entity_id"], surface, norm))
        return ent
