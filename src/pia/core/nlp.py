import os
import json
from typing import List, Dict, Optional
from openai import OpenAI
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class NLPManager:
    """
    Standardized NLP interface for the PIA. 
    Handles entity extraction and relationship inference via local LLM.
    """

    def __init__(self):
        # OpenRouter configuration (Standardized for the Brain)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = os.getenv("LLM_MODEL", "z-ai/glm-4.5-air:free")
        
        # Configure client with OpenRouter headers
        self.client = OpenAI(
            base_url=self.base_url, 
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/google/gemini-cli", # Required by OpenRouter
                "X-Title": "PIA-Core Intelligence Agent"
            }
        )
        
        # System prompt defined by Part IV of the Vision
        self.system_prompt = """
        You are a specialized Intelligence Extraction Agent for the Personal Intelligence Agency (PIA).
        Your task is to analyze raw intelligence reports and extract structured entities and their relationships.

        Return ONLY a JSON object with the following structure:
        {
            "entities": [
                {"name": "string", "type": "PERSON|ORGANIZATION|VESSEL|AIRCRAFT|INFRASTRUCTURE", "role": "string"}
            ],
            "relationships": [
                {"subject": "string", "predicate": "OWNS|WORKS_FOR|OPERATES|LOCATED_IN|AFFILIATED_WITH", "object": "string"}
            ],
            "summary": "one-sentence intelligence summary"
        }

        Rules:
        1. Be precise. If an entity is unclear, do not extract it.
        2. Normalize names (e.g., 'Boeing Corp' -> 'Boeing').
        3. Do not include any text before or after the JSON.
        """

    def extract_intelligence(self, text: str, mission_context: str = None) -> Dict:
        """
        Sends text to the local LLM and returns structured intelligence components.
        Injects optional mission focus context into the reasoning loop.
        """
        logger.debug(f"NLP: Processing intelligence extraction for text ({len(text)} chars)")
        
        dynamic_system_prompt = self.system_prompt
        if mission_context:
            dynamic_system_prompt += f"\n\nCURRENT MISSION FOCUS: {mission_context}\nPrioritize entities and relationships relevant to this mission."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": dynamic_system_prompt},
                    {"role": "user", "content": f"Analyze this intelligence report:\n\n{text}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            structured_data = json.loads(response.choices[0].message.content)
            logger.success(f"NLP: Successfully extracted {len(structured_data.get('entities', []))} entities")
            return structured_data

        except Exception as e:
            logger.error(f"NLP Extraction failed: {e}")
            # Mock data for when LLM is unavailable
            return {
                "entities": [{"name": "SpaceX", "type": "ORGANIZATION"}], 
                "relationships": [{"subject": "SpaceX", "predicate": "LOCATED_IN", "object": "Brownsville"}],
                "summary": "Mock extraction used (LLM offline)"
            }

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a 1536-dimensional vector embedding for the given text.
        Used for semantic search and entity resolution.
        """
        if not text:
            return []
            
        try:
            # We use the standard OpenAI embedding model via OpenRouter
            response = self.client.embeddings.create(
                model="openai/text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return []

    def verify_fusion(self, entity_a: Dict, entity_b: Dict) -> bool:
        """
        Acts as a logic discriminator to decide if two entities are actually the same.
        Used to prevent semantic collisions (e.g. Palm Beach vs Fairmont The Palm).
        """
        prompt = f"""
        Decide if these two entity descriptions refer to the exact same real-world object.
        
        Entity A: {json.dumps(entity_a)}
        Entity B: {json.dumps(entity_b)}
        
        Rules:
        1. Consider name, type, and geographic context.
        2. A city is NOT the same as a hotel.
        3. If they are in different countries, they are NOT the same.
        
        Return ONLY a JSON object: {{"match": true/false, "reason": "short explanation"}}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            decision = json.loads(response.choices[0].message.content)
            logger.info(f"NLP Fusion Verification: {decision.get('match')} ({decision.get('reason')})")
            return bool(decision.get('match'))
        except Exception as e:
            logger.error(f"Fusion verification failed: {e}")
            return False

if __name__ == "__main__":
    nlp = NLPManager()
    sample = "SpaceX launched a Falcon 9 rocket from Boca Chica, Texas today."
    print(json.dumps(nlp.extract_intelligence(sample), indent=2))
