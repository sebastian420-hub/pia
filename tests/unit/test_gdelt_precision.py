"""GDELT precision: full CAMEO codes, state-actor gating, regions, symmetric dedup, no synthetic quotes."""
import pytest

from pia.kg.ontology import (ACTIONS, CAMEO_CODE_TO_ACTION, LLM_ACTIONS, SYMMETRIC_ACTIONS, TOPICS,
                             cameo_action)


def test_code_table_is_consistent():
    for code, (action, topic, label) in CAMEO_CODE_TO_ACTION.items():
        assert action in ACTIONS, code
        assert topic in TOPICS, code
        assert label
    assert len(LLM_ACTIONS) == 23 and LLM_ACTIONS[-1] == "OTHER"
    assert SYMMETRIC_ACTIONS <= set(ACTIONS)


@pytest.mark.parametrize("code,action,topic", [
    ("051", "PRAISE", "diplomacy"),          # was AGREE
    ("057", "SIGN_AGREEMENT", "diplomacy"),
    ("042", "VISIT", "diplomacy"),
    ("040", "MEET", "diplomacy"),            # root fallback
    ("163", "SANCTION", "sanctions"),
    ("085", "EASE_SANCTIONS", "sanctions"),
    ("173", "ARREST", "detention"),
    ("195", "AIRSTRIKE", "military"),
    ("1385", "THREATEN_FORCE", "nuclear"),
    ("192", "OCCUPY", "territory"),
    ("176", "CYBER_ATTACK", "cyber"),
    ("010", "STATEMENT", "other"),
])
def test_cameo_action(code, action, topic):
    assert cameo_action(code)[:2] == (action, topic)


def test_unknown_root_is_dropped():
    assert cameo_action("99") is None and cameo_action("") is None


# ── the agent's actor gating, with a fake resolver ────────────────────────────

class FakeResolver:
    def __init__(self):
        self.ents = {
            "Q30": {"entity_id": "us", "qid": "Q30", "kind": "COUNTRY", "name": "United States", "resolution": "RESOLVED"},
            "Q794": {"entity_id": "ir", "qid": "Q794", "kind": "COUNTRY", "name": "Iran", "resolution": "RESOLVED"},
            "Q1065": {"entity_id": "un", "qid": "Q1065", "kind": "ORG", "name": "United Nations", "resolution": "RESOLVED"},
        }
        self.local = {
            "microsoft": {"entity_id": "ms", "qid": "Q2283", "kind": "ORG", "name": "Microsoft", "resolution": "RESOLVED", "country_qid": "Q30"},
            "oklahoma": {"entity_id": "ok", "qid": "Q1649", "kind": "PLACE", "name": "Oklahoma", "resolution": "RESOLVED", "country_qid": "Q30"},
            "state department": {"entity_id": "sd", "qid": "Q789915", "kind": "ORG", "name": "State Department", "resolution": "RESOLVED",
                                 "country_qid": "Q30", "event_entity": None},
        }
        self.local["state department"]["event_entity"] = self.ents["Q30"]

    def ensure_qid(self, qid):
        return self.ents.get(qid)

    def resolve(self, surface, role="ACTOR", context=None, local_only=False, kind_hint=None):
        return self.local.get(surface.lower())


class FakeDB:
    def __init__(self):
        self.events = []
        self.reports = {}

    def execute_query(self, q, params=None, fetch=False):
        if "INSERT INTO events" in q:
            self.events.append(params)
            return None
        if "INSERT INTO intelligence_records" in q:
            uid = f"r{len(self.reports)}"
            self.reports[params[4]] = uid
            return [{"uid": uid}]
        if "SELECT uid FROM intelligence_records WHERE source_url" in q:
            uid = self.reports.get(params[0])
            return [{"uid": uid}] if uid else []
        if "SELECT source_url, content_headline" in q:
            return []
        return []


@pytest.fixture
def agent(monkeypatch):
    from pia.agents import gdelt_agent as G
    a = G.GdeltAgent.__new__(G.GdeltAgent)
    a.name = "t"
    a.db = FakeDB()
    a.resolver = FakeResolver()
    a.iso3 = {"USA": "Q30", "IRN": "Q794"}
    a.country_iso2 = {"Q30": "US", "Q794": "IR"}
    a.country_aliases = {"Q30": {"united states", "us", "america"}, "Q794": {"iran"}}
    a.MIN_MENTIONS, a.MIN_MENTIONS_SOLO, a.MIN_ABS_GOLDSTEIN, a.MIN_SOURCES_UNTYPED = 3, 10, 5, 2
    a.FETCH_TITLES = False
    return a


