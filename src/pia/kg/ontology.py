"""
The small vocabulary the whole web speaks.

Kinds  : what an entity is.
Actions: what an event is (CAMEO root codes, so GDELT maps without an LLM).
Relation kinds: what a summary between two entities means.
"""

KINDS = ("PERSON", "ORG", "COUNTRY", "PLACE", "VESSEL", "AIRCRAFT", "EVENT", "UNKNOWN")

# action -> (CAMEO root codes, relation kind it contributes to, default tone)
# The first block is what the LLM may emit (LLM_ACTIONS); the second block is finer actions that
# only GDELT's 3-4 digit codes produce. Both live in ACTIONS so relations/tone work the same way.
ACTIONS = {
    "STATEMENT":  (("01",), None,          0.0),
    "APPEAL":     (("02",), "COOPERATIVE", 1.0),
    "COOPERATE":  (("03", "04", "05", "06"), "COOPERATIVE", 4.0),
    "MEET":       (("04",), "COOPERATIVE", 3.0),
    "AGREE":      (("05", "06"), "COOPERATIVE", 5.0),
    "AID":        (("07",), "COOPERATIVE", 6.0),
    "VISIT":      (("04",), "COOPERATIVE", 2.0),
    "ACCUSE":     (("11",), "HOSTILE",    -3.0),
    "REJECT":     (("12",), "HOSTILE",    -2.0),
    "THREATEN":   (("13",), "HOSTILE",    -5.0),
    "PROTEST":    (("14",), "HOSTILE",    -3.0),
    "SANCTION":   (("16",), "HOSTILE",    -6.0),
    "COERCE":     (("17",), "HOSTILE",    -7.0),
    "ARREST":     (("17",), "HOSTILE",    -6.0),
    "ATTACK":     (("18", "19", "20"), "HOSTILE", -9.0),
    "APPOINT":    ((), "ROLE",       0.0),
    "RESIGN":     ((), "ROLE",       0.0),
    "ELECT":      ((), "ROLE",       0.0),
    "ACQUIRE":    ((), "OWNERSHIP",  0.0),
    "INVEST":     ((), "OWNERSHIP",  1.0),
    "DEPLOY":     ((), None,        -2.0),
    "DISASTER":   ((), None,         0.0),
    "OTHER":      ((), None,         0.0),
    # ── finer actions from full CAMEO codes (GDELT only) ──
    "PRAISE":              ((), "COOPERATIVE",  1.0),
    "DEFEND":              ((), "COOPERATIVE",  2.0),
    "RECOGNIZE":           ((), "COOPERATIVE",  4.0),
    "SIGN_AGREEMENT":      ((), "COOPERATIVE",  6.0),
    "NEGOTIATE":           ((), "COOPERATIVE",  3.0),
    "CALL":                ((), "COOPERATIVE",  1.0),
    "HOST":                ((), "COOPERATIVE",  2.0),
    "MEDIATE":             ((), "COOPERATIVE",  3.0),
    "TRADE_COOPERATE":     ((), "COOPERATIVE",  4.0),
    "MILITARY_COOPERATE":  ((), "COOPERATIVE",  5.0),
    "MILITARY_AID":        ((), "COOPERATIVE",  5.0),
    "ECONOMIC_AID":        ((), "COOPERATIVE",  5.0),
    "HUMANITARIAN_AID":    ((), "COOPERATIVE",  5.0),
    "EASE_SANCTIONS":      ((), "COOPERATIVE",  6.0),
    "RELEASE":             ((), "COOPERATIVE",  5.0),
    "TRUCE":               ((), "COOPERATIVE",  6.0),
    "CUT_RELATIONS":       ((), "HOSTILE",     -4.0),
    "REJECT_TRADE":        ((), "HOSTILE",     -3.0),
    "REFUSE_EASE":         ((), "HOSTILE",     -4.0),
    "THREATEN_SANCTION":   ((), "HOSTILE",     -5.0),
    "THREATEN_FORCE":      ((), "HOSTILE",     -6.0),
    "MILITARY_POSTURE":    ((), "HOSTILE",     -3.0),
    "DEPORT":              ((), "HOSTILE",     -5.0),
    "CYBER_ATTACK":        ((), "HOSTILE",     -7.0),
    "ABDUCT":              ((), "HOSTILE",     -9.0),
    "ASSASSINATION":       ((), "HOSTILE",     -9.0),
    "BOMBING":             ((), "HOSTILE",     -9.0),
    "ARMED_ATTACK":        ((), "HOSTILE",     -9.0),
    "AIRSTRIKE":           ((), "HOSTILE",     -9.0),
    "BLOCKADE":            ((), "HOSTILE",     -8.0),
    "OCCUPY":              ((), "HOSTILE",     -8.0),
    "VIOLATE_CEASEFIRE":   ((), "HOSTILE",     -7.0),
    "MASS_VIOLENCE":       ((), "HOSTILE",    -10.0),
}
ACTION_NAMES = tuple(ACTIONS)
LLM_ACTIONS = ACTION_NAMES[:23]        # the vocabulary the extraction prompt offers

