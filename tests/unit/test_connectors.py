"""Connectors: FtM → items; the ingestor's identity order (external id → Q-id → name → new)."""
import json

from pia.connectors.base import Entity, Fact, Identifier
from pia.connectors.ftm import ftm_items


def test_ftm_maps_entities_sanctions_ownership_and_ids():
    lines = [
        json.dumps({"id": "P1", "schema": "Person", "properties": {"name": ["KUAJIEN, Michael", "Michael Kuajien"], "alias": ["M. Kuajian"],
                                                                     "country": ["ke"], "birthDate": ["1979-01-01"], "idNumber": ["A1"], "wikidataId": ["Q1"]}}),
        json.dumps({"id": "S1", "schema": "Sanction", "properties": {"entity": ["P1"], "authority": ["OFAC"], "programId": ["US-GLOMAG"],
                                                                       "startDate": ["2019-04-08"], "sourceUrl": ["https://x"]}}),
        json.dumps({"id": "O1", "schema": "Ownership", "properties": {"owner": ["P1"], "asset": ["C1"], "role": ["Owned or Controlled By"]}}),
        json.dumps({"id": "C1", "schema": "Company", "properties": {"name": ["ОАО Завод", "Zavod OJSC"], "registrationNumber": ["123"], "jurisdiction": ["ru"]}}),
        json.dumps({"id": "X1", "schema": "Passport", "properties": {"holder": ["P1"], "number": ["PP9"]}}),
        json.dumps({"id": "A1", "schema": "Address", "properties": {"full": ["Nairobi"]}}),
    ]
    items = list(ftm_items(lines, {"KE": "Q114", "RU": "Q159"}))
    ents = [i for i in items if isinstance(i, Entity)]
    facts = [i for i in items if isinstance(i, Fact)]
    ids = [i for i in items if isinstance(i, Identifier)]
    assert [e.external_id for e in ents] == ["P1", "C1"]
    p = ents[0]
    assert p.kind == "PERSON" and p.name == "KUAJIEN, Michael" and "Michael Kuajien" in p.aliases and p.country_qid == "Q114"
    assert p.wikidata_qid == "Q1" and ("id", "A1") in p.other_ids and p.properties["birthDate"] == ["1979-01-01"]
    c = ents[1]
    assert c.name == "Zavod OJSC" and c.country_qid == "Q159" and ("registration", "123") in c.other_ids   # Latin name preferred
    s = [f for f in facts if f.predicate == "sanctioned by"][0]
    assert s.subject_external_id == "P1" and s.object_name == "OFAC" and s.valid_from == "2019-04-08"
    assert s.properties["listing"]["list"] == "OFAC" and s.properties["listing"]["since"] == "2019-04-08"
    o = [f for f in facts if f.family == "NEUTRAL·ownership"][0]
    assert (o.subject_external_id, o.object_external_id) == ("P1", "C1")
    assert ids[0].kind == "passport" and ids[0].value == "PP9"
    assert len(items) == 5      # the Address row is ignored
