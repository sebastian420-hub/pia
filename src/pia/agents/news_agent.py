import requests
from loguru import logger
import xml.etree.ElementTree as ET
from datetime import datetime
import json

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class NewsAgent(BaseAgent):
    """Polls public RSS feeds for OSINT and ingests into PIA."""
    
    # We use reliable news sources
    RSS_FEEDS = [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.reutersagency.com/feed/?best-topics=world-news&post_type=best",
        "https://www.theverge.com/rss/index.xml" # Good for Tech focus
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
        """Ingests a validated news article into Layer 2 (UIR) with Global Deduplication and Mission Focus."""
        import hashlib
        
        # 1. Content Normalization and Hash
        normalized_content = (title + description).lower().strip()
        content_hash = hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
        
        # 2. Idempotency Check
        exists = self.db.execute_query(
            "SELECT 1 FROM intelligence_records WHERE source_url = %s OR content_hash = %s", 
            (link, content_hash), 
            fetch=True
        )
        if exists:
            return

        # 3. MISSION FOCUS CHECK (The Lens)
        active_missions = self.db.execute_query(
            "SELECT focus_id, keywords, target_entities FROM mission_focus WHERE is_active = TRUE", 
            fetch=True
        )
        
        assigned_mission = None
        mission_match = False
        
        for mission in active_missions:
            # Check keywords or entities in the content
            targets = (mission['keywords'] or []) + (mission['target_entities'] or [])
            if any(t.lower() in normalized_content for t in targets):
                assigned_mission = mission['focus_id']
                mission_match = True
                break

        logger.info(f"New UNIQUE OSINT detected: {title} {'[MISSION MATCH]' if mission_match else ''}")

        # 4. Domain and Priority heuristics
        domain = 'POLITICAL'
        lower_text = normalized_content
        if any(word in lower_text for word in ['military', 'war', 'army', 'navy', 'missile', 'strike']):
            domain = 'MILITARY'
        elif any(word in lower_text for word in ['market', 'bank', 'economy', 'stock', 'trade']):
            domain = 'FINANCIAL'

        # Auto-escalate if mission matches
        priority = 'HIGH' if mission_match else 'NORMAL'
        if any(word in lower_text for word in ['dead', 'killed', 'blast', 'critical', 'urgent', 'attack']):
            priority = 'HIGH'

        # 5. Atomic Insert
        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_agent, source_name, source_url, content_hash,
                content_headline, content_summary, domain, priority, confidence, mission_id
            ) VALUES (
                'OSINT', %s, %s, %s, %s,
                %s, %s, %s, %s, 0.70, %s
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
                priority,
                assigned_mission
            )
        )

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = NewsAgent(name="osint_news_v1", interval_sec=120)
    agent.run()
