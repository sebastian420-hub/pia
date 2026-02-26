import os
import subprocess
import psycopg2
from loguru import logger

def main():
    # 1. Connect to 'postgres' to ensure 'pia' database exists
    logger.info("Ensuring 'pia' database exists...")
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'pia'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE pia")
    cur.close()
    conn.close()

    # 2. Connect to 'pia' and apply EVERYTHING
    logger.info("Connecting to 'pia' for full initialization...")
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="pia")
    conn.autocommit = True
    cur = conn.cursor()

    schema_dir = "database/schema"
    schemas = [
        "01_setup_extensions.sql",
        "02_layer1_telemetry.sql",
        "03_layer2_uir_spine.sql",
        "04_layer3_analytics.sql",
        "05_layer5_knowledge_graph.sql",
        "06_system_heartbeat.sql"
    ]

    for schema in schemas:
        path = os.path.join(schema_dir, schema)
        logger.info(f"Applying Schema: {schema}")
        with open(path, 'r') as f:
            sql = f.read()
            try:
                cur.execute(sql)
            except Exception as e:
                logger.warning(f"Note on {schema}: {e}")

    logger.info("Finalizing Graph...")
    try:
        cur.execute("LOAD 'age'; SET search_path = ag_catalog, public; SELECT create_graph('pia_graph');")
    except Exception as e:
        logger.warning(f"Graph check: {e}")

    cur.close()
    conn.close()

    # 3. RUN E2E TEST
    logger.info("Running E2E Test Suite...")
    # Use explicit PYTHONPATH to ensure src is found
    subprocess.run("export PYTHONPATH=/app/src && pytest tests/integration/test_signal_path.py -v -s", shell=True)

if __name__ == "__main__":
    main()
