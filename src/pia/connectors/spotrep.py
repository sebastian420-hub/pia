"""
SPOTREP: a human report in a fixed format, read deterministically.

    reporter: crow                      # a pseudonym; becomes a source with its own trust
    observed: 2026-09-20T08:15Z         # when it happened (reported: defaults to now)
    location: 33.51, 36.29              # lat, lon — or a place name the resolver knows
    basis: direct | indirect | hearsay  # how the reporter knows
    confidence: 0.7
    mission: Gulf                       # optional, name or id

    ENTITIES:
    - Abu Khalid | person | passport: X123; phone: +963… | drives a white Hilux
    - 4th Division | org

    EVENTS:
    - 4th Division | moved artillery to | Qatana | 2026-09-20T07:00Z | 33.43, 36.08 | -2
    - Abu Khalid | met | 4th Division | | | 0

    NOTES:
    Free text: read by the analyst like an article (quotes, verified, lines).

ENTITIES and EVENTS are structured — nothing is guessed. A JSON form with the same keys
({"reporter": …, "entities": [{"name","kind","ids","notes"}], "events": [{"actor","predicate",
"target","time","place","stance"}], "notes": "…"}) is accepted too, for phones and forms.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from pia.connectors.base import Connector, Document, Entity, Event, Identifier, Item
from pia.kg.normalize import normalize

KINDS = {"person": "PERSON", "org": "ORG", "organisation": "ORG", "organization": "ORG", "group": "ORG", "company": "ORG",
         "unit": "ORG", "country": "COUNTRY", "place": "PLACE", "location": "PLACE", "vessel": "VESSEL", "ship": "VESSEL",
         "aircraft": "AIRCRAFT", "plane": "AIRCRAFT", "event": "EVENT"}
BASIS_TRUST = {"direct": 0.7, "indirect": 0.5, "hearsay": 0.3}
HEADER_KEYS = ("reporter", "observed", "reported", "location", "basis", "confidence", "mission")


class SpotrepError(ValueError):
    pass


@dataclass
class Spotrep:
    reporter: str
    observed: datetime
    reported: datetime
    basis: str = "direct"
    confidence: float = 0.6
    mission: Optional[str] = None
    location: Optional[Tuple[float, float]] = None
    place_name: Optional[str] = None
    entities: List[Dict] = field(default_factory=list)   # {name, kind, ids: [(kind, value)], notes}
    events: List[Dict] = field(default_factory=list)     # {actor, predicate, target, time, place, stance, line}
    notes: str = ""


def _time(s: Optional[str], default: Optional[datetime] = None) -> Optional[datetime]:
    if not s or not s.strip():
        return default
    s = s.strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z", "%Y-%m-%d %H:%M%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise SpotrepError(f"cannot read time {s!r} (use 2026-09-20T08:15Z)")


def _latlon(s: Optional[str]) -> Tuple[Optional[Tuple[float, float]], Optional[str]]:
    """'33.51, 36.29' → point; anything else → a place name."""
    if not s or not s.strip():
        return None, None
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*", s)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise SpotrepError(f"location out of range: {s!r}")
        return (lat, lon), None
    return None, s.strip()


def _ids(s: Optional[str]) -> List[Tuple[str, str]]:
    """'passport: X123; plate: ABC-1' → [("passport", "X123"), ("plate", "ABC-1")]."""
    out = []
    for part in re.split(r"[;,]", s or ""):
        if ":" in part:
            k, v = part.split(":", 1)
            if k.strip() and v.strip():
                out.append((k.strip().lower(), v.strip()))
    return out


def parse(text: str) -> Spotrep:
    text = text.strip()
    if text.startswith("{"):
        return _from_json(json.loads(text))
    header: Dict[str, str] = {}
    section = None
    ents, evs, notes = [], [], []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        up = line.strip().upper().rstrip(":")
        if up in ("ENTITIES", "EVENTS", "NOTES") and line.strip().endswith(":"):
            section = up
            continue
        if section is None:
            if not line.strip():
                continue
            if ":" not in line:
                raise SpotrepError(f"line {n}: expected 'key: value' in the header, got {line!r}")
            k, v = line.split(":", 1)
            k = k.strip().lower()
            if k not in HEADER_KEYS:
                raise SpotrepError(f"line {n}: unknown header {k!r} (allowed: {', '.join(HEADER_KEYS)})")
            header[k] = v.strip()
        elif section == "NOTES":
            notes.append(line)
        elif line.strip().startswith("-"):
            cols = [c.strip() for c in line.strip()[1:].split("|")]
            if section == "ENTITIES":
                if not cols[0]:
                    raise SpotrepError(f"line {n}: an entity needs a name")
                ents.append({"name": cols[0], "kind": (cols[1] if len(cols) > 1 else ""), "ids": (cols[2] if len(cols) > 2 else ""),
                             "notes": (cols[3] if len(cols) > 3 else ""), "line": n})
            else:
                if len(cols) < 2 or not cols[0] or not cols[1]:
                    raise SpotrepError(f"line {n}: an event needs at least 'actor | predicate'")
                evs.append({"actor": cols[0], "predicate": cols[1], "target": (cols[2] if len(cols) > 2 else ""),
                            "time": (cols[3] if len(cols) > 3 else ""), "place": (cols[4] if len(cols) > 4 else ""),
                            "stance": (cols[5] if len(cols) > 5 else ""), "line": n})
        elif line.strip():
            raise SpotrepError(f"line {n}: rows in {section} start with '- '")
    return _build(header, ents, evs, "\n".join(notes).strip())


def _from_json(d: Dict) -> Spotrep:
    header = {k: str(d[k]) for k in HEADER_KEYS if d.get(k) is not None}
    ents = [{"name": e.get("name", ""), "kind": e.get("kind", ""), "notes": e.get("notes", ""), "line": i + 1,
             "ids": "; ".join(f"{k}: {v}" for k, v in (e.get("ids") or {}).items()) if isinstance(e.get("ids"), dict) else str(e.get("ids") or "")}
            for i, e in enumerate(d.get("entities") or [])]
    evs = [{"actor": e.get("actor", ""), "predicate": e.get("predicate", ""), "target": e.get("target", ""), "time": str(e.get("time") or ""),
            "place": str(e.get("place") or ""), "stance": str(e.get("stance") if e.get("stance") is not None else ""), "line": i + 1}
           for i, e in enumerate(d.get("events") or [])]
    return _build(header, ents, evs, str(d.get("notes") or "").strip())


def _build(header: Dict[str, str], ents: List[Dict], evs: List[Dict], notes: str) -> Spotrep:
    if not header.get("reporter"):
        raise SpotrepError("a report needs 'reporter: <pseudonym>'")
    if not header.get("observed"):
        raise SpotrepError("a report needs 'observed: <time>'")
    basis = (header.get("basis") or "direct").lower()
    if basis not in BASIS_TRUST:
        raise SpotrepError("basis must be direct, indirect or hearsay")
    try:
        conf = max(0.0, min(1.0, float(header.get("confidence") or 0.6)))
    except ValueError:
        raise SpotrepError("confidence must be a number 0–1")
    loc, place = _latlon(header.get("location"))
    rep = Spotrep(reporter=re.sub(r"[^A-Za-z0-9_.-]", "_", header["reporter"])[:40], observed=_time(header["observed"]),
                  reported=_time(header.get("reported"), datetime.now(timezone.utc)), basis=basis, confidence=conf,
                  mission=header.get("mission") or None, location=loc, place_name=place, notes=notes)
    for e in ents:
        kind = KINDS.get((e["kind"] or "").lower())
        if e["kind"] and not kind:
            raise SpotrepError(f"line {e['line']}: unknown kind {e['kind']!r} (person, org, country, place, vessel, aircraft, event)")
        rep.entities.append({"name": e["name"], "kind": kind or "UNKNOWN", "ids": _ids(e["ids"]), "notes": e["notes"]})
    for ev in evs:
        try:
            stance = int(ev["stance"]) if ev["stance"] else 0
        except ValueError:
            stance = 99
        if not -3 <= stance <= 3:
            raise SpotrepError(f"line {ev['line']}: stance must be -3…3")
        p, pname = _latlon(ev["place"])
        rep.events.append({"actor": ev["actor"], "predicate": ev["predicate"], "target": ev["target"] or None,
                           "time": _time(ev["time"], rep.observed), "place": p or rep.location, "place_name": pname,
                           "stance": stance, "line": ev["line"]})
    if not rep.entities and not rep.events and not rep.notes:
        raise SpotrepError("an empty report: add ENTITIES, EVENTS or NOTES")
    return rep


class SpotrepConnector(Connector):
    """One report → Entities (+ Identifiers), Events, and the NOTES as a Document."""

    def __init__(self, rep: Spotrep, ref: str, mission_id: Optional[str] = None):
        self.rep, self.ref, self.mission_id = rep, ref, mission_id
        self.source = {"source_id": f"reporter:{rep.reporter}", "label": f"Reporter {rep.reporter}", "kind": "HUMAN",
                       "trust": round(BASIS_TRUST[rep.basis] * (0.5 + rep.confidence / 2), 2), "homepage": None,
                       "visibility": "restricted"}      # a human report is private until an admin says otherwise

    @staticmethod
    def key(name: str) -> str:
        return "name:" + normalize(name)

    def pull(self, since=None) -> Iterable[Item]:
        rep = self.rep
        named = {self.key(e["name"]) for e in rep.entities}
        for e in rep.entities:
            yield Entity(external_id=self.key(e["name"]), kind=e["kind"], name=e["name"], description=e["notes"] or None,
                         properties={"reported_by": rep.reporter}, other_ids=[(k, f"{k}:{v}") for k, v in e["ids"]])
            for k, v in e["ids"]:
                yield Identifier(holder_external_id=self.key(e["name"]), kind=k, value=v)
        # actors / targets not listed under ENTITIES still get a row (kind unknown) so the event can stand
        for ev in rep.events:
            for name in (ev["actor"], ev["target"]):
                if name and self.key(name) not in named:
                    named.add(self.key(name))
                    yield Entity(external_id=self.key(name), kind="UNKNOWN", name=name, properties={"reported_by": rep.reporter})
        for ev in rep.events:
            family = "HOSTILE·force" if ev["stance"] <= -2 else "HOSTILE·accusation" if ev["stance"] == -1 \
                else "COOPERATIVE·agreement" if ev["stance"] >= 2 else "COOPERATIVE·alliance/support" if ev["stance"] == 1 else "NEUTRAL·statement"
            quote = f"{ev['actor']} {ev['predicate']} {ev['target'] or ''}".strip() + f" — reported by {rep.reporter} ({rep.basis})"
            yield Event(actor_external_id=self.key(ev["actor"]), predicate=ev["predicate"],
                        target_external_id=self.key(ev["target"]) if ev["target"] else None, time=ev["time"], family=family,
                        stance=ev["stance"], place=ev["place"], quote=quote, record_ref=f"{self.ref}#L{ev['line']}",
                        confidence=rep.confidence)
        if rep.notes:
            head = rep.notes.splitlines()[0][:120]
            yield Document(external_id=self.ref, title=f"SPOTREP {rep.reporter} · {head}", text=rep.notes, published=rep.observed,
                           domain="MILITARY" if any(ev["stance"] <= -2 for ev in rep.events) else "POLITICAL",
                           source_type="HUMINT", mission_id=self.mission_id,
                           geo=rep.location, extra={"spotrep": True, "basis": rep.basis, "confidence": rep.confidence})