# What an event is *about*. Relations are summarised per (kind, topic) so a card can say
# "diplomacy (26) · military (19)" instead of "27 cooperative · 19 hostile".
TOPICS = ("nuclear", "sanctions", "trade", "territory", "military", "security", "diplomacy",
          "detention", "migration", "energy", "technology", "cyber", "elections", "human_rights",
          "humanitarian", "economy", "health", "environment", "crime", "other")

# CAMEO root code -> action (coarse fallback when no finer prefix matches)
CAMEO_ROOT_TO_ACTION = {
    "01": "STATEMENT", "02": "APPEAL", "03": "COOPERATE", "04": "MEET", "05": "AGREE", "06": "AGREE",
    "07": "AID", "08": "AGREE", "09": "STATEMENT", "10": "APPEAL", "11": "ACCUSE", "12": "REJECT",
    "13": "THREATEN", "14": "PROTEST", "15": "DEPLOY", "16": "SANCTION", "17": "COERCE",
    "18": "ATTACK", "19": "ATTACK", "20": "ATTACK",
}
CAMEO_ROOT_TOPIC = {
    "01": "other", "02": "diplomacy", "03": "diplomacy", "04": "diplomacy", "05": "diplomacy",
    "06": "economy", "07": "humanitarian", "08": "diplomacy", "09": "crime", "10": "diplomacy",
    "11": "diplomacy", "12": "diplomacy", "13": "security", "14": "human_rights", "15": "military",
    "16": "sanctions", "17": "security", "18": "security", "19": "military", "20": "human_rights",
}

