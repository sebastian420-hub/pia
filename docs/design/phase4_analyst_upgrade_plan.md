# PIA Phase 4.1: Analyst Agent Upgrade (Intelligence Fusion)

## Objective
To fulfill the **Phase 2 Vision** of the PIA Design Document by upgrading the existing `AnalystAgent` from simple spatial correlation to full **Intelligence Fusion**. The upgraded agent will autonomously extract entities from news, link them to the knowledge graph, and perform cross-domain relationship inference.

---

## 1. The Consolidated Reasoning Loop
The `AnalystAgent` will now follow an expanded 5-step loop for every job in the `analysis_queue`:

1.  **Ingest:** Pull the latest Universal Intelligence Record (UIR).
2.  **Spatial reasoning:** Find the nearest seeded Cities/Locations (PostGIS).
3.  **Entity Extraction (NLP):** Use the local Kimi K2.5 LLM to identify People, Organizations, and Vessels mentioned in the UIR text.
4.  **Knowledge Resolution:** 
    *   Search the `entities` table for matching Wikidata QIDs or names.
    *   Link the UIR to the entity (`uir_refs` update).
    *   Increment the entity's `mention_count`.
5.  **Relationship Inference:** 
    *   If two entities appear together, propose an `entity_relationship` (e.g., `WORKS_FOR`, `OPERATES_IN`).
    *   Mirror the relationship into the **Apache AGE Graph**.

---

## 2. Technical Implementation

### 2.1 The NLP Bridge (`src/pia/core/nlp.py`)
A shared utility that handles the conversation with the local LLM. It enforces a strict JSON schema for extraction to ensure the data can be parsed by the agent.

### 2.2 Analyst Agent Methods (`src/pia/agents/analyst_agent.py`)
*   `extract_entities(text)`: The LLM call.
*   `resolve_entity(name)`: The database lookup.
*   `link_and_update_graph()`: The final Layer 5 write.

---

## 3. Build Sequence

### Step 1: LLM Connectivity
Add the `openai` Python library to communicate with the local Kimi API.

### Step 2: The NLP Bridge
Create the shared `NLPManager` class with a robust "Intelligence Extraction" prompt.

### Step 3: The Agent Upgrade
Implement the `extract` and `resolve` logic within the existing `AnalystAgent.poll()` method.

### Step 4: Verification (The "Triple Join")
1.  Ingest a news report about a known company (e.g., "SpaceX") in a known city (e.g., "Brownsville").
2.  **Success Condition:** 
    *   A cluster is created near the city.
    *   The "SpaceX" entity in your graph has a new `uir_ref` pointing to that news article.
    *   The `mention_count` for SpaceX increases.

---

## 4. Design Alignment Check
This plan is 100% compliant with **PIA Design v2.0 Part IV**, as it uses the existing `entities` and `entity_relationships` tables and places the responsibility on the designated `Analyst Agent`.
