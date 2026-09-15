"""Resolver behaviour with a fake store and fake Wikidata: strictness, government seats, scoring."""
import pytest

from pia.kg import resolver as R


class FakeDB:
    """Records queries; answers a few shapes the resolver needs."""
    def __init__(self):
        self.entities = {}     # qid -> dict
        self.local = []
        self.calls = []

    def execute_query(self, q, params=None, fetch=False):
        self.calls.append((q.strip().split()[0], params))
        if "FROM entities WHERE qid = %s" in q:
            e = self.entities.get(params[0])
            return [e] if e else []
        if "INSERT INTO entities (qid" in q:
            qid = params[0]
            e = {"entity_id": f"id-{qid}", "qid": qid, "kind": params[1], "name": params[2], "resolution": "RESOLVED"}
            self.entities[qid] = e
            return [e]
        if "INSERT INTO entities (kind, name, resolution" in q:
            e = {"entity_id": f"local-{len(self.local)}", "qid": None, "kind": params[0], "name": params[1], "resolution": params[2]}
            self.local.append(e)
            return [e]
        if "FROM entity_aliases a JOIN entities e" in q:
            return []
        if "FROM resolution_cache" in q:
            return []
        if "FROM wikidata_classes" in q:
            return []
        if "SELECT entity_id, qid FROM entities WHERE qid = ANY" in q:
            return []
        if "WHERE qid IS NULL AND resolution IN" in q:
            return []
        return [] if fetch else None

    def execute_values(self, query, rows, template=None, page_size=500):
        self.calls.append(("VALUES", len(rows)))


def parsed(qid, label, kind_class, sitelinks=50, description="", aliases=(), country=None):
    return {"qid": qid, "label": label, "description": description, "aliases": list(aliases), "p31": [kind_class],
            "coords": None, "country_qid": country, "sitelinks": sitelinks, "relations": []}


@pytest.fixture
def fake(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(R.wikidata, "classify_class", lambda c: {"Q5": "PERSON", "Q6256": "COUNTRY", "Q4830453": "ORG"}.get(c, "UNKNOWN"))
    return db


def test_generic_noun_is_rejected(fake):
    assert R.Resolver(fake).resolve("prosecutors") is None
    assert R.Resolver(fake).resolve("Iran's president", role="ACTOR") is None


def test_government_seat_resolves_to_country(fake, monkeypatch):
    monkeypatch.setattr(R.wikidata, "get_entities", lambda qids: {"Q148": parsed("Q148", "China", "Q6256", 300)})
    ent = R.Resolver(fake).resolve("Beijing", role="ACTOR")
    assert ent["qid"] == "Q148" and ent["role"] == "GOVERNMENT"


def test_clear_winner_is_resolved_automatically(fake, monkeypatch):
    monkeypatch.setattr(R.wikidata, "search", lambda text, limit=5: [{"qid": "Q30", "label": "United States", "description": "country", "match": "United States"},
                                                                       {"qid": "Q637413", "label": "United States Census Bureau", "description": "agency", "match": "United States Census Bureau"}])
    monkeypatch.setattr(R.wikidata, "get_entities", lambda qids: {
        "Q30": parsed("Q30", "United States", "Q6256", 300, aliases=("the US", "USA")),
        "Q637413": parsed("Q637413", "United States Census Bureau", "Q4830453", 40)})
    ent = R.Resolver(fake).resolve("the US", kind_hint="COUNTRY", role="ACTOR")
    assert ent["qid"] == "Q30" and ent["resolution"] == "RESOLVED"


def test_ambiguous_name_goes_to_review_without_llm(fake, monkeypatch):
    monkeypatch.setattr(R.wikidata, "search", lambda text, limit=5: [{"qid": "Q1", "label": "Cambridge", "description": "city in England", "match": "Cambridge"},
                                                                       {"qid": "Q2", "label": "Cambridge", "description": "city in Massachusetts", "match": "Cambridge"}])
    monkeypatch.setattr(R.wikidata, "get_entities", lambda qids: {"Q1": parsed("Q1", "Cambridge", "Q515", 120), "Q2": parsed("Q2", "Cambridge", "Q515", 110)})
    monkeypatch.setattr(R.wikidata, "classify_class", lambda c: "PLACE")
    ent = R.Resolver(fake).resolve("Cambridge", kind_hint="PLACE")
    assert ent["resolution"] == "NEEDS_REVIEW" and ent["qid"] is None


def test_llm_tiebreak_picks_candidate(fake, monkeypatch):
    monkeypatch.setattr(R.wikidata, "search", lambda text, limit=5: [{"qid": "Q1", "label": "Cambridge", "description": "city in England", "match": "Cambridge"},
                                                                       {"qid": "Q2", "label": "Cambridge", "description": "city in Massachusetts", "match": "Cambridge"}])
    monkeypatch.setattr(R.wikidata, "get_entities", lambda qids: {"Q1": parsed("Q1", "Cambridge", "Q515", 120), "Q2": parsed("Q2", "Cambridge", "Q515", 110)})
    monkeypatch.setattr(R.wikidata, "classify_class", lambda c: "PLACE")
    ent = R.Resolver(fake, llm_choose=lambda s, ctx, cands: 1).resolve("Cambridge", kind_hint="PLACE")
    assert ent["qid"] == "Q2"


def test_wrong_kind_candidate_is_penalised(fake, monkeypatch):
    monkeypatch.setattr(R.wikidata, "search", lambda text, limit=5: [{"qid": "Q9", "label": "Mercury", "description": "planet", "match": "Mercury"}])
    monkeypatch.setattr(R.wikidata, "get_entities", lambda qids: {"Q9": parsed("Q9", "Mercury", "Q634", 200)})
    ent = R.Resolver(fake).resolve("Mercury", kind_hint="PERSON")
    assert ent["resolution"] == "NEEDS_REVIEW"