# Full CAMEO code prefix -> (action, topic, label). Longest matching prefix wins.
# Labels are CAMEO's own wording so the evidence panel can say "coded by GDELT as 051 praise or endorse".
CAMEO_CODE_TO_ACTION = {
    "036":  ("NEGOTIATE", "diplomacy", "express intent to meet or negotiate"),
    "037":  ("NEGOTIATE", "diplomacy", "express intent to settle dispute"),
    "039":  ("NEGOTIATE", "military", "express intent to de-escalate military engagement"),
    "041":  ("CALL", "diplomacy", "discuss by telephone"),
    "042":  ("VISIT", "diplomacy", "make a visit"),
    "043":  ("HOST", "diplomacy", "host a visit"),
    "044":  ("MEET", "diplomacy", "meet at a third location"),
    "045":  ("MEDIATE", "diplomacy", "mediate"),
    "046":  ("NEGOTIATE", "diplomacy", "engage in negotiation"),
    "051":  ("PRAISE", "diplomacy", "praise or endorse"),
    "052":  ("DEFEND", "diplomacy", "defend verbally"),
    "053":  ("DEFEND", "diplomacy", "rally support on behalf of"),
    "054":  ("RECOGNIZE", "diplomacy", "grant diplomatic recognition"),
    "057":  ("SIGN_AGREEMENT", "diplomacy", "sign formal agreement"),
    "061":  ("TRADE_COOPERATE", "trade", "cooperate economically"),
    "062":  ("MILITARY_COOPERATE", "military", "cooperate militarily"),
    "063":  ("COOPERATE", "crime", "engage in judicial cooperation"),
    "064":  ("COOPERATE", "security", "share intelligence or information"),
    "071":  ("ECONOMIC_AID", "economy", "provide economic aid"),
    "072":  ("MILITARY_AID", "military", "provide military aid"),
    "073":  ("HUMANITARIAN_AID", "humanitarian", "provide humanitarian aid"),
    "074":  ("MILITARY_AID", "military", "provide military protection or peacekeeping"),
    "075":  ("AID", "migration", "grant asylum"),
    "0811": ("EASE_SANCTIONS", "human_rights", "ease restrictions on political freedoms"),
    "0841": ("RELEASE", "detention", "return or release persons"),
    "0842": ("RELEASE", "economy", "return or release property"),
    "085":  ("EASE_SANCTIONS", "sanctions", "ease economic sanctions, boycott or embargo"),
    "0871": ("TRUCE", "military", "declare truce or ceasefire"),
    "0872": ("TRUCE", "military", "ease military blockade"),
    "0873": ("TRUCE", "military", "demobilize armed forces"),
    "0874": ("TRUCE", "military", "retreat or surrender militarily"),
    "1121": ("ACCUSE", "crime", "accuse of crime or corruption"),
    "1122": ("ACCUSE", "human_rights", "accuse of human rights abuses"),
    "1123": ("ACCUSE", "military", "accuse of aggression"),
    "1124": ("ACCUSE", "human_rights", "accuse of war crimes"),
    "1125": ("ACCUSE", "security", "accuse of espionage or treason"),
    "1211": ("REJECT_TRADE", "trade", "reject economic cooperation"),
    "1212": ("REJECT", "military", "reject military cooperation"),
    "1231": ("REFUSE_EASE", "detention", "refuse to release persons"),
    "1233": ("REFUSE_EASE", "sanctions", "refuse to ease economic sanctions"),
    "1244": ("REFUSE_EASE", "military", "refuse to de-escalate military engagement"),
    "1311": ("THREATEN_SANCTION", "economy", "threaten to reduce or stop aid"),
    "1312": ("THREATEN_SANCTION", "sanctions", "threaten with sanctions, boycott or embargo"),
    "1313": ("THREATEN", "diplomacy", "threaten to reduce or break relations"),
    "134":  ("THREATEN", "diplomacy", "threaten to halt negotiations"),
    "138":  ("THREATEN_FORCE", "military", "threaten with military force"),
    "1381": ("THREATEN_FORCE", "military", "threaten blockade"),
    "1382": ("THREATEN_FORCE", "territory", "threaten occupation"),
    "1385": ("THREATEN_FORCE", "nuclear", "threaten attack with WMD"),
    "139":  ("THREATEN", "security", "give ultimatum"),
    "15":   ("MILITARY_POSTURE", "military", "exhibit force posture"),
    "155":  ("CYBER_ATTACK", "cyber", "mobilize or increase cyber-forces"),
    "161":  ("CUT_RELATIONS", "diplomacy", "reduce or break diplomatic relations"),
    "162":  ("SANCTION", "economy", "reduce or stop aid"),
    "163":  ("SANCTION", "sanctions", "impose sanctions, boycott or embargo"),
    "164":  ("CUT_RELATIONS", "diplomacy", "halt negotiations"),
    "166":  ("DEPORT", "diplomacy", "expel or withdraw"),
    "171":  ("COERCE", "economy", "seize or damage property"),
    "172":  ("COERCE", "human_rights", "impose administrative sanctions"),
    "173":  ("ARREST", "detention", "arrest, detain or charge"),
    "174":  ("DEPORT", "migration", "expel or deport individuals"),
    "175":  ("COERCE", "human_rights", "use tactics of violent repression"),
    "176":  ("CYBER_ATTACK", "cyber", "attack cybernetically"),
    "181":  ("ABDUCT", "security", "abduct, hijack or take hostage"),
    "182":  ("ATTACK", "security", "physically assault"),
    "183":  ("BOMBING", "security", "conduct suicide, car or other non-military bombing"),
    "185":  ("ASSASSINATION", "security", "attempt to assassinate"),
    "186":  ("ASSASSINATION", "security", "assassinate"),
    "190":  ("ARMED_ATTACK", "military", "use conventional military force"),
    "191":  ("BLOCKADE", "military", "impose blockade or restrict movement"),
    "192":  ("OCCUPY", "territory", "occupy territory"),
    "193":  ("ARMED_ATTACK", "military", "fight with small arms and light weapons"),
    "194":  ("ARMED_ATTACK", "military", "fight with artillery and tanks"),
    "195":  ("AIRSTRIKE", "military", "employ aerial weapons"),
    "196":  ("VIOLATE_CEASEFIRE", "military", "violate ceasefire"),
    "201":  ("MASS_VIOLENCE", "migration", "engage in mass expulsion"),
    "202":  ("MASS_VIOLENCE", "human_rights", "engage in mass killings"),
    "203":  ("MASS_VIOLENCE", "human_rights", "engage in ethnic cleansing"),
    "204":  ("MASS_VIOLENCE", "nuclear", "use weapons of mass destruction"),
}
CAMEO_ROOT_LABELS = {
    "01": "make public statement", "02": "appeal", "03": "express intent to cooperate", "04": "consult",
    "05": "engage in diplomatic cooperation", "06": "engage in material cooperation", "07": "provide aid",
    "08": "yield", "09": "investigate", "10": "demand", "11": "disapprove", "12": "reject", "13": "threaten",
    "14": "protest", "15": "exhibit force posture", "16": "reduce relations", "17": "coerce", "18": "assault",
    "19": "fight", "20": "use unconventional mass violence",
}


