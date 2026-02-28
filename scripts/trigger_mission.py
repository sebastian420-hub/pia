import psycopg2
from loguru import logger
import hashlib

def trigger_mission():
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="pia")
    conn.autocommit = True
    cur = conn.cursor()
    
    headline = "SpaceX Starship Prepares for Next Orbital Launch Attempt"
    summary = "SpaceX is readying its Starship rocket at Boca Chica for a critical mission to test heat shield integrity."
    
    normalized_content = (headline + summary).lower().strip()
    content_hash = hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
    
    # 1. Manually check mission focus
    cur.execute("SELECT focus_id FROM mission_focus WHERE is_active = TRUE AND category = 'TECH' LIMIT 1;")
    mission_id = cur.fetchone()[0]
    
    logger.info(f"Injecting SpaceX Mission Match with Mission ID: {mission_id}")
    
    cur.execute(
        """
        INSERT INTO intelligence_records (
            source_type, source_agent, source_name, source_url, content_hash,
            content_headline, content_summary, domain, priority, confidence, mission_id
        ) VALUES (
            'OSINT', 'manual_trigger', 'Test Feed', 'https://spacex.com/test', %s,
            %s, %s, 'POLITICAL', 'HIGH', 0.99, %s
        ) ON CONFLICT (content_hash) DO NOTHING;
        """,
        (content_hash, headline, summary, mission_id)
    )
    
    logger.success("SpaceX intelligence injected. Watch the Analyst Agents react.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    trigger_mission()