def row(a1name, a1cc, a1type, a2name, a2cc, a2type, code, mentions=5, sources=3, geo_cc="US", url="http://x.test/a"):
    r = [""] * 61
    r[0], r[1] = "1", "20260919"
    r[6], r[7], r[12] = a1name, a1cc, a1type
    r[16], r[17], r[22] = a2name, a2cc, a2type
    r[26], r[28] = code, code[:2]
    r[30], r[31], r[32] = "-2.0", str(mentions), str(sources)
    r[52], r[53], r[56], r[57] = "Somewhere", geo_cc, "35.0", "-97.0"
    r[60] = url
    return "\t".join(r)


def ingest(agent, *rows):
    return agent.ingest("\n".join(rows) + "\n", "file")


def test_typed_state_actors_make_an_event(agent):
    assert ingest(agent, row("UNITED STATES", "USA", "GOV", "IRAN", "IRN", "GOV", "163")) == 1
    ev = agent.db.events[0]
    assert ev[1] == "SANCTION" and ev[2] == "HOSTILE" and ev[3] == "us" and ev[4] == "ir"
    assert ev[12] == "sanctions" and ev[13] == "163"            # topic, code
    assert ev[8] is not None                                    # report linked
    assert abs(ev[9] - 0.7) < 1e-9                              # 3 sources


def test_untyped_country_alone_is_a_story_about_a_place(agent):
    # "United States" (no type) vs a PLACE: the murder-trial case
    assert ingest(agent, row("UNITED STATES", "USA", "", "OKLAHOMA", "USA", "", "190")) == 0
    # untyped both sides, country-to-country, corroborated → kept
    assert ingest(agent, row("UNITED STATES", "USA", "", "IRAN", "IRN", "", "042", sources=3)) == 1
    # same with one source → dropped
    assert ingest(agent, row("UNITED STATES", "USA", "", "IRAN", "IRN", "", "042", sources=1)) == 0


def test_typed_placeholder_cannot_carry_a_solo_event(agent):
    # "ORLANDO"/USA/GOV protesting alone (the measles story) → nothing
    assert ingest(agent, row("NURSE", "", "HLH", "ORLANDO", "USA", "GOV", "141", mentions=20)) == 0
    # the country named itself, typed, solo protest with enough mentions → kept
    assert ingest(agent, row("UNITED STATES", "USA", "GOV", "", "", "", "141", mentions=20)) == 1


def test_regions_and_places_never_act(agent):
    assert ingest(agent, row("EUROPE", "EUR", "", "IRAN", "IRN", "GOV", "051")) == 0
    assert ingest(agent, row("OKLAHOMA", "USA", "", "IRAN", "IRN", "GOV", "051")) == 0


def test_government_body_collapses_to_country(agent):
    assert ingest(agent, row("STATE DEPARTMENT", "USA", "GOV", "IRAN", "IRN", "GOV", "051")) == 1
    assert agent.db.events[0][3] == "us"


def test_symmetric_actions_dedup_on_the_pair(agent):
    ingest(agent, row("UNITED STATES", "USA", "GOV", "IRAN", "IRN", "GOV", "044"),
           row("IRAN", "IRN", "GOV", "UNITED STATES", "USA", "GOV", "044"))
    keys = {e[-1] for e in agent.db.events}
    assert len(agent.db.events) == 2 and len(keys) == 1


def test_no_quote_and_geo_only_in_actor_country(agent):
    ingest(agent, row("UNITED STATES", "USA", "GOV", "IRAN", "IRN", "GOV", "051", geo_cc="IN"))  # New Delhi dateline
    ev = agent.db.events[0]
    assert ev[5] is False                                       # event_geo flag → geo NULL
    assert "NULL" in [l for l in open(__import__('pia.agents.gdelt_agent', fromlist=['x']).__file__).read().splitlines()
                      if "'gdelt', 'gdelt', NULL" in l][0]
    ingest(agent, row("UNITED STATES", "USA", "GOV", "IRAN", "IRN", "GOV", "052", geo_cc="IR"))
    assert agent.db.events[1][5] is True
