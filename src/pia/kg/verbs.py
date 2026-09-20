"""
Living verbs: the families are fixed, the verbs grow on their own.

  family   — HOSTILE·force, HOSTILE·sanction, … (FAMILIES): decides the wheel sector and the
             default colour; the model can never invent one
  verb     — an open catalogue row ("call for a boycott of"): canonical phrase, family, default
             stance, examples, embedding; created automatically when a new phrasing appears
  stance   — judged per event (−3 … +3), never derived from the verb
  modality — asserted | intended | claimed | hypothetical | denied; polarity — happened / negated

canonical(predicate, family) maps the article's words to a verb: exact → alias → embedding
similarity within the family (≥ SIM_MERGE) → otherwise a new auto verb. No human in the loop;
the /review Verbs tab lets a person rename, move, merge or reject later.
"""
import json
from typing import Callable, Dict, List, Optional, Tuple

from loguru import logger

from pia.kg.normalize import normalize

# ── families (fixed) ──────────────────────────────────────────────────────────
FAMILIES: Dict[str, Tuple[str, int]] = {
    # family              (kind,          typical stance)
    "HOSTILE·force":       ("HOSTILE", -3),
    "HOSTILE·coercion":    ("HOSTILE", -2),
    "HOSTILE·sanction":    ("HOSTILE", -2),
    "HOSTILE·accusation":  ("HOSTILE", -1),
    "HOSTILE·threat":      ("HOSTILE", -2),
    "COOPERATIVE·agreement": ("COOPERATIVE", 2),
    "COOPERATIVE·aid":     ("COOPERATIVE", 2),
    "COOPERATIVE·support": ("COOPERATIVE", 1),
    "COOPERATIVE·meeting": ("COOPERATIVE", 1),
    "NEUTRAL·role":        ("ROLE", 0),
    "NEUTRAL·ownership":   ("OWNERSHIP", 0),
    "NEUTRAL·statement":   (None, 0),
}
FAMILY_NAMES = tuple(FAMILIES)
MODALITIES = ("asserted", "intended", "claimed", "hypothetical", "denied")
SIM_MERGE = 0.80          # cosine similarity above which a new phrasing is an alias of an existing verb
                          # (text-embedding-3-small: "praised"↔"praise" 0.80, "bombed"↔"bomb" 0.59 — so the model
                          # is asked to pick from the catalogue first; embeddings only catch close variants)

IRREGULAR = {"met": "meet", "held": "hold", "sent": "send", "struck": "strike", "shot": "shoot", "bought": "buy",
             "sold": "sell", "led": "lead", "left": "leave", "took": "take", "gave": "give", "made": "make",
             "said": "say", "told": "tell", "fought": "fight", "sought": "seek", "won": "win", "lost": "lose",
             "broke": "break", "withdrew": "withdraw", "began": "begin", "flew": "fly", "spoke": "speak",
             "froze": "freeze", "cut": "cut", "hit": "hit", "put": "put", "set": "set", "shut": "shut"}


