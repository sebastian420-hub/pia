"""
The small vocabulary the whole web speaks.

Kinds  : what an entity is.
Actions: what an event is (CAMEO root codes, so GDELT maps without an LLM).
Relation kinds: what a summary between two entities means.
"""

KINDS = ("PERSON", "ORG", "COUNTRY", "PLACE", "VESSEL", "AIRCRAFT", "EVENT", "UNKNOWN")

# action -> (CAMEO root codes, relation kind it contributes to, default tone)
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
}
ACTION_NAMES = tuple(ACTIONS)

# CAMEO root code -> action (first match wins; more specific codes first)
CAMEO_ROOT_TO_ACTION = {
    "01": "STATEMENT", "02": "APPEAL", "03": "COOPERATE", "04": "MEET", "05": "AGREE", "06": "AGREE",
    "07": "AID", "08": "AGREE", "09": "STATEMENT", "10": "APPEAL", "11": "ACCUSE", "12": "REJECT",
    "13": "THREATEN", "14": "PROTEST", "15": "DEPLOY", "16": "SANCTION", "17": "COERCE",
    "18": "ATTACK", "19": "ATTACK", "20": "ATTACK",
}

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
