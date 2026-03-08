import uuid, hashlib, sys, os, random
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def generate_crisis_backlog():
    db = DatabaseManager()
    
    scenario = "THE 2026 SILICON SHIELD COLLAPSE"
    logger.info(f"🚀 GENERATING SYNTHETIC BACKLOG: {scenario}")

    # Core Entities involved in the scenario
    entities = ["TSMC", "Nvidia", "SpaceX", "Elon Musk", "Department of Defense", "Kremlin", "Vladimir Putin", "Microsoft", "OpenAI", "Apple", "ASML", "Joe Biden"]
    
    # High-quality report templates (Fact-Dense)
    templates = [
        "Intelligence Update: {e1} has reported a significant logistical shift in its partnership with {e2}. Analysts believe this is a direct response to recent signals from the {e3} regarding export controls.",
        "Strategic Audit: A confidential agreement between {e1} and {e2} indicates a new focus on {e3} infrastructure protection. This move likely bypasses previous regulatory hurdles from {e4}.",
        "Geopolitical Pulse: Satellite imagery confirms that {e1} is increasing its presence near facilities operated by {e2}. This escalation follows a meeting between {e3} and high-ranking officials from {e4}.",
        "Financial Brief: {e1} has initiated a multi-billion dollar acquisition of assets formerly controlled by {e2}. This consolidation grants {e1} unprecedented leverage over the {e3} supply chain.",
        "Operational Alert: Cyber-activity traced back to {e1} has targeted the internal networks of {e2}. Experts suggest the goal was to exfiltrate proprietary data regarding {e3}'s latest project.",
        "Policy Shift: {e1} (representing the {e2}) has authorized a series of aggressive measures against {e3}, specifically citing their deep ties to {e4}.",
        "Supply Chain Intelligence: {e1} has warned that a shortage of components from {e2} will delay the rollout of {e3}'s next-generation hardware by at least six months.",
        "Confidential Memo: {e1} CEO has been seen in private discussions with {e2} regarding the deployment of {e3} technology in territories disputed by the {e4}.",
        "Technical Analysis: The latest firmware update for {e1} hardware includes hooks for {e2} surveillance, raising alarms within the {e3} and leading to a formal protest from {e4}.",
        "Strategic Realignment: Following the collapse of talks with {e1}, {e2} has pivotally aligned its long-term goals with {e3}, creating a new power bloc against {e4} interests."
    ]

    count = 100
    logger.info(f"Injecting {count} high-density reports into the engine's queue...")

    for i in range(count):
        # Pick 3-4 random entities for the report
        selected = random.sample(entities, 4)
        
        # Select a template and fill it
        template = random.choice(templates)
        report_text = template.format(e1=selected[0], e2=selected[1], e3=selected[2], e4=selected[3])
        
        # Use a consistent source name to group the simulation
        source_name = "Strategic Simulation Office (Path 1)"
        h = hashlib.sha256(f"path1_sim_{i}_{uuid.uuid4()}".encode()).hexdigest()
        
        db.execute_query("""
            INSERT INTO intelligence_records (
                source_type, source_agent, source_name, content_hash, 
                content_headline, content_summary, domain, priority
            ) VALUES ('OSINT', 'simulation_engine', %s, %s, 'Path 1: Strategic Crisis Brief', %s, 'FINANCIAL', 'HIGH')
        """, (source_name, h, report_text))

    logger.success(f"Successfully injected {count} high-quality reports. The Analyst Agents are now building the graph.")
    db.close()

if __name__ == "__main__":
    generate_crisis_backlog()