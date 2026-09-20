"""Missions: the pieces that do not need a database."""
import re

from pia.kg import missions


class FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def execute_query(self, sql, params=None, fetch=False):
        return self.rows if fetch else None


def test_watch_names_match_at_word_start_only():
    db = FakeDB([{"mid": "m1", "alias": "iran"}, {"mid": "m1", "alias": "islamic republic of iran"}])
    pats = missions.watch_names(db)
    assert missions.tag_report(pats, "tehran says iran will respond") == "m1"
    assert missions.tag_report(pats, "iranian officials said") == "m1"          # prefix of a word is fine
    assert missions.tag_report(pats, "miranda kerr opens a shop") is None          # inside a word is not
    assert missions.tag_report({}, "anything") is None


def test_watch_names_escape_regex_characters():
    db = FakeDB([{"mid": "m1", "alias": "c++ (group)"}])
    pats = missions.watch_names(db)
    assert isinstance(pats["m1"], re.Pattern)
    assert missions.tag_report(pats, "the c++ (group) met") == "m1"


def test_is_general():
    general = {"watchlist": [], "countries": [], "has_area": False, "topics": []}
    gulf = dict(general, countries=["Q794"])
    assert missions.is_general(general)
    assert not missions.is_general(gulf)


def test_mission_feeds_deduplicated_and_sorted():
    db = FakeDB([{"feeds": ["https://b", "https://a"]}, {"feeds": ["https://a", ""]}])
    assert missions.mission_feeds(db) == ["https://a", "https://b"]


def test_topics_map_to_report_domains():
    assert missions.TOPIC_TO_DOMAIN["military"] == "MILITARY"
    assert missions.TOPIC_TO_DOMAIN["sanctions"] == "FINANCIAL"
    assert missions.TOPIC_TO_DOMAIN["other"] is None
