#!/bin/bash
set -e

echo "--- 1. Enabling Extensions ---"
psql -U pia -d pia -f /tmp/schema/01_setup_extensions.sql

echo "--- 2. Building 6-Layer Schema ---"
psql -U pia -d pia -f /tmp/schema/02_layer1_telemetry.sql
psql -U pia -d pia -f /tmp/schema/03_layer2_uir_spine.sql
psql -U pia -d pia -f /tmp/schema/04_layer3_analytics.sql
psql -U pia -d pia -f /tmp/schema/05_layer5_knowledge_graph.sql
psql -U pia -d pia -f /tmp/schema/06_system_heartbeat.sql

echo "--- 3. Initializing Knowledge Graph ---"
psql -U pia -d pia -c "LOAD 'age'; SET search_path = ag_catalog, public; SELECT create_graph('pia_graph');"

echo "--- 4. Seeding Geographic Baseline ---"
psql -U pia -d pia -f /tmp/ingest_geonames.sql

echo "--- DATABASE INITIALIZATION COMPLETE ---"