def lemma_phrase(phrase: str) -> str:
    """First word to its base form ('launched strikes on' → 'launch strikes on'); enough to merge inflections."""
    words = phrase.split()
    if not words:
        return phrase
    w = words[0]
    if w in IRREGULAR:
        base = IRREGULAR[w]
    elif w.endswith("ied") and len(w) > 4:
        base = w[:-3] + "y"
    elif w.endswith("ed") and len(w) > 4:
        stem = w[:-2]
        if stem + "e" in _E_VERBS:
            base = stem + "e"                                  # praised → praise
        elif len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiouls":
            base = stem[:-1]                                   # stopped → stop
        else:
            base = stem                                        # launched → launch
    elif w.endswith("ing") and len(w) > 5:
        stem = w[:-3]
        base = stem + "e" if stem + "e" in _E_VERBS else (stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiouls" else stem)
    elif w.endswith("ies") and len(w) > 4:
        base = w[:-3] + "y"                                    # denies → deny
    elif w.endswith(("ses", "xes", "zes", "ches", "shes")) and len(w) > 4:
        base = w[:-2]                                          # pushes → push
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        base = w[:-1]                                          # carries handled above; meets → meet
    else:
        base = w
    return " ".join([base] + words[1:])


_PREPOSITIONS = {"with", "on", "to", "against", "from", "of", "at", "in", "for", "over", "into"}
_E_VERBS = {"strike", "praise", "recognise", "recognize", "release", "blockade", "condemn", "criticise", "criticize", "mediate",
            "negotiate", "declare", "announce", "acquire", "invade", "seize", "expel", "impose", "propose", "promise", "pledge",
            "withdraw", "close", "freeze", "invite", "welcome", "endorse", "denounce", "escalate", "evacuate", "capture",
            "liberate", "recruit", "fire", "arrive", "leave", "issue", "provide", "receive", "remove", "reduce", "use",
            "urge", "accuse", "ease", "raise", "seize", "resume", "finance", "advise", "oppose", "compete", "engage"}


def kind_for_stance(stance: Optional[int], family: Optional[str]) -> Optional[str]:
    """The ledger a verified event feeds. Stance decides; the family only for role / ownership."""
    if family in ("NEUTRAL·role", "NEUTRAL·ownership"):
        return FAMILIES[family][0]
    if stance is None:
        return None
    if stance <= -1:
        return "HOSTILE"
    if stance >= 1:
        return "COOPERATIVE"
    return None


def guard_family(family: Optional[str], stance: Optional[int]) -> str:
    """A family the model invents is mapped to the closest real one by stance."""
    if family in FAMILIES:
        return family
    f = (family or "").upper()
    for name in FAMILY_NAMES:          # tolerate "hostile/force", "HOSTILE force", "force"
        head, sub = name.split("·")
        if sub in f.lower() or f.replace("/", "·").replace(" ", "·") == name:
            return name
    s = stance or 0
    return "HOSTILE·accusation" if s <= -1 else "COOPERATIVE·support" if s >= 1 else "NEUTRAL·statement"


# ── seed: the old 23 actions + GDELT's finer codes, expressed as verbs ────────
# (verb, family, default stance, cameo codes, old action name)
SEED: List[Tuple[str, str, int, List[str], Optional[str]]] = [
    ("strike",                   "HOSTILE·force",     -3, ["190", "193", "194"], "ARMED_ATTACK"),
    ("attack",                   "HOSTILE·force",     -3, ["18", "182"], "ATTACK"),
    ("carry out airstrikes on",  "HOSTILE·force",     -3, ["195"], "AIRSTRIKE"),
    ("bomb",                     "HOSTILE·force",     -3, ["183"], "BOMBING"),
    ("occupy",                   "HOSTILE·force",     -3, ["192"], "OCCUPY"),
    ("blockade",                 "HOSTILE·force",     -2, ["191"], "BLOCKADE"),
    ("abduct",                   "HOSTILE·force",     -3, ["181"], "ABDUCT"),
    ("assassinate",              "HOSTILE·force",     -3, ["185", "186"], "ASSASSINATION"),
    ("violate a ceasefire with", "HOSTILE·force",     -2, ["196"], "VIOLATE_CEASEFIRE"),
    ("commit mass violence against", "HOSTILE·force", -3, ["20", "201", "202", "203", "204"], "MASS_VIOLENCE"),
    ("attack cybernetically",    "HOSTILE·force",     -2, ["176", "155"], "CYBER_ATTACK"),
    ("deploy forces against",    "HOSTILE·force",     -2, [], "DEPLOY"),
    ("coerce",                   "HOSTILE·coercion",  -2, ["17", "170", "171", "172", "175"], "COERCE"),
    ("arrest",                   "HOSTILE·coercion",  -2, ["173"], "ARREST"),
    ("expel",                    "HOSTILE·coercion",  -2, ["174", "166"], "DEPORT"),
    ("show military force towards", "HOSTILE·coercion", -1, ["15", "150", "151", "152", "153", "154"], "MILITARY_POSTURE"),
    ("impose sanctions on",      "HOSTILE·sanction",  -2, ["16", "163"], "SANCTION"),
    ("cut aid to",               "HOSTILE·sanction",  -2, ["162"], None),
    ("call for a boycott of",    "HOSTILE·sanction",  -2, ["143", "1312"], None),
    ("boycott",                  "HOSTILE·sanction",  -2, [], None),
    ("refuse to ease sanctions on", "HOSTILE·sanction", -1, ["1231", "1233", "1244"], "REFUSE_EASE"),
    ("cut relations with",       "HOSTILE·sanction",  -2, ["161", "164"], "CUT_RELATIONS"),
    ("reject trade with",        "HOSTILE·sanction",  -1, ["1211"], "REJECT_TRADE"),
    ("accuse",                   "HOSTILE·accusation", -1, ["11", "112", "1121", "1122", "1123", "1124", "1125"], "ACCUSE"),
    ("condemn",                  "HOSTILE·accusation", -1, ["111"], None),
    ("criticise",                "HOSTILE·accusation", -1, ["110"], None),
    ("reject",                   "HOSTILE·accusation", -1, ["12", "120"], "REJECT"),
    ("protest against",          "HOSTILE·accusation", -1, ["14", "141", "145"], "PROTEST"),
    ("threaten",                 "HOSTILE·threat",    -2, ["13", "130", "1313", "134", "139"], "THREATEN"),
    ("threaten sanctions against", "HOSTILE·threat",  -2, ["1311"], "THREATEN_SANCTION"),
    ("threaten military force against", "HOSTILE·threat", -2, ["138", "1381", "1382", "1385"], "THREATEN_FORCE"),
    ("sign an agreement with",   "COOPERATIVE·agreement", 2, ["057"], "SIGN_AGREEMENT"),
    ("agree with",               "COOPERATIVE·agreement", 2, ["05", "06", "08", "080"], "AGREE"),
    ("cooperate with",           "COOPERATIVE·agreement", 2, ["03", "030", "063", "064"], "COOPERATE"),
    ("cooperate economically with", "COOPERATIVE·agreement", 2, ["061"], "TRADE_COOPERATE"),
    ("cooperate militarily with", "COOPERATIVE·agreement", 2, ["062"], "MILITARY_COOPERATE"),
    ("negotiate with",           "COOPERATIVE·agreement", 1, ["036", "037", "039", "046"], "NEGOTIATE"),
    ("declare a truce with",     "COOPERATIVE·agreement", 3, ["0871", "0872", "0873", "0874"], "TRUCE"),
    ("recognise",                "COOPERATIVE·agreement", 2, ["054"], "RECOGNIZE"),
    ("send aid to",              "COOPERATIVE·aid",   2, ["07", "07x"], "AID"),
    ("send military aid to",     "COOPERATIVE·aid",   2, ["072", "074"], "MILITARY_AID"),
    ("send economic aid to",     "COOPERATIVE·aid",   2, ["071"], "ECONOMIC_AID"),
    ("send humanitarian aid to", "COOPERATIVE·aid",   2, ["073"], "HUMANITARIAN_AID"),
    ("ease sanctions on",        "COOPERATIVE·aid",   2, ["085", "0811"], "EASE_SANCTIONS"),
    ("release",                  "COOPERATIVE·aid",   2, ["0841", "0842"], "RELEASE"),
    ("grant asylum to",          "COOPERATIVE·aid",   2, ["075"], None),
    ("invest in",                "NEUTRAL·ownership", 1, [], "INVEST"),
    ("praise",                   "COOPERATIVE·support", 1, ["051"], "PRAISE"),
    ("defend",                   "COOPERATIVE·support", 1, ["052", "053"], "DEFEND"),
    ("support",                  "COOPERATIVE·support", 1, [], None),
    ("appeal to",                "NEUTRAL·statement", 0, ["02", "10"], "APPEAL"),
    ("meet",                     "COOPERATIVE·meeting", 1, ["04", "040", "044"], "MEET"),
    ("visit",                    "COOPERATIVE·meeting", 1, ["042"], "VISIT"),
    ("host",                     "COOPERATIVE·meeting", 1, ["043"], "HOST"),
    ("speak by phone with",      "COOPERATIVE·meeting", 1, ["041"], "CALL"),
    ("mediate between",          "COOPERATIVE·meeting", 1, ["045"], "MEDIATE"),
    ("appoint",                  "NEUTRAL·role",      0, [], "APPOINT"),
    ("resign from",              "NEUTRAL·role",      0, [], "RESIGN"),
    ("elect",                    "NEUTRAL·role",      0, [], "ELECT"),
    ("acquire",                  "NEUTRAL·ownership", 0, [], "ACQUIRE"),
    ("say",                      "NEUTRAL·statement", 0, ["01", "010", "09"], "STATEMENT"),
    ("announce",                 "NEUTRAL·statement", 0, [], None),
    ("deny",                     "NEUTRAL·statement", 0, ["016"], None),
    ("suffer a disaster",        "NEUTRAL·statement", 0, [], "DISASTER"),
    ("act towards",              "NEUTRAL·statement", 0, [], "OTHER"),
]


class VerbCatalogue:
    """Reads and grows the verbs table. `embed` is optional: without it, only exact / alias matches merge."""

    def __init__(self, db, embed: Optional[Callable[[str], List[float]]] = None):
        self.db = db
        self.embed = embed
        self._by_phrase: Dict[str, dict] = {}
        self._alias: Dict[str, str] = {}
        self._by_action: Dict[str, str] = {}
        self.reload()

    # ── loading ──
    def reload(self):
        rows = self.db.execute_query("""
            SELECT verb_id::text, verb, family, default_stance, status, cameo_codes, seen_count
            FROM verbs WHERE status IN ('seed','auto','curated')
        """, fetch=True) or []
        self._by_phrase = {r["verb"]: dict(r) for r in rows}
        self._alias = {r["alias"]: r["verb_id"] for r in (self.db.execute_query(
            "SELECT alias, verb_id::text FROM verb_aliases", fetch=True) or [])}
        self._by_action = {}
        for v, fam, st, codes, action in SEED:
            row = self._by_phrase.get(v)
            if row and action:
                self._by_action[action] = row["verb_id"]

    def seed(self) -> int:
        """Insert the seed verbs (idempotent)."""
        n = 0
        for verb, family, stance, codes, action in SEED:
            res = self.db.execute_query("""
                INSERT INTO verbs (verb, family, default_stance, status, cameo_codes, created_by)
                VALUES (%s, %s, %s, 'seed', %s, 'seed')
                ON CONFLICT (verb) DO UPDATE SET cameo_codes = EXCLUDED.cameo_codes
                RETURNING (xmax = 0) AS inserted
            """, (verb, family, stance, codes), fetch=True)
            n += 1 if res and res[0]["inserted"] else 0
        self.reload()
        return n

    # ── lookups ──
    def by_action(self, action: str) -> Optional[str]:
        """verb_id for one of the old action names (analyst / GDELT compatibility)."""
        return self._by_action.get(action)

    def by_cameo(self, code: str) -> Optional[dict]:
        code = (code or "").strip()
        best = None
        for row in self._by_phrase.values():
            for c in row["cameo_codes"] or []:
                if code.startswith(c) and (best is None or len(c) > best[0]):
                    best = (len(c), row)
        return best[1] if best else None

    def prompt_block(self, per_family: int = 8) -> str:
        """The families with their most-used verbs, for the extraction prompt."""
        lines = []
        for fam in FAMILY_NAMES:
            verbs = sorted((r for r in self._by_phrase.values() if r["family"] == fam),
                           key=lambda r: (-(r["seen_count"] or 0), r["verb"]))[:per_family]
            lines.append(f"{fam}: " + " · ".join(r["verb"] for r in verbs))
        return "\n".join(lines)

    # ── matching ──
    def canonical(self, predicate: str, family: str, stance: Optional[int] = None, quote: str = "") -> Tuple[str, str, bool]:
        """
        -> (verb_id, canonical verb, is_new). Exact phrase → alias → embedding similarity in the
        same family → new auto verb. Records the phrasing as an alias and bumps seen_count.
        """
        phrase = _clean(predicate)
        if not phrase:
            phrase = "act towards"
        family = guard_family(family, stance)
        lem = lemma_phrase(phrase)
        stripped = " ".join(lem.split()[:-1]) if lem.split()[-1] in _PREPOSITIONS and len(lem.split()) > 1 else lem
        for candidate in dict.fromkeys((phrase, lem, stripped)):
            row = self._by_phrase.get(candidate)
            if row:
                self._touch(row["verb_id"], quote)
                return row["verb_id"], row["verb"], False
            vid = self._alias.get(candidate)
            if vid:
                self._touch(vid, quote)
                return vid, next((r["verb"] for r in self._by_phrase.values() if r["verb_id"] == vid), candidate), False
        phrase = lemma_phrase(phrase)

        vec = None
        if self.embed:
            try:
                vec = self.embed(phrase)
            except Exception as e:                      # embedding down: fall through to a new verb
                logger.warning(f"verb embedding failed: {e}")
            if vec is not None:
                hit = self.db.execute_query("""
                    SELECT verb_id::text, verb, 1 - (embedding <=> %s::vector) AS sim
                    FROM verbs WHERE family = %s AND status IN ('seed','auto','curated') AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector LIMIT 1
                """, (vec, family, vec), fetch=True)
                if hit and hit[0]["sim"] is not None and float(hit[0]["sim"]) >= SIM_MERGE:
                    vid = hit[0]["verb_id"]
                    self.db.execute_query("INSERT INTO verb_aliases (alias, verb_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (phrase, vid))
                    self._alias[phrase] = vid
                    self._touch(vid, quote)
                    return vid, hit[0]["verb"], False

        # genuinely new: create it in the family, usable at once, visible on the Verbs tab
        res = self.db.execute_query("""
            INSERT INTO verbs (verb, family, default_stance, status, examples, embedding, seen_count, created_by)
            VALUES (%s, %s, %s, 'auto', %s::jsonb, %s::vector, 1, 'model')
            ON CONFLICT (verb) DO UPDATE SET seen_count = verbs.seen_count + 1
            RETURNING verb_id::text
        """, (phrase, family, int(stance or FAMILIES[family][1]), json.dumps([quote][:1] if quote else []), vec), fetch=True)
        vid = res[0]["verb_id"]
        self._by_phrase[phrase] = {"verb_id": vid, "verb": phrase, "family": family, "default_stance": stance, "status": "auto", "cameo_codes": [], "seen_count": 1}
        logger.info(f"new verb [{family}] '{phrase}'")
        return vid, phrase, True

    def _touch(self, verb_id: str, quote: str):
        self.db.execute_query("""
            UPDATE verbs SET seen_count = seen_count + 1, updated_at = NOW(),
                   examples = CASE WHEN jsonb_array_length(examples) < 5 AND %s <> '' THEN examples || to_jsonb(%s::text) ELSE examples END
            WHERE verb_id = %s
        """, (quote, quote[:300], verb_id))

    def embed_missing(self, limit: int = 200) -> int:
        """Fill embeddings for verbs that have none (seed rows, or rows created while embedding was down)."""
        if not self.embed:
            return 0
        rows = self.db.execute_query("SELECT verb_id::text, verb FROM verbs WHERE embedding IS NULL LIMIT %s", (limit,), fetch=True) or []
        n = 0
        for r in rows:
            try:
                self.db.execute_query("UPDATE verbs SET embedding = %s::vector WHERE verb_id = %s", (self.embed(r["verb"]), r["verb_id"]))
                n += 1
            except Exception as e:
                logger.warning(f"embed verb '{r['verb']}': {e}")
                break
        return n


def _clean(predicate: str) -> str:
    """'Launched strikes on' → 'launched strikes on'; strips quotes and trailing punctuation; ≤ 8 words."""
    p = normalize(predicate or "")
    words = p.split()
    return " ".join(words[:8])
