import re
import unicodedata

_ARTICLES = re.compile(r"^(the|a|an)\s+", re.I)
_POSSESSIVE = re.compile(r"[’']s$")
_WS = re.compile(r"\s+")


def normalize(name: str) -> str:
    """Case-, accent-, article- and punctuation-insensitive key for alias matching."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.strip().lower()
    s = _ARTICLES.sub("", s)
    s = _POSSESSIVE.sub("", s)
    s = re.sub(r"[^\w\s\-]", " ", s)
    s = _WS.sub(" ", s).strip()
    return s


def looks_generic(name: str) -> bool:
    """Lower-case single common words and role nouns are not entities."""
    raw = (name or "").strip()
    if not raw:
        return True
    norm = normalize(raw)
    from pia.kg.ontology import GENERIC_STOPLIST
    if norm in GENERIC_STOPLIST:
        return True
    # collective / role nouns as the last word: 'Gulf nations', 'government forces', 'the kingdom'
    if re.search(r"\b(nations|forces|officials|authorities|troops|militants|rebels|kingdom|coalition|allies|leaders|sources|media)$", norm):
        return True
    words = raw.split()
    # 'prosecutors', 'pipeline': one lowercase word, not an acronym
    if len(words) == 1 and raw.islower() and len(raw) > 2:
        return True
    # 'Iran's president', 'Danish prime minister': role phrases
    if re.search(r"\b(president|minister|secretary|chief|spokesman|spokesperson|leader|governor|mayor|ambassador|general|commander|ceo)\b", norm) \
            and not re.search(r"\b(ministry|office|department)\b", norm):
        return True
    return False


# corporate-form words that carry no identity: "Open Joint Stock Company Rosneft Oil Company" is Rosneft
# legal forms only: "International", "Industries", "Trading", "Holding" distinguish a subsidiary from its parent and stay
CORPORATE_FORMS = {"jsc", "pjsc", "ojsc", "cjsc", "oao", "ooo", "pao", "zao", "ao", "llc", "ltd", "limited", "company", "corporation",
                   "corp", "co", "inc", "plc", "sa", "s.a", "gmbh", "ag", "nv", "bv", "spa", "srl", "sarl", "joint", "stock", "open",
                   "public", "private", "closed", "the", "of", "and", "&", "state", "federal", "unitary", "oil", "gas"}


def bare_name(name: str) -> str:
    """The name without its corporate-form words — what people actually call the company."""
    words = [w for w in normalize(name).replace(",", " ").replace(".", " ").split() if w not in CORPORATE_FORMS]
    return " ".join(words)
