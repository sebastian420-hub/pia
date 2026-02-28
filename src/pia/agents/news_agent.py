import requests
from loguru import logger
import xml.etree.ElementTree as ET
from datetime import datetime
import json

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class NewsAgent(BaseAgent):
    """Polls public RSS feeds for OSINT and ingests into PIA."""
    
    # We use a reliable World News RSS Feed
    RSS_FEEDS = [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.a.dj.com/public/rss/RSSWorldNews" # WSJ World News
    ]

    def setup(self):
        self.db = DatabaseManager()
        logger.info(f"{self.name} initialized database connection.")

    def poll(self):
        for url in self.RSS_FEEDS:
            logger.debug(f"{self.name} polling RSS feed: {url}")
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                self.process_feed(response.content, url)
            except Exception as e:
                logger.error(f"Failed to fetch or parse {url}: {e}")

    def process_feed(self, xml_content, source_url):
        root = ET.fromstring(xml_content)
        channel = root.find('channel')
        if channel is None:
            return
            
        items = channel.findall('item')
        logger.info(f"Retrieved {len(items)} items from {source_url}.")

        for item in items:
            title_el = item.find('title')
            link_el = item.find('link')
            desc_el = item.find('description')
            pubdate_el = item.find('pubDate')

            if title_el is None or link_el is None:
                continue

            title = title_el.text or ""
            link = link_el.text or ""
            description = desc_el.text if desc_el is not None else ""
            
            self.ingest_article(title, link, description, source_url)

    def ingest_article(self, title: str, link: str, description: str, feed_url: str):
        """Ingests a validated news article into Layer 2 (UIR) with Global Deduplication."""
        import hashlib
        
        # 1. Content Normalization and Hash (The "Fingerprint")
        # We normalize to lowercase and strip whitespace to ensure 'BBC' vs 'bbc' match.
        normalized_content = (title + description).lower().strip()
        content_hash = hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
        
        # 2. Idempotency Check (URL or Content Hash match)
        exists = self.db.execute_query(
            "SELECT 1 FROM intelligence_records WHERE source_url = %s OR content_hash = %s", 
            (link, content_hash), 
            fetch=True
        )
        if exists:
            return

        logger.info(f"New UNIQUE OSINT detected: {title}")

        # 3. Simple domain/priority heuristics
        domain = 'POLITICAL'
        lower_text = (title + description).lower()
        if any(word in lower_text for word in ['military', 'war', 'army', 'navy', 'missile', 'strike']):
            domain = 'MILITARY'
        elif any(word in lower_text for word in ['market', 'bank', 'economy', 'stock', 'trade']):
            domain = 'FINANCIAL'

        priority = 'NORMAL'
        if any(word in lower_text for word in ['dead', 'killed', 'blast', 'critical', 'urgent', 'attack']):
            priority = 'HIGH'

        # 4. Atomic Insert
        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_agent, source_name, source_url, content_hash,
                content_headline, content_summary, domain, priority, confidence
            ) VALUES (
                'OSINT', %s, %s, %s, %s,
                %s, %s, %s, %s, 0.70
            ) ON CONFLICT (content_hash) DO NOTHING;
            """,
            (
                self.name, 
                "RSS News Feed", 
                link,
                content_hash,
                title, 
                description,
                domain,
                priority
            )
        )

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = NewsAgent(name="osint_news_v1", interval_sec=120)
    agent.run()
