import uuid, hashlib, sys, os, time
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def seed_engine_with_facts():
    db = DatabaseManager()
    
    # Coordinates for key hubs
    tech_hubs = {
        "SF": (37.7749, -122.4194),
        "Austin": (30.2672, -97.7431),
        "BocaChica": (25.9973, -97.1561),
        "Washington": (38.9072, -77.0369),
        "Hsinchu": (24.7736, 121.0116),
        "Moscow": (55.7558, 37.6173)
    }
    
    logger.info("🚀 INITIALIZING ENGINE SEEDING: FEEDING CORE KNOWLEDGE BASE")
    
    # 1. Set Broad Missions to ensure priority
    db.execute_query("INSERT INTO mission_focus (category, keywords, is_active) VALUES ('GLOBAL', ARRAY['Elon Musk', 'SpaceX', 'Tesla', 'TSMC', 'Microsoft', 'Nvidia', 'Pentagon', 'Kremlin', 'Joe Biden', 'Donald Trump'], TRUE)")
    
    # 2. Define the Fact Feed (Raw intelligence statements)
    facts = [
        # Elon Musk & SpaceX
        {"agent": "osint_feeder", "source": "Bloomberg", "headline": "Elon Musk's dominance in aerospace", "summary": "Elon Musk is the founder and CEO of SpaceX. He founded the company in 2002 with the goal of reducing space transportation costs to enable the colonization of Mars.", "domain": "FINANCIAL", "geo": tech_hubs["BocaChica"]},
        {"agent": "osint_feeder", "source": "Wall Street Journal", "headline": "SpaceX secures Pentagon contracts", "summary": "SpaceX, led by Elon Musk, has been awarded a $1.8 billion contract by the U.S. Department of Defense to launch national security satellites.", "domain": "MILITARY", "geo": tech_hubs["Washington"]},
        {"agent": "osint_feeder", "source": "Reuters", "headline": "Tesla's global chip reliance", "summary": "Tesla, Inc. relies heavily on TSMC for the production of its Full Self-Driving (FSD) computer chips. Elon Musk remains the CEO of Tesla.", "domain": "FINANCIAL", "geo": tech_hubs["Austin"]},
        
        # Geopolitical & Military
        {"agent": "osint_feeder", "source": "Associated Press", "headline": "U.S. Defense Strategy Update", "summary": "The Pentagon (Department of Defense) announced a new initiative to counter Russian influence in Eastern Europe. President Joe Biden approved the strategic deployment.", "domain": "MILITARY", "geo": tech_hubs["Washington"]},
        {"agent": "osint_feeder", "source": "TASS", "headline": "Kremlin response to sanctions", "summary": "The Kremlin, representing the Russian Government, has issued a formal protest against U.S. economic sanctions. Vladimir Putin met with security advisors today.", "domain": "POLITICAL", "geo": tech_hubs["Moscow"]},
        
        # Tech Alliances
        {"agent": "osint_feeder", "source": "TechCrunch", "headline": "Nvidia and Microsoft's AI Supercluster", "summary": "Nvidia is supplying thousands of H100 GPUs to Microsoft to power their new Azure AI supercomputer in San Francisco.", "domain": "FINANCIAL", "geo": tech_hubs["SF"]},
        {"agent": "osint_feeder", "source": "Financial Times", "headline": "TSMC's critical role in AI", "summary": "TSMC, headquartered in Hsinchu, Taiwan, manufactures the advanced 3nm chips that power Nvidia's AI hardware and Apple's latest devices.", "domain": "FINANCIAL", "geo": tech_hubs["Hsinchu"]},
        
        # Politics
        {"agent": "osint_feeder", "source": "The Hill", "headline": "Biden vs Trump on Industrial Policy", "summary": "President Joe Biden and former President Donald Trump hold opposing views on the CHIPS Act, which impacts how much funding is provided to companies like TSMC and Intel.", "domain": "POLITICAL", "geo": tech_hubs["Washington"]},
        
        # X Corp
        {"agent": "osint_feeder", "source": "The Verge", "headline": "X Corp's new privacy policy", "summary": "X Corp., the social media company formerly known as Twitter, is now owned by Elon Musk. The company is headquartered in San Francisco.", "domain": "FINANCIAL", "geo": tech_hubs["SF"]}
    ]

    # 3. Inject facts into the UIR Spine
    logger.info(f"Injecting {len(facts)} strategic facts into the engine's ingestion pipe...")
    for fact in facts:
        h = hashlib.sha256(f"{fact['headline']}_{uuid.uuid4()}".encode()).hexdigest()
        db.execute_query("""
            INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo)
            VALUES ('OSINT', %s, %s, %s, %s, %s, %s, 'HIGH', ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        """, (fact["agent"], fact["source"], h, fact["headline"], fact["summary"], fact["domain"], fact["geo"][1], fact["geo"][0]))

    logger.success("Knowledge injection complete. The Analyst Agents will now build the graph.")
    db.close()

if __name__ == "__main__":
    seed_engine_with_facts()