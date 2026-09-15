import pytest

from pia.kg.normalize import looks_generic, normalize
from pia.kg.ontology import ACTIONS, CAMEO_ROOT_TO_ACTION, GOVERNMENT_SEATS, RELATION_KINDS


@pytest.mark.parametrize("raw, expected", [
    ("The United States", "united states"),
    ("Iran's", "iran"),
    ("Málaga", "malaga"),
    ("  U.S.  ", "u s"),
    ("Al-Mamlaka", "al-mamlaka"),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("name", ["king", "prosecutors", "pipeline", "Iran's president", "Danish prime minister",
                                  "security services", "the kingdom", "Gulf nations", "officials"])
def test_generic_names_rejected(name):
    assert looks_generic(name)


@pytest.mark.parametrize("name", ["Iran", "SpaceX", "Houthis", "Donald Trump", "NATO", "USS Abraham Lincoln", "Bab al-Mandab Strait"])
def test_real_names_kept(name):
    assert not looks_generic(name)


def test_every_action_has_a_relation_or_none():
    for action, (codes, kind, tone) in ACTIONS.items():
        assert kind is None or kind in RELATION_KINDS
        assert -10 <= tone <= 10


def test_cameo_roots_map_to_known_actions():
    assert set(CAMEO_ROOT_TO_ACTION.values()) <= set(ACTIONS)
    assert CAMEO_ROOT_TO_ACTION["18"] == "ATTACK" and CAMEO_ROOT_TO_ACTION["05"] == "AGREE"


def test_government_seats_are_qids():
    assert all(q.startswith("Q") for q in GOVERNMENT_SEATS.values())
    assert GOVERNMENT_SEATS["beijing"] == "Q148" and GOVERNMENT_SEATS["the kremlin"] == "Q159"
