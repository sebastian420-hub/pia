# PIA Phase 2: Wikidata Knowledge Graph Plan

## Objective
To bootstrap the PIA's "World Memory" by ingesting the **Wikidata5M** dataset. This phase transforms the system from a simple geographic map into a rich geopolitical model containing 5 million entities (People, Organizations, Infrastructure) and their multi-hop relationships.

---

## 1. Data Source & Selection
We will use the **Wikidata5M** dataset, a curated subset of Wikidata designed for intelligence and reasoning tasks.

### 1.1 Target Entity Types
*   **ORGANIZATION:** Corporations, NGOs, Government Agencies, Military Units.
*   **PERSON:** Political leaders, CEOs, Key influencers.
*   **INFRASTRUCTURE:** Airports, Power Plants, Strategic Ports, Bridges.
*   **EVENT:** Major historical or recurring geopolitical events.

### 1.2 The "Noise Filter"
To keep the database performant and relevant, we will only ingest entities that meet one of the following criteria:
1.  Have more than **10 Wikipedia mentions** (indicates significance).
2.  Have an associated **GPS coordinate** (Infrastructure/Orgs).
3.  Are directly related to a **Country** or **Major City**.

---

## 2. Technical Architecture

### 2.1 Ingestion Pipeline (`src/pia/ingestion/wikidata_ingestor.py`)
A dedicated Python class that handles the three-step ingestion process:
1.  **Stream:** Stream the large Wikidata5M TSV files to avoid memory exhaustion.
2.  **Transform:** Map Wikidata IDs (Q-nodes) and Properties (P-edges) to our `entities` and `entity_relationships` schema.
3.  **Bulk Load:** Use PostgreSQL `COPY` for entities, and a batch logic for relationships to ensure foreign key integrity.

### 2.2 The Apache AGE Sync
For every relationship added to the `entity_relationships` table, we will mirror it in the **Apache AGE property graph** (`pia_graph`). This enables OpenCypher queries like:
```cypher
MATCH (p:PERSON)-[:WORKS_FOR]->(o:ORGANIZATION)-[:HEADQUARTERED_IN]->(l:LOCATION)
WHERE l.name = 'London'
RETURN p.name, o.name
```

---

## 3. Implementation Sequence

### Step 1: Mapping Dictionary
Define a JSON mapping of common Wikidata Properties (e.g., `P17` -> `COUNTRY`, `P127` -> `OWNED_BY`) to our internal `relationship_type` taxonomy.

### Step 2: Entity Ingestor
Implement the `WikidataIngestor` to populate the `entities` table.
*   Generate semantic embeddings for entity descriptions to enable "Concept Search."
*   Map Wikidata coordinates to PostGIS points.

### Step 3: Relationship Ingestor
Implement the logic to populate `entity_relationships`.
*   Handle the many-to-many links between people and their organizations.

### Step 4: System Integration
Update `scripts/validate_system.py` to include a mock Wikidata ingestion check to ensure the graph stays healthy during future updates.

---

## 4. Verification (The "Intelligence Test")
The phase is complete when we can query the system:
*"Find all organizations headquartered within 50km of the recent earthquake cluster in Clearlake."*

**Success Condition:** The system returns a list of specific companies or facilities (e.g., "The Geysers Geothermal Facility") instead of just "Clearlake."
