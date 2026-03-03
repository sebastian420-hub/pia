# PIA Phase 8: Sovereign Intelligence Model (SIM)
## Specialized Fine-Tuning Design Document

**Status:** PROPOSED  
**Version:** 1.0  
**Target Architecture:** Llama-3-8B-Instruct or Mistral-7B-v0.3  

---

## 1. Vision & Objectives
The goal of Phase 8 is to replace general-purpose LLMs (OpenRouter/Gemini) with a **Sovereign Intelligence Model (SIM)**. This model is fine-tuned specifically to act as the "Analyst Swarm" within the PIA 7-layer architecture.

### Objectives:
1.  **Architecture Native:** The model should output valid SQL (PostGIS) and Cypher (Apache AGE) commands without complex system prompting.
2.  **Grounded Reasoning:** Natively incorporate "Geospatial Veto" and "Source Authority" logic into its weights.
3.  **Low Latency/Cost:** Run locally on private hardware, eliminating API dependencies and costs.
4.  **Security:** Enable air-gapped operations for classified or sensitive intelligence missions.

---

## 2. Training Data Pipeline (The "Intelligence Corpus")
We will use the existing PIA engine to harvest and generate a specialized training dataset.

### A. Data Sources:
*   **Layer 2 (UIR) Extraction Pairs:** Raw news/SIGINT text mapped to perfectly formatted JSON/UIR records.
*   **Layer 5 (Graph) Syntax Pairs:** Natural language descriptions mapped to complex Cypher `MERGE` and `MATCH` queries.
*   **Grounding Decision Logs:** Examples of successful and failed entity fusions (e.g., the Palm Beach vs. Dubai collision) to train the model on "Reflective Scepticism."

### B. Dataset Format (Instruction Tuning):
We will use the **Alpaca/ShareGPT** format:
```json
{
  "instruction": "Extract entities and relationships from this signal using PIA UIR standards.",
  "input": "[OSINT] Air Force One detected over Berlin...",
  "output": "{"entities": [...], "relationships": [...], "domain": "MILITARY", "priority": "HIGH"}"
}
```

---

## 3. Fine-Tuning Methodology (QLoRA)
To maintain world-class efficiency, we will use **4-bit Quantized Low-Rank Adaptation (QLoRA)**.

*   **Base Model:** `Llama-3-8B-Instruct` (High reasoning density).
*   **Training Infrastructure:** Single A100 or 2x RTX 4090 (24GB VRAM).
*   **Optimization:** Unsloth or Axolotl for high-speed training.
*   **Curriculum:** 
    *   **50% Extraction:** Entity/Relationship/UIR mapping.
    *   **30% Reasoning:** Grounding, Veto logic, and Source Weighting.
    *   **20% Code/Syntax:** SQL, PostGIS, and Apache AGE Cypher generation.

---

## 4. Integration Architecture (The Swap)
The model will be served locally via **vLLM** or **Ollama**, exposing an OpenAI-compatible API.

### Changes to Core:
1.  **`NLPManager.py`:** Update `base_url` to point to the local SIM endpoint.
2.  **Prompt Compression:** Remove ~1,000 tokens of "System Instructions" as the model is now "native" to our schema.
3.  **Local Inference Swarm:** Deploy SIM replicas alongside the Analyst Swarm for 100% offline reasoning.

---

## 5. Success Metrics (The "Truth" Test)
The SIM must outperform the general Gemini model on three key tests:
1.  **Zero-Shot Schema Accuracy:** Correct JSON/SQL formatting without prompts.
2.  **Veto Precision:** 100% rejection rate on "Dubai-Florida" style semantic collisions.
3.  **Context Density:** Ability to link an entity to 3+ hops in the Knowledge Graph in a single inference pass.

---

## 6. Implementation Roadmap
1.  **Step 1 (Harvesting):** Run PIA for 48 hours on a "Firehose" feed to collect 5,000+ high-quality reasoning logs.
2.  **Step 2 (Labeling):** Use a larger "Teacher" model (Gemini 1.5 Pro) to audit and clean the harvested logs.
3.  **Step 3 (Training):** Execute the QLoRA fine-tune.
4.  **Step 4 (Deployment):** Swap OpenRouter for the local SIM and run the `master_e2e_real.py` test suite.
