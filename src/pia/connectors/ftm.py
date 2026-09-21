"""
FollowTheMoney (FtM) → connector items.

FtM is the open data model OCCRP's Aleph and OpenSanctions use for investigative data: a JSON
line per entity with `id`, `schema` (Person, Company, Sanction, Ownership, …) and multi-valued
`properties`. Speaking FtM means any database exported in that shape plugs into PIA with no new
code — only a source row and a file or URL.
"""
import json
import re
from typing import Dict, Iterable, List, Optional

from pia.connectors.base import Entity, Fact, Identifier, Item, Listing

KIND = {
    "Person": "PERSON", "Organization": "ORG", "Company": "ORG", "LegalEntity": "ORG", "PublicBody": "ORG",
    "Vessel": "VESSEL", "Airplane": "AIRCRAFT",
}
ID_PROPS = {"registrationNumber": "registration", "innCode": "tax", "ogrnCode": "registration", "leiCode": "lei",
            "taxNumber": "tax", "imoNumber": "imo", "mmsi": "mmsi", "idNumber": "id", "passportNumber": "passport",
            "icaoCode": "icao", "registrationNumber_": "registration"}
KEEP_PROPS = ("birthDate", "birthPlace", "gender", "nationality", "citizenship", "position", "incorporationDate",
              "jurisdiction", "legalForm", "sector", "website", "flag", "type", "buildDate", "callSign", "programId",
              "topics", "sourceUrl", "notes", "modifiedAt", "classification")


def _first(props: Dict, key: str) -> Optional[str]:
    v = props.get(key)
    return v[0] if isinstance(v, list) and v else (v if isinstance(v, str) else None)


