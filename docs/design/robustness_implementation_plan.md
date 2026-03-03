# 🛡️ BURMANLABS: Enterprise Robustness & Hardening Plan

**Document Version:** 1.0
**Date:** March 2, 2026
**Subject:** Technical Implementation Plan for System Robustness (Cognitive Guardrails, Ontology Expansion, Data Decay, and Human-in-the-Loop Feedback).

---

## Overview
While the core PIA Intelligence Synthesis Engine operates effectively and dynamically routes prompts based on multi-tenant architecture, edge-case testing reveals that the "System 1" (fast-thinking) nature of the LLM can result in unverified hallucinations (e.g., inferring incorrect structural connections between co-mentioned entities). 

To achieve Tier-1 Enterprise reliability suitable for Hedge Funds and Defense Contractors, we must implement four layers of system hardening:

1.  **Cognitive Guardrails (Chain-of-Thought)**
2.  **Ontology Expansion (Targeted Vocabulary)**
3.  **Data Decay & Deletion (Information Lifespan)**
4.  **Human-in-the-Loop (HITL) Feedback Engine**

---

## Phase 1: Cognitive Guardrails & Ontology Expansion
**Goal:** Prevent the AI from making rushed, incorrect logical leaps, and give it the precise vocabulary required for different enterprise verticals.

### 1.1 The "Think Before You Speak" Upgrade (Chain-of-Thought)
Currently, the `NLPManager` requests a raw JSON output containing only entities and relationships. We will enforce a "reasoning" step.
*   **Target File:** `pia-core/src/pia/core/nlp.py`
*   **Implementation:** 
    *   Update the `system_prompt` JSON schema to require a `reasoning` key for every relationship.
    *   **Prompt Addition:** *"For every relationship you extract, you MUST provide a one-sentence `reasoning` string explaining why they are connected based strictly on the text. If your reasoning requires assumptions not present in the text, DO NOT extract the relationship."*
    *   **Benefit:** This forces the LLM to use "System 2" (slow, logical) thinking before committing a connection to the graph, heavily reducing hallucinations.

### 1.2 Expanding the Ontology (The Vocabulary Problem)
The AI is currently constrained to generic verbs (e.g., `AFFILIATED_WITH`).
*   **Target File:** `pia-core/src/pia/core/nlp.py`
*   **Implementation:** Update the `extract_intelligence` method to dynamically swap the allowed relationship predicates based on the `mission_category`.
    *   **FINANCIAL Lens:** Allow `INVESTED_IN`, `ACQUIRED`, `SHORTING`, `SUPPLIES`, `LITIGATING_AGAINST`, `BOARD_MEMBER_OF`.
    *   **MILITARY Lens:** Allow `AT_WAR_WITH`, `TARGETING`, `DEPLOYED_TO`, `COMMANDS`, `SANCTIONED_BY`, `ALLIED_WITH`.
    *   **Benefit:** The AI no longer has to "force" a bad relationship verb because it lacks the correct word.

---

## Phase 2: Information Lifespan (Decay & Delete)
**Goal:** Ensure the Knowledge Graph does not become poisoned with unverified, low-confidence rumors over time.

### 2.1 The TTL Decay Script
The `entity_relationships` table already has `confidence`, `last_confirmed`, and `still_valid` columns. We will utilize these.
*   **Target File:** Create a new automated script `pia-core/scripts/maintenance_decay.py` (to run as a cron job or background thread).
*   **Implementation logic:**
    *   **Query 1 (Decay):** Find all relationships where `confidence < 0.5` AND `last_confirmed < NOW() - INTERVAL '7 days'`. 
    *   **Action 1:** Set `still_valid = FALSE` and drop the confidence score slightly.
    *   **Query 2 (Prune):** Find all relationships where `confidence < 0.2` and delete them entirely from both the relational table and the Apache AGE Graph.
    *   **Benefit:** The system becomes "self-healing." If it makes a low-confidence guess that is never corroborated by another news source, it eventually forgets it, just like a human analyst would dismiss an unverified rumor.

---

## Phase 3: Human-in-the-Loop (HITL) Feedback Engine
**Goal:** Allow users to correct the AI, and force the AI to learn from its specific mistakes.

### 3.1 Database Schema Update
We need a place to store corrections.
*   **Target File:** Create `pia-core/database/schema/07_layer7_feedback.sql`.
*   **Implementation:**
    ```sql
    CREATE TABLE ai_feedback (
        feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        client_id UUID NOT NULL,
        relationship_id UUID REFERENCES entity_relationships(relationship_id),
        original_subject TEXT,
        original_predicate TEXT,
        original_object TEXT,
        feedback_type TEXT CHECK (feedback_type IN ('CONFIRMED', 'REJECTED_HALLUCINATION', 'REJECTED_WRONG_PREDICATE')),
        human_correction TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    ```

### 3.2 Dynamic Prompt Feedback Loop
When the AI makes a mistake, it should not make that exact same mistake again for that client.
*   **Target File:** `pia-core/src/pia/core/nlp.py`
*   **Implementation:** 
    *   Before querying the LLM, the `NLPManager` will quickly poll the `ai_feedback` table for the top 3 recent `REJECTED` items for that specific `client_id`.
    *   It will inject these into the system prompt as "Negative Few-Shot Examples."
    *   **Prompt Addition:** *"Based on previous feedback from this user, DO NOT make the following mistakes: [List of rejected relationships]."*
    *   **Benefit:** The system becomes a personalized, learning engine that adapts to the specific definitions and standards of the enterprise client using it.

---
*End of Plan. Awaiting approval to begin implementation.*