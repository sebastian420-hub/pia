import uuid, sys, os, json
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager

def bootstrap_high_quality_graph():
    db = DatabaseManager()
    nlp = NLPManager()
    
    logger.info("🛡️  PHASE 1: BOOTSTRAPPING WORLD MEMORY (Golden Records)")
    
    # 1. Clear Noise
    db.execute_query("DELETE FROM entity_relationships;")
    db.execute_query("DELETE FROM analysis_queue;")
    logger.info("Cleared old graph and noise queue.")

    # 2. Define the "Legit Entities" (Organizations, Leaders, Infrastructure)
    # These represent the 'Legit/CIA style' baseline memory.
    master_nodes = [
        {"name": "Elon Musk", "type": "PERSON", "desc": "CEO of SpaceX, Tesla, and X Corp. Strategic technology influencer.", "lat": 30.2672, "lon": -97.7431, "threat": 0.3},
        {"name": "SpaceX", "type": "ORGANIZATION", "desc": "Aerospace manufacturer and satellite communications company (Starlink).", "lat": 33.9207, "lon": -118.3278, "threat": 0.2},
        {"name": "TSMC", "type": "ORGANIZATION", "desc": "Taiwan Semiconductor Manufacturing Company. World's leading advanced chip maker.", "lat": 24.7736, "lon": 121.0116, "threat": 0.4},
        {"name": "Department of Defense", "type": "ORGANIZATION", "desc": "The Pentagon. United States military headquarters.", "lat": 38.8719, "lon": -77.0563, "threat": 0.8},
        {"name": "Kremlin", "type": "INFRASTRUCTURE", "desc": "Official residence of the President of Russia and government headquarters.", "lat": 55.7520, "lon": 37.6175, "threat": 0.9},
        {"name": "Vladimir Putin", "type": "PERSON", "desc": "President of the Russian Federation.", "lat": 55.7520, "lon": 37.6175, "threat": 0.95},
        {"name": "Nvidia", "type": "ORGANIZATION", "desc": "Leading manufacturer of AI-focused GPU hardware.", "lat": 37.3541, "lon": -121.9552, "threat": 0.3},
        {"name": "Joe Biden", "type": "PERSON", "desc": "46th President of the United States.", "lat": 38.8977, "lon": -77.0365, "threat": 0.7},
        {"name": "Donald Trump", "type": "PERSON", "desc": "45th and 47th President of the United States.", "lat": 26.6771, "lon": -80.0370, "threat": 0.8},
        {"name": "Microsoft", "type": "ORGANIZATION", "desc": "Multinational technology corporation and OpenAI partner.", "lat": 47.6448, "lon": -122.1260, "threat": 0.3},
        {"name": "OpenAI", "type": "ORGANIZATION", "desc": "Artificial Intelligence research laboratory and developer of ChatGPT.", "lat": 37.7624, "lon": -122.4148, "threat": 0.4}
    ]

    for node in master_nodes:
        # Generate embedding for grounding
        emb = nlp.generate_embedding(node["name"])
        
        # Manually check for existence to handle lack of unique constraint on 'name'
        exists = db.execute_query("SELECT entity_id FROM entities WHERE name = %s LIMIT 1", (node["name"],), fetch=True)
        
        if exists:
            db.execute_query("""
                UPDATE entities 
                SET description = %s, 
                    entity_type = %s,
                    threat_score = %s,
                    watch_status = 'ACTIVE',
                    primary_geo = ST_SetSRID(ST_MakePoint(%s, %s), 4326), 
                    embedding = %s::vector
                WHERE entity_id = %s;
            """, (node["desc"], node["type"], node["threat"], node["lon"], node["lat"], emb, exists[0]['entity_id']))
        else:
            db.execute_query("""
                INSERT INTO entities (name, entity_type, description, threat_score, watch_status, primary_geo, embedding)
                VALUES (%s, %s, %s, %s, 'ACTIVE', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s::vector);
            """, (node["name"], node["type"], node["desc"], node["threat"], node["lon"], node["lat"], emb))
    
    logger.success(f"Successfully seeded {len(master_nodes)} Golden Records into engine memory.")

    logger.info("📡 PHASE 2: FEEDING HIGH-QUALITY INTELLIGENCE (Legit Data Dump)")
    
    # 3. High Quality Reports (Fact-Dense)
    # These represent the 'CIA/Legit' style event data.
    reports = [
        "Intelligence Report: SpaceX (led by Elon Musk) has entered into a strategic partnership with the Department of Defense to deploy Starlink arrays for military communications in Eastern Europe, specifically countering jamming signals detected from the Kremlin.",
        "Strategic Audit: TSMC remains the sole supplier of the high-performance AI chips required by Nvidia and Microsoft. Any escalation from the Kremlin or geopolitical shifts in the region poses a critical threat to the Nvidia supply chain.",
        "Financial Brief: Elon Musk has increased his ownership stake in X Corp and used the platform to facilitate communications between high-ranking Department of Defense officials and key personnel at Tesla.",
        "Geopolitical Pulse: President Joe Biden has signed an executive order limiting the export of Nvidia H100 GPUs to regions affiliated with the Kremlin, following reports of Vladimir Putin seeking alternative AI hardware sources via shell companies.",
        "Corporate Intelligence: Microsoft has finalized a $50 billion infrastructure deal with OpenAI to build 'Stargate', a massive AI supercomputer. OpenAI remains dependent on Microsoft Azure for all compute resources.",
        "Operational Alert: Vladimir Putin (representing the Kremlin) has authorized a series of cyber-drills targeting Department of Defense infrastructure, specifically looking for vulnerabilities in the SpaceX satellite network."
    ]

    for i, report in enumerate(reports):
        h = f"hq_report_{i}_{uuid.uuid4()}"
        db.execute_query("""
            INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority)
            VALUES ('OSINT', 'legit_data_pipeline', 'Strategic Briefing', %s, 'High Quality Intelligence Brief', %s, 'POLITICAL', 'CRITICAL')
        """, (h, report))

    logger.success("High-quality intelligence dump complete. The Analyst Swarm is now processing...")
    db.close()

if __name__ == "__main__":
    bootstrap_high_quality_graph()