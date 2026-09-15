"""Keyword heuristics used by the news ingestor to pre-label records before NLP runs."""

MILITARY_WORDS = ('military', 'war', 'army', 'navy', 'missile', 'strike')
FINANCIAL_WORDS = ('market', 'bank', 'economy', 'stock', 'trade')
ESCALATION_WORDS = ('dead', 'killed', 'blast', 'critical', 'urgent', 'attack')


def classify_domain(normalized_text: str) -> str:
    """POLITICAL by default; MILITARY or FINANCIAL when their keywords appear (military wins)."""
    text = normalized_text.lower()
    if any(w in text for w in MILITARY_WORDS):
        return 'MILITARY'
    if any(w in text for w in FINANCIAL_WORDS):
        return 'FINANCIAL'
    return 'POLITICAL'


def classify_priority(normalized_text: str, mission_match: bool = False) -> str:
    """HIGH when the record matches an active mission or contains escalation words."""
    text = normalized_text.lower()
    if mission_match or any(w in text for w in ESCALATION_WORDS):
        return 'HIGH'
    return 'NORMAL'