def ftm_items(lines: Iterable[str], iso2_to_qid: Dict[str, str]) -> Iterable[Item]:
    """Yield connector items from FtM JSON lines. Unknown schemata are ignored.
    Positions and Occupancies (the PEP datasets) are buffered: a post's name may come after the people who hold it,
    so the PEP listings are yielded once the stream ends."""
    positions: Dict[str, Dict] = {}          # position id → {"name", "country"}
    occupancies: List[Dict] = []
    for line in lines:
        try:
            d = json.loads(line)
        except Exception:
            continue
        schema, props, fid = d.get("schema"), d.get("properties") or {}, d.get("id")
        if not fid or not schema:
            continue
        if schema in KIND:
            names = props.get("name") or []
            name = _pick_name(names) or fid
            aliases = [n for n in names if n != name] + list(props.get("alias") or [])
            cc = (_first(props, "country") or _first(props, "jurisdiction") or _first(props, "nationality") or _first(props, "citizenship") or _first(props, "flag") or "").upper()
            country_qid = iso2_to_qid.get(cc)
            desc = _first(props, "position") or (_first(props, "notes") or "")[:300] or None
            other_ids = [(kind, v) for prop, kind in ID_PROPS.items() for v in (props.get(prop) or [])]
            # OpenSanctions keys Wikidata-derived people by the Q-id itself
            qid = _first(props, "wikidataId") or (fid if re.fullmatch(r"Q\d+", fid) else None)
            yield Entity(external_id=fid, kind=KIND[schema], name=name[:200], aliases=aliases[:30], description=desc,
                         country_qid=country_qid, properties={k: props[k] for k in KEEP_PROPS if k in props},
                         wikidata_qid=qid, other_ids=other_ids)
        elif schema == "Position":
            positions[fid] = {"name": _pick_name(props.get("name") or []) or fid, "country": (_first(props, "country") or "").upper()}
        elif schema == "Occupancy":
            holder, post = _first(props, "holder"), _first(props, "post")
            if holder and post:
                occupancies.append({"holder": holder, "post": post, "since": _first(props, "startDate"), "until": _first(props, "endDate"),
                                    "status": _first(props, "status"), "url": _first(props, "sourceUrl")})
        elif schema == "Family":
            person, relative = _first(props, "person"), _first(props, "relative")
            if person and relative:
                yield Fact(subject_external_id=person, predicate=_kinship(_first(props, "relationship")),
                           object_external_id=relative, family="NEUTRAL·statement", record_ref=_first(props, "sourceUrl") or fid)
        elif schema == "Sanction":
            subject = _first(props, "entity")
            if not subject:
                continue
            authority = _first(props, "authority") or _first(props, "programId") or "unknown authority"
            listing = {"list": authority, "program": _first(props, "program") or _first(props, "programId"),
                       "since": _first(props, "startDate") or _first(props, "listingDate"), "until": _first(props, "endDate"),
                       "url": _first(props, "sourceUrl")}
            yield Fact(subject_external_id=subject, predicate="sanctioned by", object_name=authority,
                       family="NEUTRAL·statement", valid_from=listing["since"], valid_to=listing["until"],
                       record_ref=_first(props, "sourceUrl") or fid,
                       properties={"listing": listing, "reason": (_first(props, "reason") or "")[:500], "programId": _first(props, "programId")})
        elif schema == "Ownership":
            owner, asset = _first(props, "owner"), _first(props, "asset")
            if owner and asset:
                # the subject is the owner, so the predicate must read from the owner's side: lists write the role from
                # the asset's side ("Owned or Controlled By"), which would come out backwards as "Rosneft — owned by — RN Holding"
                yield Fact(subject_external_id=owner, predicate="owns", object_external_id=asset,
                           family="NEUTRAL·ownership", valid_from=_first(props, "startDate"), valid_to=_first(props, "endDate"),
                           record_ref=_first(props, "sourceUrl") or fid,
                           properties={"share": _first(props, "percentage"), "role": _first(props, "role")})
        elif schema == "Directorship":
            director, org = _first(props, "director"), _first(props, "organization")
            if director and org:
                yield Fact(subject_external_id=director, predicate=(_first(props, "role") or "director of").lower()[:60], object_external_id=org,
                           family="NEUTRAL·role", valid_from=_first(props, "startDate"), valid_to=_first(props, "endDate"), record_ref=fid)
        elif schema == "Membership":
            member, org = _first(props, "member"), _first(props, "organization")
            if member and org:
                yield Fact(subject_external_id=member, predicate=(_first(props, "role") or "member of").lower()[:60], object_external_id=org,
                           family="NEUTRAL·statement", valid_from=_first(props, "startDate"), valid_to=_first(props, "endDate"), record_ref=fid)
        elif schema == "Employment":
            emp, org = _first(props, "employee"), _first(props, "employer")
            if emp and org:
                yield Fact(subject_external_id=emp, predicate=(_first(props, "role") or "employed by").lower()[:60], object_external_id=org,
                           family="NEUTRAL·role", record_ref=fid)
        elif schema in ("Passport", "Identification"):
            holder = _first(props, "holder")
            number = _first(props, "number") or _first(props, "passportNumber")
            if holder and number:
                yield Identifier(holder_external_id=holder, kind="passport" if schema == "Passport" else "id", value=number,
                                 properties={"country": _first(props, "country"), "type": _first(props, "type")})
        # Address, CryptoWallet, Security, Representation, UnknownLink, Asset: not mapped yet
    for o in occupancies:
        post = positions.get(o["post"])
        program = f"{post['name']} ({post['country']})" if post and post["country"] else (post["name"] if post else o["post"])
        yield Listing(holder_external_id=o["holder"], listing={"list": "PEP", "program": program[:200], "since": o["since"],
                                                              "until": o["until"], "status": o["status"], "url": o["url"]})


def _kinship(rel: Optional[str]) -> str:
    """'son of Yury Chaika' → 'son of'; 'Spouse' → 'spouse of'; free text → 'relative of' (the catalogue must not fill with names)."""
    r = (rel or "").strip().lower()
    if not r:
        return "relative of"
    if " of " in r:
        r = r.split(" of ", 1)[0].strip() + " of"
    elif not r.endswith(" of"):
        r = r + " of"
    return r[:40] if len(r.split()) <= 3 and r.replace(" of", "").replace("-", "").replace(" ", "").isalpha() else "relative of"


def _pick_name(names) -> Optional[str]:
    """Prefer a Latin-script name; else the first."""
    for n in names or []:
        if isinstance(n, str) and all(ord(ch) < 0x250 for ch in n):
            return n
    return names[0] if names else None
