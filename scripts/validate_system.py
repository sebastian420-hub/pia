"""
Database bootstrap for PIA.

1. Creates the database if missing.
2. On a fresh database: applies database/schema/*.sql, creates the AGE graph,
   the restricted RLS role, and seeds GeoNames cities.
3. Every start: applies unapplied database/migrations/NNN_*.sql in order and
   records them in schema_migrations.

Credentials come from the environment (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME).
"""
import os
import zipfile

import psycopg2
import requests
from loguru import logger

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "pia")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "pia")
RLS_ROLE_PASSWORD = os.getenv("PIA_CLIENT_ROLE_PASSWORD", DB_PASSWORD)

SCHEMA_DIR = "database/schema"
MIGRATIONS_DIR = "database/migrations"


def connect(database: str):
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=database)


def download_data():
    txt_path = "cities15000.txt"
    if not os.path.exists(txt_path):
        logger.info("Downloading GeoNames dataset...")
        url = "https://download.geonames.org/export/dump/cities15000.zip"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open("cities.zip", 'wb') as f:
            f.write(r.content)
        with zipfile.ZipFile("cities.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
    return os.path.abspath(txt_path)


def ensure_database():
    logger.info("Step 1: DB existence check...")
    conn = connect("postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
    cur.close()
    conn.close()


def deploy_fresh_schema(cur):
    logger.info("Step 2: Full schema deployment...")
    sql_files = sorted(f for f in os.listdir(SCHEMA_DIR) if f.endswith('.sql'))
    for f_name in sql_files:
        logger.info(f"Applying: {f_name}")
        with open(os.path.join(SCHEMA_DIR, f_name), 'r', encoding='utf-8') as f:
            cur.execute(f.read())

    logger.info("Step 3: Graph initialization...")
    cur.execute("LOAD 'age'; SET search_path = public, ag_catalog; SELECT create_graph('pia_graph');")

    logger.info("Step 3.5: RLS Role Initialization...")
    try:
        cur.execute("CREATE ROLE pia_client LOGIN PASSWORD %s", (RLS_ROLE_PASSWORD,))
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO pia_client")
        cur.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pia_client")
    except Exception as e:
        logger.warning(f"Note: RLS role setup message: {e}")

    logger.info("Step 4: Data seeding...")
    data_path = download_data()
    cur.execute("CREATE TEMP TABLE t_geo (geonameid INT, name TEXT, asciiname TEXT, alternatenames TEXT, latitude FLOAT, longitude FLOAT, feature_class TEXT, feature_code TEXT, country_code TEXT, cc2 TEXT, admin1 TEXT, admin2 TEXT, admin3 TEXT, admin4 TEXT, population BIGINT, elevation TEXT, dem TEXT, timezone TEXT, modification_date DATE);")
    with open(data_path, 'r', encoding='utf-8') as f:
        cur.copy_from(f, 't_geo', sep='\t', null='')
    cur.execute("INSERT INTO entities (entity_type, name, canonical_name, aliases, description, confidence, watch_status, primary_geo) SELECT 'LOCATION', name, asciiname, string_to_array(alternatenames, ','), 'City', 0.99, 'PASSIVE', ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) FROM t_geo;")


def apply_migrations(cur):
    """Applies database/migrations/*.sql that are not yet in schema_migrations."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("SELECT version FROM schema_migrations")
    applied = {row[0] for row in cur.fetchall()}

    if not os.path.isdir(MIGRATIONS_DIR):
        return
    for f_name in sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql')):
        if f_name in applied:
            continue
        logger.info(f"Migration: {f_name}")
        with open(os.path.join(MIGRATIONS_DIR, f_name), 'r', encoding='utf-8') as f:
            cur.execute(f.read())
        cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (f_name,))
    logger.info("Migrations up to date.")


def main():
    ensure_database()

    conn = connect(DB_NAME)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.flight_tracks');")
    if cur.fetchone()[0] is not None:
        logger.info("Schema already deployed. Skipping base schema and seeding.")
    else:
        deploy_fresh_schema(cur)

    apply_migrations(cur)

    cur.close()
    conn.close()
    logger.info("Initialization complete.")


if __name__ == "__main__":
    main()
