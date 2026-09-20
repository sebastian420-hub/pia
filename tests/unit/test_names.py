"""Self-maintaining names: the rules that need no database."""
from pia.kg.names import NameKeeper


def test_head_of_strips_collective_and_qualifier_words():
    nk = NameKeeper(db=None)
    assert nk.head_of("Chinese Foreign Ministry") == "chinese"
    assert nk.head_of("Houthi-run Health Ministry") == "houthi"
    assert nk.head_of("Dutch riot police") == "dutch"
    assert nk.head_of("South Korean government") == "south korean"
    assert nk.head_of("US embassy") == "us"


def test_head_of_leaves_real_names_alone():
    nk = NameKeeper(db=None)
    assert nk.head_of("Jacob Wulfson") is None            # no collective word
    assert nk.head_of("Messina Touring Group") == "messina touring"   # a head, but no owner will match it
    assert nk.head_of("state media") is None              # nothing left once the collective words go
    assert nk.head_of("government") is None


class FakeDB:
    """Answers alias / country queries from a small in-memory table."""
    def __init__(self, aliases, countries=()):
        self.aliases = aliases          # [(entity_id, kind, alias_norm, current)]
        self.countries = set(countries)

    def execute_query(self, sql, params=None, fetch=False):
        if "a.alias_norm = %s OR a.alias_norm = %s OR a.alias_norm LIKE %s" in sql:
            kinds, head, plural, prefix, _ = params
            rows = [{"entity_id": e, "kind": k, "sitelinks": 1, "mention_count": 1, "alias_norm": a}
                    for e, k, a, _ in self.aliases if k in kinds and (a == head or a == plural or a.startswith(prefix[:-1]))]
            rows.sort(key=lambda r: (r["alias_norm"] == head, r["kind"] == "COUNTRY"), reverse=True)
            return rows
        if "e.metadata ? 'iso3' AND a.alias_norm = %s" in sql:
            return [{"entity_id": e} for e, k, a, cur in self.aliases if k == "COUNTRY" and cur and a == params[0]][:1]
        return []


def test_owner_by_alias_plural_and_prefix():
    nk = NameKeeper(FakeDB([("H", "ORG", "houthis", False), ("H", "ORG", "houthi rebels", False),
                            ("K1", "COUNTRY", "korea", True), ("K2", "COUNTRY", "korea north", True)]))
    nk._demonyms, nk._current = {}, {}
    assert nk.owner_of("houthi")["entity_id"] == "H"       # plural + prefix hits, all the same entity
    assert nk.owner_of("korea")["entity_id"] == "K1"       # exact hit wins over a prefix of another
    assert nk.owner_of("messina touring") is None


def test_owner_prefers_current_state_then_adjective_then_any_demonym():
    nk = NameKeeper(FakeDB([("IQ", "COUNTRY", "iraq", True)]))
    nk._demonyms = {"iraqi": "KINGDOM_OF_IRAQ", "russian": "RU", "prussian": "PRUSSIA"}
    nk._current = {"iraqi": False, "russian": True, "prussian": False}
    assert nk.owner_of("russian") == {"entity_id": "RU", "how": "demonym"}
    assert nk.owner_of("iraqi") == {"entity_id": "IQ", "how": "adjective"}          # the live country beats the kingdom
    assert nk.owner_of("prussian") == {"entity_id": "PRUSSIA", "how": "demonym"}    # nothing better: the historical one
