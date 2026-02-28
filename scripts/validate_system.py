import os
import subprocess
import psycopg2
import requests
import zipfile
from loguru import logger

def download_data():
    txt_path = "cities15000.txt"
    if not os.path.exists(txt_path):
        logger.info("Downloading GeoNames dataset...")
        url = "https://download.geonames.org/export/dump/cities15000.zip"
        r = requests.get(url)
        with open("cities.zip", 'wb') as f:
            f.write(r.content)
        with zipfile.ZipFile("cities.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
    return os.path.abspath(txt_path)

def main():
    # 1. Ensure 'pia' database exists
    logger.info("Step 1: DB existence check...")
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'pia'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE pia")
    cur.close()
    conn.close()

    # 2. Initialization session
    logger.info("Step 2: Full schema deployment...")
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="pia")
    conn.autocommit = True
    cur = conn.cursor()

    # Apply ALL SQL files in one session
    schema_dir = "database/schema"
    
    cur.execute("SELECT to_regclass('public.flight_tracks');")
    if cur.fetchone()[0] is not None:
        logger.info("Schema already deployed. Skipping schema and seeding.")
    else:
        sql_files = [
            "01_setup_extensions.sql",
            "02_layer1_telemetry.sql",
            "03_layer2_uir_spine.sql",
            "04_layer3_analytics.sql",
            "05_layer5_knowledge_graph.sql",
            "06_system_heartbeat.sql"
        ]

        for f_name in sql_files:
            logger.info(f"Applying: {f_name}")
            with open(os.path.join(schema_dir, f_name), 'r') as f:
                cur.execute(f.read())

        logger.info("Step 3: Graph initialization...")
        cur.execute("LOAD 'age'; SET search_path = public, ag_catalog; SELECT create_graph('pia_graph');")

        logger.info("Step 4: Data seeding...")
        data_path = download_data()
        cur.execute("CREATE TEMP TABLE t_geo (geonameid INT, name TEXT, asciiname TEXT, alternatenames TEXT, latitude FLOAT, longitude FLOAT, feature_class TEXT, feature_code TEXT, country_code TEXT, cc2 TEXT, admin1 TEXT, admin2 TEXT, admin3 TEXT, admin4 TEXT, population BIGINT, elevation TEXT, dem TEXT, timezone TEXT, modification_date DATE);")
        with open(data_path, 'r', encoding='utf-8') as f:
            cur.copy_from(f, 't_geo', sep='\t', null='')
        cur.execute("INSERT INTO entities (entity_type, name, canonical_name, aliases, description, confidence, watch_status, primary_geo) SELECT 'LOCATION', name, asciiname, string_to_array(alternatenames, ','), 'City', 0.99, 'PASSIVE', ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) FROM t_geo ON CONFLICT DO NOTHING;")
    
    cur.close()
    conn.close()

    # 5. TEST
    logger.info("Initialization complete. Run E2E tests manually via 'ps.ps1 validate'.")
    # Removed subprocess.run so container exits and agents can start.

if __name__ == "__main__":
    main()
