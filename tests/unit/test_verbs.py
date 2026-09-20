"""Living verbs: families are fixed, verbs grow; matching by phrase, lemma, alias, embedding, else new."""
from pia.kg.verbs import FAMILIES, SEED, VerbCatalogue, guard_family, kind_for_stance, lemma_phrase


class FakeDB:
    def __init__(self):
        self.verbs = {}       # verb -> row
        self.aliases = {}
        self.n = 0

    def execute_query(self, q, params=None, fetch=False):
        if q.strip().startswith("SELECT verb_id::text, verb, family, default_stance"):
            return list(self.verbs.values())
        if "FROM verb_aliases" in q:
            return [{"alias": a, "verb_id": v} for a, v in self.aliases.items()]
        if q.strip().startswith("INSERT INTO verbs (verb, family, default_stance, status, cameo_codes"):
            verb, family, stance, codes = params
            new = verb not in self.verbs
            self.n += 1
            self.verbs.setdefault(verb, {"verb_id": f"v{self.n}", "verb": verb, "family": family, "default_stance": stance, "status": "seed", "cameo_codes": codes, "seen_count": 0})
            return [{"inserted": new}]
        if q.strip().startswith("INSERT INTO verbs (verb, family, default_stance, status, examples"):
            verb, family, stance = params[0], params[1], params[2]
            self.n += 1
            self.verbs[verb] = {"verb_id": f"v{self.n}", "verb": verb, "family": family, "default_stance": stance, "status": "auto", "cameo_codes": [], "seen_count": 1}
            return [{"verb_id": f"v{self.n}"}]
        if "INSERT INTO verb_aliases" in q:
            self.aliases[params[0]] = params[1]
            return None
        if q.strip().startswith("UPDATE verbs SET seen_count"):
            return None
        if "FROM verbs WHERE family" in q:            # embedding search: nothing similar
            return []
        return []


def test_seed_covers_every_family_and_old_action():
    families = {f for _, f, _, _, _ in SEED}
    assert families == set(FAMILIES)
    actions = {a for *_, a in SEED if a}
    for old in ("ATTACK", "SANCTION", "MEET", "AGREE", "APPEAL", "STATEMENT", "OTHER", "AID"):
        assert old in actions


def test_lemma_and_matching():
    assert lemma_phrase("launched strikes on") == "launch strikes on"
    assert lemma_phrase("praised") == "praise" and lemma_phrase("struck") == "strike" and lemma_phrase("denies") == "deny"
    db = FakeDB()
    cat = VerbCatalogue(db)
    cat.seed()
    vid, verb, new = cat.canonical("praised", "COOPERATIVE·support", 1)
    assert verb == "praise" and not new
    vid2, verb2, new2 = cat.canonical("met with", "COOPERATIVE·meeting", 1)
    assert verb2 == "meet" and not new2
    vid3, verb3, new3 = cat.canonical("Divested its pension fund from", "HOSTILE·sanction", -2, quote="Norway divested…")
    assert new3 and verb3 == "divest its pension fund from" and db.verbs[verb3]["family"] == "HOSTILE·sanction"
    # the same phrasing again is not new
    assert cat.canonical("divested its pension fund from", "HOSTILE·sanction", -2)[2] is False


def test_family_guard_and_stance_kind():
    assert guard_family("HOSTILE·force", -3) == "HOSTILE·force"
    assert guard_family("hostile/force", -3) == "HOSTILE·force"
    assert guard_family("made-up", -2) == "HOSTILE·accusation"
    assert guard_family("made-up", 2) == "COOPERATIVE·support"
    assert guard_family(None, 0) == "NEUTRAL·statement"
    assert kind_for_stance(-2, "HOSTILE·sanction") == "HOSTILE"
    assert kind_for_stance(0, "NEUTRAL·statement") is None
    assert kind_for_stance(0, "NEUTRAL·role") == "ROLE"
    assert kind_for_stance(1, "COOPERATIVE·meeting") == "COOPERATIVE"
