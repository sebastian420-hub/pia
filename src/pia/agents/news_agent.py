import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import requests
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.core.heuristics import classify_domain, classify_priority
from pia.ingest.article import fetch_body, outlet_from_url


class NewsAgent(BaseAgent):
    """
    Polls RSS feeds and stores one report per article: outlet, published time, and the
    full article body (fetched before insert, so the analyst always sees the whole text).
    """

    RSS_FEEDS = [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.theverge.com/rss/index.xml",
    ]
    MAX_NEW_PER_POLL = 40  # body fetches are the slow part

    def setup(self):
        self.db = DatabaseManager()
        logger.info(f"{self.name} initialized database connection.")

    def poll(self):
        headers = {"User-Agent": "PIA-news-agent/1.0 (+https://github.com/sebastian420-hub/pia)"}
        budget = self.MAX_NEW_PER_POLL
        for url in self.RSS_FEEDS:
            try:
                response = requests.get(url, timeout=15, headers=headers)
                response.raise_for_status()
                budget = self.process_feed(response.content, url, budget)
            except Exception as e:
                logger.error(f"Failed to fetch or parse {url}: {e}")
            if budget <= 0:
                break

    def process_feed(self, xml_content, feed_url, budget) -> int:
        root = ET.fromstring(xml_content)
        channel = root.find('channel')
        items = channel.findall('item') if channel is not None else root.findall('{http://www.w3.org/2005/Atom}entry')
        logger.info(f"Retrieved {len(items)} items from {feed_url}.")
        for item in items:
            if budget <= 0:
                return 0
            title = html.unescape((item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title') or "").strip())
            link = (item.findtext('link') or "").strip()
            if not link:
                atom_link = item.find('{http://www.w3.org/2005/Atom}link')
                link = (atom_link.get('href') if atom_link is not None else "") or ""
            desc = item.findtext('description') or item.findtext('{http://www.w3.org/2005/Atom}summary') or ""
            pub = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published')
            if not title or not link:
                continue
            if self.ingest_article(title, link, desc, pub):
                budget -= 1
        return budget

    @staticmethod
    def _clean_blurb(desc: str) -> str:
        text = re.sub(r"<[^>]+>", " ", desc or "")
        return " ".join(html.unescape(text).split())

    @staticmethod
    def _published(pub: str):
        if not pub:
            return None
        try:
            return parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            try:
                return datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                return None

    def ingest_article(self, title: str, link: str, description: str, pub: str) -> bool:
        """Returns True when a new report was stored."""
        blurb = self._clean_blurb(description)
        normalized = (title + " " + blurb).lower().strip()
        content_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()

        if self.db.execute_query("SELECT 1 FROM intelligence_records WHERE source_url = %s OR content_hash = %s",
                                 (link, content_hash), fetch=True):
            return False

        outlet = outlet_from_url(link)
        # make sure the outlet exists as a source (unknown outlets get the default trust)
        self.db.execute_query("""
            INSERT INTO sources (source_id, label, kind, trust) VALUES (%s, %s, 'NEWS', 0.5)
            ON CONFLICT (source_id) DO NOTHING
        """, (outlet, outlet))

        body, body_status = fetch_body(link)
        text_for_rules = (normalized + " " + (body or "")[:2000]).lower()

        # mission focus
        assigned_mission, assigned_client, mission_match = None, '00000000-0000-0000-0000-000000000000', False
        for m in self.db.execute_query(
                "SELECT focus_id, keywords, target_entities, client_id FROM mission_focus WHERE is_active = TRUE", fetch=True) or []:
            targets = (m['keywords'] or []) + (m['target_entities'] or [])
            if any(t.lower() in text_for_rules for t in targets):
                assigned_mission, assigned_client, mission_match = m['focus_id'], m['client_id'], True
                break

        domain = classify_domain(text_for_rules)
        priority = classify_priority(text_for_rules, mission_match)

        self.db.execute_query("""
            INSERT INTO intelligence_records (
                source_type, source_id, source_agent, source_name, source_url, published_at, content_hash,
                content_headline, content_summary, content_raw, body_status, body_fetched_at,
                domain, priority, confidence, mission_id, client_id, language
            ) VALUES ('OSINT', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, 'en')
            ON CONFLICT (content_hash) DO NOTHING
        """, (outlet, self.name, outlet, link, self._published(pub), content_hash, title, blurb, body, body_status,
              domain, priority, 0.70 if body else 0.5, assigned_mission, assigned_client))
        logger.info(f"New report [{outlet}] body={body_status} {len(body or '')}ch: {title[:70]}{' [MISSION]' if mission_match else ''}")
        return True

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = NewsAgent(name="osint_news_v1", interval_sec=120)
    agent.run()
