"""GLEIF connector: the walk and the mapping, without network."""
from pia.connectors.gleif import GleifConnector


def _row(child, parent, typ, status="ACTIVE", start="2015-01-01T00:00:00.000Z", ref="https://sec.gov/x"):
    return {"Relationship.StartNode.NodeID": child, "Relationship.EndNode.NodeID": parent, "Relationship.RelationshipType": typ,
            "Relationship.RelationshipStatus": status, "Relationship.Period.1.startDate": start, "Relationship.Period.1.endDate": "",
            "Registration.ValidationReference": ref, "Registration.ValidationSources": "FULLY_CORROBORATED"}


A, B, C, D, F = "A" * 20, "B" * 20, "C" * 20, "D" * 20, "F" * 20


def test_grow_walks_hops_and_skips_funds_by_default():
    rows = [_row(A, B, "IS_DIRECTLY_CONSOLIDATED_BY"), _row(B, C, "IS_ULTIMATELY_CONSOLIDATED_BY"),
            _row(C, D, "IS_DIRECTLY_CONSOLIDATED_BY"), _row(F, A, "IS_FUND-MANAGED_BY"), _row("short", A, "IS_DIRECTLY_CONSOLIDATED_BY")]
    g = GleifConnector(db=None, hops=1, seed={A}, iso2_to_qid={})
    grown, edges = g.grow({A}, rows)
    assert grown == {A, B} and len(edges) == 1                      # one hop: A's parent only; fund edge and bad id ignored
    g2 = GleifConnector(db=None, hops=2, seed={A}, iso2_to_qid={})
    grown, edges = g2.grow({A}, rows)
    assert grown == {A, B, C} and len(edges) == 2                   # two hops: A→B→C; C→D would be hop 3
    g3 = GleifConnector(db=None, hops=1, funds=True, seed={A}, iso2_to_qid={})
    grown, _ = g3.grow({A}, rows)
    assert F in grown


def test_entity_prefers_latin_name_and_keeps_legal_name_as_alias():
    g = GleifConnector(db=None, seed=set(), iso2_to_qid={"RU": "Q159"})
    rec = {"id": "253400JT3MQWNDKMJE44", "attributes": {"bic": ["ROSNRUMM"], "registration": {"status": "ISSUED"}, "entity": {
        "legalName": {"name": "публичное акционерное общество \"Нефтяная компания \"Роснефть\"", "language": "ru"},
        "otherNames": [{"name": "Rosneft"}, {"name": "Rosneft Oil Company"}], "transliteratedOtherNames": [],
        "legalAddress": {"country": "RU", "city": "Москва"}, "headquartersAddress": {"country": "RU", "city": "Москва"},
        "status": "ACTIVE", "legalForm": {"id": "4TYO"}, "registeredAs": "1027700043502", "jurisdiction": "RU", "category": "GENERAL"}}}
    e = g.entity_from(rec)
    assert e.name == "Rosneft" and e.kind == "ORG" and e.country_qid == "Q159"
    assert e.aliases[0].startswith("публичное") and "Rosneft Oil Company" in e.aliases
    assert ("lei", "253400JT3MQWNDKMJE44") in e.other_ids and ("registration", "1027700043502") in e.other_ids and ("bic", "ROSNRUMM") in e.other_ids
    assert e.properties["lei_status"] == "ACTIVE" and e.properties["legal_form"] == "4TYO"


def test_pull_emits_one_fact_per_pair_preferring_direct(monkeypatch):
    g = GleifConnector(db=None, hops=1, seed={A}, iso2_to_qid={})
    rows = [_row(A, B, "IS_DIRECTLY_CONSOLIDATED_BY"), _row(A, B, "IS_ULTIMATELY_CONSOLIDATED_BY"), _row(A, C, "IS_ULTIMATELY_CONSOLIDATED_BY")]
    monkeypatch.setattr(g, "relationship_rows", lambda: rows)
    recs = [{"id": x, "attributes": {"registration": {}, "entity": {"legalName": {"name": x}, "legalAddress": {}}}} for x in (A, B, C)]
    monkeypatch.setattr(g, "records", lambda leis: recs)
    facts = [i for i in g.pull() if hasattr(i, "predicate")]
    assert [(f.subject_external_id, f.object_external_id, f.predicate) for f in facts] == \
        [(A, B, "directly consolidated by"), (A, C, "ultimately consolidated by")]
