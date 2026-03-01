import uuid, hashlib, sys, os, time, threading
from loguru import logger
from concurrent.futures import ThreadPoolExecutor

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

class SignalStorm:
    def __init__(self):
        self.db = DatabaseManager()
        self.uids = []
        self.start_time = 0

    def setup_missions(self):
        logger.info("Setting up Mission Contention layers...")
        self.db.execute_query("UPDATE mission_focus SET is_active = FALSE") # Reset
        
        missions = [
            ('TECH', ['AI', 'Rocket', 'Semiconductor']),
            ('FINANCE', ['Market', 'Bank', 'Interest']),
            ('MILITARY', ['Naval', 'Drill', 'Deployment'])
        ]
        
        mission_map = {}
        for cat, keys in missions:
            res = self.db.execute_query(
                "INSERT INTO mission_focus (category, keywords, is_active) VALUES (%s, %s, TRUE) RETURNING focus_id",
                (cat, keys), fetch=True
            )
            mission_map[cat] = res[0]['focus_id']
        return mission_map

    def inject_record(self, data):
        """Simulates a high-velocity sensor hit."""
        h = hashlib.sha256(f"{data['headline']}_{uuid.uuid4()}".encode()).hexdigest()
        try:
            res = self.db.execute_query(
                """
                INSERT INTO intelligence_records (
                    source_type, source_agent, content_hash, content_headline, 
                    content_summary, domain, priority, geo
                ) VALUES ('OSINT', 'storm_sensor', %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                RETURNING uid
                """,
                (h, data['headline'], data['summary'], data['domain'], data['priority'], data['lon'], data['lat']),
                fetch=True
            )
            return res[0]['uid']
        except Exception as e:
            logger.error(f"Injection failed: {e}")
            return None

    def run_storm(self):
        mission_map = self.setup_missions()
        
        # 30 Diverse Records (Fuzzy naming for Entity Resolution test)
        storm_data = [
            # Fuzzy TECH
            {"headline": "Space-X Launch", "summary": "Rocket ignition at Boca.", "domain": "POLITICAL", "priority": "HIGH", "lat": 25.99, "lon": -97.15},
            {"headline": "The Musk Rocket Company", "summary": "New booster tested.", "domain": "POLITICAL", "priority": "NORMAL", "lat": 25.99, "lon": -97.15},
            {"headline": "SpaceX Corp Operations", "summary": "Flight 10 planned.", "domain": "POLITICAL", "priority": "HIGH", "lat": 25.99, "lon": -97.15},
            # FINANCE
            {"headline": "Federal Reserve Update", "summary": "Interest rates may hold.", "domain": "FINANCIAL", "priority": "NORMAL", "lat": 38.89, "lon": -77.03},
            {"headline": "Central Bank Shift", "summary": "Market volatility detected.", "domain": "FINANCIAL", "priority": "HIGH", "lat": 38.89, "lon": -77.03},
            # MILITARY
            {"headline": "Naval Drills in Baltic", "summary": "Multiple vessels spotted.", "domain": "MILITARY", "priority": "HIGH", "lat": 54.7, "lon": 18.5},
        ] * 5 # Scale to 30 records

        logger.info(f"🚀 LAUNCHING SIGNAL STORM: Injecting {len(storm_data)} concurrent records...")
        self.start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            self.uids = list(executor.map(self.inject_record, storm_data))
        
        self.uids = [u for u in self.uids if u]
        logger.info(f"Injection Complete. {len(self.uids)} UIRs in spine. Monitoring fusion...")

    def monitor_progress(self):
        max_wait = 120 # 2 minutes for deep fusion
        while time.time() - self.start_time < max_wait:
            res = self.db.execute_query(
                "SELECT status, count(*) as count FROM analysis_queue WHERE trigger_uid = ANY(%s::uuid[]) GROUP BY status",
                (self.uids,), fetch=True
            )
            
            stats = {row['status']: row['count'] for row in res}
            done = stats.get('DONE', 0)
            failed = stats.get('FAILED', 0)
            pending = stats.get('PENDING', 0) + stats.get('PROCESSING', 0)
            
            logger.info(f"Storm Progress: DONE: {done} | FAILED: {failed} | ACTIVE: {pending}")
            
            if done + failed == len(self.uids):
                break
            time.sleep(5)
        
        total_time = time.time() - self.start_time
        logger.success(f"Storm Dissipated. Total Time: {total_time:.2f}s")
        self.audit_results()

    def audit_results(self):
        logger.info("--- SYSTEM AUDIT: QUALITY OF INTELLIGENCE ---")
        
        # 1. Check Entity Fusion (Did SpaceX get merged?)
        res = self.db.execute_query(
            "SELECT name, mention_count FROM entities WHERE name ILIKE '%SpaceX%' OR name ILIKE '%Musk%'", 
            fetch=True
        )
        logger.info("Entity Resolution Audit:")
        for row in res:
            logger.info(f"   Entity: {row['name']} | Mentions: {row['mention_count']}")

        # 2. Check Mission Accuracy
        res = self.db.execute_query(
            """
            SELECT m.category, count(u.uid) as record_count 
            FROM intelligence_records u 
            JOIN mission_focus m ON u.mission_id = m.focus_id 
            WHERE u.uid = ANY(%s::uuid[])
            GROUP BY m.category
            """, (self.uids,), fetch=True
        )
        logger.info("Mission Logic Audit:")
        for row in res:
            logger.info(f"   Mission: {row['category']} | Records Captured: {row['record_count']}")

        self.db.close()

if __name__ == "__main__":
    storm = SignalStorm()
    storm.run_storm()
    storm.monitor_progress()
