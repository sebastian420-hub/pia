import json
from loguru import logger
from typing import Dict, Optional
import sys
import os

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager

class EnrichmentAgent(BaseAgent):
    """
    The 'Ground Truth' Hunter.
    Monitors the Knowledge Graph for new entities and enriches them with official data.
    """

    def setup(self):
        self.db = DatabaseManager()
        self.nlp = NLPManager()
        logger.info(f"{self.name} initialized for entity enrichment.")

    def poll(self):
        """Finds entities with low confidence and attempts to enrich them via LLM/Search."""
        # Atomic claim of 1 entity needing enrichment
        targets = self.db.execute_query("""
            SELECT entity_id, name, entity_type, description
            FROM entities
            WHERE confidence < 0.5
            ORDER BY mention_count DESC
            LIMIT 1
        """, fetch=True)

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
            
            enrichment_data = self.nlp.client.chat.completions.create(
                model=self.nlp.model,
                messages=[
                    {"role": "system", "content": "You are a Ground Truth Intelligence Agent. Provide accurate, official metadata for the given entity."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            data = json.loads(enrichment_data.choices[0].message.content)
            
            # Step 2: Update the Knowledge Graph with 'Hardened' data
            self.db.execute_query("""
                UPDATE entities
                SET description = %s,
                    aliases = array_cat(aliases, %s::text[]),
                    confidence = 0.8,
                    last_seen = NOW()
                WHERE entity_id = %s
            """, (data.get('description'), data.get('aliases', []), eid))
            
            logger.success(f"Hardened Entity: {name}. Confidence raised to 0.8")

        except Exception as e:
            logger.error(f"Enrichment failed for {name}: {e}")

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = EnrichmentAgent(name="enrichment_hunter_v1", interval_sec=15)
    agent.run()
