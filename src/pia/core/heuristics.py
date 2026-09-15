"""Keyword heuristics used by the news ingestor to pre-label records before NLP runs."""
import re

MILITARY_WORDS = ('military', 'war', 'wars', 'army', 'navy', 'missile', 'missiles', 'airstrike', 'airstrikes',
                  'troops', 'warship', 'drone strike', 'ceasefire', 'invasion')
FINANCIAL_WORDS = ('market', 'markets', 'bank', 'banks', 'economy', 'stock', 'stocks', 'trade', 'tariff', 'tariffs',
                   'inflation', 'investors')
ESCALATION_WORDS = ('dead', 'killed', 'blast', 'explosion', 'critical', 'urgent', 'attack', 'attacks')


def _has(words, text: str) -> bool:
    # whole words only: 'war' must not match 'hardware' or 'warning'
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def classify_domain(normalized_text: str) -> str:
    """POLITICAL by default; MILITARY or FINANCIAL when their keywords appear (military wins)."""
    text = normalized_text.lower()
    if _has(MILITARY_WORDS, text):
        return 'MILITARY'
    if _has(FINANCIAL_WORDS, text):
        return 'FINANCIAL'
    return 'POLITICAL'


def classify_priority(normalized_text: str, mission_match: bool = False) -> str:
    """HIGH when the record matches an active mission or contains escalation words."""
    text = normalized_text.lower()
    if mission_match or _has(ESCALATION_WORDS, text):
        return 'HIGH'
    return 'NORMAL'
