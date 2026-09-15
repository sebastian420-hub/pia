import os
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager, parse_llm_json

class EnrichmentAgent(BaseAgent):
    """
    Entity profile enrichment.

    Asks an LLM for a one-line description and aliases of low-confidence entities.
    The LLM is not a ground-truth source: the result is stored with
    metadata.enrichment_source = 'llm' and confidence ENRICHED_CONFIDENCE, not 0.8.
    Failures back off exponentially and give up after MAX_ATTEMPTS.
    """

    MAX_ATTEMPTS = int(os.getenv("ENRICH_MAX_ATTEMPTS", "5"))
    ENRICHED_CONFIDENCE = 0.5

    def setup(self):
        self.db = DatabaseManager()
        self.nlp = NLPManager()
        logger.info(f"{self.name} initialized for entity enrichment.")

    def poll(self):
        """Finds entities without a description and asks the LLM for one (with backoff)."""
        # Atomic claim of 1 entity needing enrichment
        targets = self.db.execute_query("""
            SELECT entity_id, name, entity_type, description, enrichment_attempts
            FROM entities
            WHERE (description IS NULL OR description = '')
              AND entity_type <> 'LOCATION'
              AND enrichment_attempts < %s
              AND (enrichment_next_at IS NULL OR enrichment_next_at < NOW())
            ORDER BY mention_count DESC
            LIMIT 1
        """, (self.MAX_ATTEMPTS,), fetch=True)

        if not targets:
            return

        target = targets[0]
        eid = target['entity_id']
        name = target['name']
        logger.info(f"Enriching Entity: {name} (Type: {target['entity_type']})")

        try:
            # Step 1: Use LLM to generate an 'Official' summary and identify aliases
            json_format = '{"description": "...", "aliases": ["..."], "official_type": "..."}'
            prompt = f"Provide a one-sentence official description and a list of common aliases for the entity: '{name}' ({target['entity_type']}). Return ONLY a JSON object: {json_format}"
            
            selected_model = self.nlp._get_next_model()
            enrichment_data = self.nlp.client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": "You are a Ground Truth Intelligence Agent. Provide accurate, official metadata for the given entity."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )

            data = parse_llm_json(enrichment_data.choices[0].message.content)
            aliases = [a for a in (data.get('aliases') or []) if isinstance(a, str) and a.strip()]
            description = data.get('description') if isinstance(data.get('description'), str) else None

            # Step 2: Store it, labelled as LLM-sourced (not verified ground truth)
            self.db.execute_query("""
                UPDATE entities
                SET description = COALESCE(%s, description),
                    aliases = ARRAY(SELECT DISTINCT a FROM unnest(array_cat(COALESCE(aliases, '{}'), %s::text[])) a),
                    confidence = GREATEST(confidence, %s),
                    metadata = jsonb_set(COALESCE(metadata, '{}'), '{enrichment_source}', '"llm"'),
                    enrichment_attempts = enrichment_attempts + 1,
                    last_seen = NOW()
                WHERE entity_id = %s
            """, (description, aliases, self.ENRICHED_CONFIDENCE, eid))

            logger.success(f"Enriched entity: {name} (llm, confidence {self.ENRICHED_CONFIDENCE})")

        except Exception as e:
            attempts = (target.get('enrichment_attempts') or 0) + 1
            delay_min = 2 ** attempts
            logger.error(f"Enrichment failed for {name} (attempt {attempts}/{self.MAX_ATTEMPTS}, retry in {delay_min} min): {e}")
            self.db.execute_query("""
                UPDATE entities
                SET enrichment_attempts = %s,
                    enrichment_next_at = NOW() + make_interval(mins => %s)
                WHERE entity_id = %s
            """, (attempts, delay_min, eid))

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = EnrichmentAgent(name="enrichment_hunter_v1", interval_sec=15)
    agent.run()
