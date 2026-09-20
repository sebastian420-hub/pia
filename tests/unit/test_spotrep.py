"""SPOTREP: the fixed human-report format is read without guessing, and bad reports are refused with a reason."""
import pytest

from pia.connectors.base import Document, Entity, Event, Identifier
from pia.connectors.spotrep import SpotrepConnector, SpotrepError, parse

SAMPLE = """reporter: crow
observed: 2026-09-20T08:15Z
location: 33.51, 36.29
basis: direct
confidence: 0.8
mission: Gulf

ENTITIES:
- Abu Khalid | person | passport: X123; plate: ABC-1 | drives a white Hilux
- 4th Division | unit

EVENTS:
- 4th Division | moved artillery to | Qatana | 2026-09-20T07:00Z | 33.43, 36.08 | -2
- Abu Khalid | met | 4th Division

NOTES:
Two trucks seen at the checkpoint at dawn.
Locals say the unit rotated in last week.
"""


def test_parse_markdown_form():
    rep = parse(SAMPLE)
    assert rep.reporter == "crow" and rep.basis == "direct" and rep.confidence == 0.8 and rep.mission == "Gulf"
    assert rep.location == (33.51, 36.29)
    assert [e["kind"] for e in rep.entities] == ["PERSON", "ORG"]
    assert rep.entities[0]["ids"] == [("passport", "X123"), ("plate", "ABC-1")]
    assert rep.events[0]["stance"] == -2 and rep.events[0]["place"] == (33.43, 36.08)
    assert rep.events[1]["time"] == rep.observed and rep.events[1]["place"] == rep.location   # defaults to the report's
    assert rep.notes.startswith("Two trucks")


def test_parse_json_form():
    rep = parse('{"reporter": "crow", "observed": "2026-09-20", "entities": [{"name": "Iran", "kind": "country"}],'
                ' "events": [{"actor": "Iran", "predicate": "warned", "target": "Iraq", "stance": -1}], "notes": ""}')
    assert rep.entities[0]["kind"] == "COUNTRY" and rep.events[0]["stance"] == -1


@pytest.mark.parametrize("text, msg", [
    ("observed: 2026-09-20\nNOTES:\nx", "reporter"),
    ("reporter: a\nobserved: yesterday\nNOTES:\nx", "cannot read time"),
    ("reporter: a\nobserved: 2026-09-20\nbasis: rumour\nNOTES:\nx", "basis"),
    ("reporter: a\nobserved: 2026-09-20\nENTITIES:\n- X | alien", "unknown kind"),
    ("reporter: a\nobserved: 2026-09-20\nEVENTS:\n- X", "actor | predicate"),
    ("reporter: a\nobserved: 2026-09-20\nEVENTS:\n- X | hit | Y | | | 9", "stance"),
    ("reporter: a\nobserved: 2026-09-20\ncolour: red\nNOTES:\nx", "unknown header"),
    ("reporter: a\nobserved: 2026-09-20", "empty"),
])
def test_bad_reports_are_refused_with_a_reason(text, msg):
    with pytest.raises(SpotrepError, match=msg):
        parse(text)


def test_connector_items():
    rep = parse(SAMPLE)
    items = list(SpotrepConnector(rep, "spotrep:test.md", "m1").pull())
    ents = [i for i in items if isinstance(i, Entity)]
    assert {e.name for e in ents} == {"Abu Khalid", "4th Division", "Qatana"}      # Qatana appears only as a target
    assert [i for i in items if isinstance(i, Identifier)][0].value == "X123"
    evs = [i for i in items if isinstance(i, Event)]
    assert evs[0].family == "HOSTILE·force" and evs[0].record_ref == "spotrep:test.md#L13" and "reported by crow" in evs[0].quote
    doc = [i for i in items if isinstance(i, Document)][0]
    assert doc.source_type == "HUMINT" and doc.mission_id == "m1" and doc.geo == (33.51, 36.29)


def test_reporter_trust_follows_basis_and_confidence():
    assert SpotrepConnector(parse(SAMPLE), "r").source["trust"] == 0.63                       # direct 0.7 × (0.5 + 0.4)
    hearsay = parse(SAMPLE.replace("basis: direct", "basis: hearsay").replace("confidence: 0.8", "confidence: 0.2"))
    assert SpotrepConnector(hearsay, "r").source["trust"] == 0.18