def cameo_action(code: str):
    """
    Full CAMEO code ("051", "1385") -> (action, topic, label). Longest matching prefix in
    CAMEO_CODE_TO_ACTION wins; otherwise the 2-digit root. None when the root is unknown.
    """
    code = (code or "").strip()
    for n in (4, 3, 2):
        hit = CAMEO_CODE_TO_ACTION.get(code[:n])
        if hit:
            return hit
    root = code[:2].zfill(2)
    action = CAMEO_ROOT_TO_ACTION.get(root)
    if not action:
        return None
    return action, CAMEO_ROOT_TOPIC.get(root, "other"), CAMEO_ROOT_LABELS.get(root, "event")


# Actions where a->b and b->a are the same event (dedup on the unordered pair)
SYMMETRIC_ACTIONS = {"MEET", "CALL", "NEGOTIATE", "SIGN_AGREEMENT", "COOPERATE", "AGREE", "TRUCE",
                     "TRADE_COOPERATE", "MILITARY_COOPERATE"}

# GDELT actor type codes that mean "the state acting": government, military, legislature,
# intelligence, judiciary. A country actor with no type is a story *about* a place.
STATE_ACTOR_TYPES = {"GOV", "MIL", "LEG", "SPY", "JUD"}

# GDELT country-code slots that are regions, not countries — never an actor or target
GDELT_REGION_CODES = {"EUR", "AFR", "ASA", "NMR", "SAM", "MEA", "WST", "LAM", "CRB", "SAS", "EEC",
                      "BLK", "SCN", "EAF", "WAF", "NAF", "SAF", "CAU", "CAS", "SEA", "PGS", "MDT", "BLT"}
GDELT_KNOWN_GROUPS = {"UNO": "Q1065", "NAT": "Q7184", "EEC": "Q458", "IGOEEC": "Q458", "IGOUNO": "Q1065",
                      "IGONAT": "Q7184", "OPC": "Q7795", "ARL": "Q7172", "AFU": "Q7159", "ASN": "Q7768",
                      "IMF": "Q8885", "WBK": "Q7164", "WTO": "Q7825", "GSS": "Q83184"}

