"""
Fetches and cleans article bodies so the extractor sees the whole story, not the RSS blurb.
Respects robots.txt, identifies itself, caps size. Returns (text, status).
"""
import os
import time
import urllib.robotparser
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit

import requests
import trafilatura
from loguru import logger

USER_AGENT = os.getenv("ARTICLE_USER_AGENT", "PIA-research-bot/1.0 (+https://github.com/sebastian420-hub/pia)")
MAX_CHARS = int(os.getenv("ARTICLE_MAX_CHARS", "12000"))
TIMEOUT = int(os.getenv("ARTICLE_TIMEOUT", "20"))
_robots: Dict[str, Tuple[float, Optional[urllib.robotparser.RobotFileParser]]] = {}
PAYWALL_HINTS = ("subscribe to continue", "subscription required", "create a free account to read", "sign in to read")


def outlet_from_url(url: str) -> str:
    """'https://www.bbc.co.uk/news/…' → 'bbc.co.uk' (drops www./feeds./rss.)"""
    host = (urlsplit(url).hostname or "").lower()
    for prefix in ("www.", "feeds.", "rss.", "m.", "amp."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def robots_allow(url: str) -> bool:
    host = urlsplit(url).netloc
    now = time.time()
    cached = _robots.get(host)
    if cached and now - cached[0] < 86400:
        rp = cached[1]
    else:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"{urlsplit(url).scheme}://{host}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=10)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            elif r.status_code >= 400:
                rp = None  # no robots file → allowed
        except requests.RequestException:
            rp = None
        _robots[host] = (now, rp)
    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENT, url) and rp.can_fetch("*", url)
    except Exception:
        return True


def fetch_body(url: str) -> Tuple[Optional[str], str]:
    """Returns (clean_text or None, status in OK|ROBOTS_DENIED|PAYWALL|ERROR)."""
    if not url or not url.startswith("http"):
        return None, "ERROR"
    if not robots_allow(url):
        return None, "ROBOTS_DENIED"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"}, timeout=TIMEOUT)
        if r.status_code in (401, 402, 403):
            return None, "PAYWALL" if r.status_code != 403 else "ERROR"
        r.raise_for_status()
    except requests.RequestException as e:
        logger.debug(f"fetch failed {url}: {e}")
        return None, "ERROR"
    text = trafilatura.extract(r.text, include_comments=False, include_tables=False, favor_precision=True) or ""
    text = " ".join(text.split())
    if len(text) < 300:
        low = r.text.lower()
        if any(h in low for h in PAYWALL_HINTS):
            return None, "PAYWALL"
        return (text or None), ("OK" if text else "ERROR")
    return text[:MAX_CHARS], "OK"