# P31 classes that mean "a body of a government": as an actor or target of an event the body
# collapses to its country (the prompt's rule 5: forces, ministries, embassies → the COUNTRY).
GOVERNMENT_BODY_CLASSES = {
    "Q327333",    # government agency
    "Q192350",    # ministry
    "Q35798",     # executive branch
    "Q2659904",   # government organization
    "Q11204",     # legislature
    "Q772547",    # armed forces
    "Q61883",     # military branch
    "Q176799",    # military unit
    "Q47913",     # intelligence agency
    "Q20857065",  # agency of the United States federal government
    "Q910252",    # United States federal executive department
    "Q1063523",   # department (government)
    "Q640506",    # executive office of a head of state
    "Q4498974",   # cabinet
    "Q17102106",  # embassy
}

# GDELT actor names that are roles or generic groups (CAMEO actor dictionary), never a specific
# thing on their own. With a country code and a state type they already collapse to the country.
GDELT_GENERIC_ACTORS = {
    "air force", "army", "navy", "marines", "coast guard", "national guard", "police", "sheriff",
    "military", "soldier", "soldiers", "troops", "citizen", "citizens", "civilian", "civilians",
    "resident", "residents", "people", "public", "community", "family", "families", "child",
    "children", "woman", "women", "man", "men", "student", "students", "university", "school",
    "college", "teacher", "doctor", "nurse", "hospital", "church", "mosque", "media", "press",
    "journalist", "reporter", "lawyer", "attorney", "prosecutor", "judge", "court", "jury",
    "company", "business", "businessman", "industry", "bank", "farmer", "worker", "workers",
    "employee", "employees", "union", "labor", "protester", "protesters", "demonstrator",
    "activist", "activists", "rebel", "rebels", "militant", "militants", "terrorist", "insurgent",
    "refugee", "refugees", "migrant", "migrants", "immigrant", "voter", "voters", "candidate",
    "leader", "leaders", "official", "officials", "authorities", "government", "administration",
    "president", "prime minister", "minister", "ministry", "secretary", "senator", "senate",
    "congress", "congressman", "parliament", "legislature", "lawmaker", "lawmakers", "governor",
    "mayor", "council", "king", "queen", "prince", "princess", "royal", "chief", "commander",
    "general", "officer", "spokesman", "spokesperson", "expert", "analyst", "scientist",
    "economist", "critic", "opposition", "party", "coalition", "house", "state", "city", "town",
    "village", "province", "region", "county", "nation", "country", "world", "guard", "force",
    "forces", "group", "agency", "department", "office", "committee", "commission", "board",
}

# Continents: places, never actors or targets
CONTINENT_QIDS = {"Q15", "Q46", "Q48", "Q49", "Q18", "Q538", "Q51", "Q5401", "Q828"}

RELATION_KINDS = ("HOSTILE", "COOPERATIVE", "ROLE", "OWNERSHIP", "MEMBERSHIP", "LOCATED", "MENTIONED_WITH")

# Wikidata properties we import as static relations: P-id -> (relation kind, label, directed a->b)
WIKIDATA_RELATION_PROPERTIES = {
    "P35":  ("ROLE", "head of state", True),          # country -> person
    "P6":   ("ROLE", "head of government", True),
    "P169": ("ROLE", "chief executive officer", True),  # org -> person
    "P488": ("ROLE", "chairperson", True),
    "P39":  ("ROLE", "position held", True),          # person -> position (org/country via P642 ignored)
    "P108": ("ROLE", "employer", True),               # person -> org
    "P127": ("OWNERSHIP", "owned by", True),          # thing -> owner
    "P749": ("OWNERSHIP", "parent organization", True),
    "P355": ("OWNERSHIP", "subsidiary", True),
    "P463": ("MEMBERSHIP", "member of", True),
    "P361": ("MEMBERSHIP", "part of", True),
    "P17":  ("LOCATED", "country", True),
    "P131": ("LOCATED", "located in", True),
    "P159": ("LOCATED", "headquarters location", True),
    "P36":  ("LOCATED", "capital", True),
    "P137": ("OWNERSHIP", "operator", True),
    "P102": ("MEMBERSHIP", "member of political party", True),
}

# P31 classes we already know (saves a SPARQL walk); everything else is learned and cached
KNOWN_CLASS_KINDS = {
    "Q5": "PERSON",
    "Q3624078": "COUNTRY", "Q6256": "COUNTRY", "Q7275": "COUNTRY", "Q1489259": "COUNTRY",
    "Q515": "PLACE", "Q486972": "PLACE", "Q1549591": "PLACE", "Q5119": "PLACE", "Q1637706": "PLACE",
    "Q23442": "PLACE", "Q8502": "PLACE", "Q4022": "PLACE", "Q165": "PLACE", "Q39594": "PLACE",
    "Q82794": "PLACE", "Q10864048": "PLACE", "Q1048835": "PLACE", "Q15284": "PLACE", "Q3957": "PLACE",
    "Q43229": "ORG", "Q4830453": "ORG", "Q7278": "ORG", "Q327333": "ORG", "Q484652": "ORG",
    "Q17149090": "ORG", "Q61883": "ORG", "Q1371037": "ORG", "Q891723": "ORG", "Q783794": "ORG",
    "Q6881511": "ORG", "Q2659904": "ORG", "Q31855": "ORG", "Q7188": "ORG", "Q37726": "ORG",
    "Q2467461": "ORG", "Q748019": "ORG", "Q1616075": "ORG", "Q4438121": "ORG", "Q1058914": "ORG",
    "Q11446": "VESSEL", "Q1229765": "VESSEL", "Q2811": "VESSEL", "Q170382": "VESSEL",
    "Q11436": "AIRCRAFT", "Q15056993": "AIRCRAFT",
    "Q1656682": "EVENT", "Q198": "EVENT", "Q3839081": "EVENT", "Q2223653": "EVENT", "Q7944": "EVENT",
    "Q124490": "EVENT", "Q13418847": "EVENT", "Q1190554": "EVENT",
}

# Root classes used when walking subclass-of for an unknown P31 (checked in this order)
KIND_ROOTS = [
    ("PERSON", ("Q5",)),
    ("COUNTRY", ("Q6256", "Q3624078", "Q7275")),
    ("VESSEL", ("Q11446", "Q2811")),
    ("AIRCRAFT", ("Q11436",)),
    ("EVENT", ("Q1656682", "Q1190554")),
    ("ORG", ("Q43229",)),
    ("PLACE", ("Q2221906", "Q618123", "Q486972")),   # geographic location / geographical feature / settlement
]

# Words that must never become an entity on their own
GENERIC_STOPLIST = {
    "king", "queen", "president", "prime minister", "minister", "government", "officials", "official",
    "police", "prosecutors", "security services", "forces", "troops", "army", "navy", "military",
    "pipeline", "port", "airport", "company", "organization", "organisation", "agency", "court",
    "parliament", "senate", "congress", "ministry", "the kingdom", "the country", "the city", "people",
    "residents", "protesters", "rebels", "militants", "authorities", "investigators", "experts",
    "the coalition", "the alliance", "the group", "the firm", "the bank", "the union", "the party",
    "state media", "local media", "sources", "reports", "witnesses",
}

# "Beijing said…" — capitals / seats used as the government of a country
GOVERNMENT_SEATS = {
    "washington": "Q30", "beijing": "Q148", "moscow": "Q159", "the kremlin": "Q159", "kremlin": "Q159",
    "tehran": "Q794", "london": "Q145", "downing street": "Q145", "whitehall": "Q145", "paris": "Q142",
    "berlin": "Q183", "brussels": "Q458", "ankara": "Q43", "riyadh": "Q851", "jerusalem": "Q801",
    "tel aviv": "Q801", "pyongyang": "Q423", "seoul": "Q884", "tokyo": "Q17", "new delhi": "Q668",
    "islamabad": "Q843", "kyiv": "Q212", "kiev": "Q212", "taipei": "Q865", "canberra": "Q408",
    "ottawa": "Q16", "brasilia": "Q155", "cairo": "Q79", "damascus": "Q858", "baghdad": "Q796",
    "kabul": "Q889", "naypyidaw": "Q836", "bangkok": "Q869", "hanoi": "Q881", "jakarta": "Q252",
    "manila": "Q928", "the white house": "Q30", "the pentagon": "Q30", "capitol hill": "Q30",
}
