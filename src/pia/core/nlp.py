import os
import json
import random
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

    # Define global ontology of allowed verbs
    ALLOWED_VERBS_FINANCIAL = [
        "INVESTED_IN", "ACQUIRED", "SHORTING", "SUPPLIES", "LITIGATING_AGAINST", 
        "BOARD_MEMBER_OF", "AFFILIATED_WITH", "WORKS_FOR", "FINANCES", "LOBBIED_BY", 
        "FUNDED_BY", "SUED_BY", "MANUFACTURES", "REGULATES", "SUBSIDIARY_OF", "EXECUTIVE_OF"
    ]
    
    ALLOWED_VERBS_MILITARY = [
        "AT_WAR_WITH", "ATTACKED", "HOSTILE_TO", "TARGETING", "DEPLOYED_TO", 
        "COMMANDS", "SANCTIONED_BY", "ALLIED_WITH", "OPERATES", "AFFILIATED_WITH", 
        "SUPPLIED_ARMS_TO", "TRAINED_BY", "OCCUPYING", "DEFENDING", "BOMBED"
    ]
    
    ALLOWED_VERBS_GENERAL = [
        "OWNS", "WORKS_FOR", "OPERATES", "LOCATED_IN", "AFFILIATED_WITH", 
        "ALLIED_WITH", "HOSTILE_TO", "ATTACKED", "FOUNDED_BY", "BORN_IN", 
        "SPOKEN_AT", "CRITICIZED", "SUPPORTED"
    ]
    
    ALLOWED_VERBS_INVESTIGATIVE = [
        "FLEW_ON", "VISITED_RESIDENCE", "PHOTOGRAPHED_WITH", "MENTIONED_IN_TESTIMONY", 
        "EMPLOYED_BY", "FINANCED_BY", "SUBPOENAED", "ASSOCIATED_WITH", "LEGAL_COUNSEL_FOR"
    ]
    
    # Combined set of all valid verbs for strict filtering
    ALL_VALID_VERBS = set(ALLOWED_VERBS_FINANCIAL + ALLOWED_VERBS_MILITARY + ALLOWED_VERBS_GENERAL + ALLOWED_VERBS_INVESTIGATIVE)

    def __init__(self):
        # OpenRouter configuration (Standardized for the Brain)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        
        # Free Tier Model Rotation Pool to bypass strict rate limits
        self.model_pool = [
            "arcee-ai/trinity-large-preview:free",
            "stepfun/step-3.5-flash:free",
            "z-ai/glm-4.5-air:free"
        ]
        
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
                {"name": "string", "type": "PERSON|ORGANIZATION|LOCATION|VESSEL|AIRCRAFT|INFRASTRUCTURE", "role": "string"}
            ],
            "relationships": [
                {
                    "subject": "string", 
                    "predicate": "MUST BE FROM ALLOWED LIST", 
                    "object": "string",
                    "reasoning": "A one-sentence logical justification explaining exactly why these two entities are connected based ONLY on the text provided."
                }
            ],
            "summary": "one-sentence intelligence summary"
        }

        Rules:
        1. Be precise. If an entity is unclear, do not extract it.
        2. Normalize names (e.g., 'Boeing Corp' -> 'Boeing').
        3. Do not include any text before or after the JSON.
        4. COGNITIVE GUARDRAIL: If your `reasoning` for a relationship requires you to assume facts not explicitly stated in the text, DO NOT extract the relationship.
        5. ENTITY FILTER: DO NOT extract generic category names as entities (e.g., 'Vessel', 'Ship', 'Person', 'Company', 'Official', 'Organization'). Only extract specific, proper names of real-world objects or individuals.
        """

    def _get_next_model(self) -> str:
        """Returns a random model from the rotation pool to distribute load."""
        return random.choice(self.model_pool)

    def extract_intelligence(self, text: str, mission_category: str = None, mission_keywords: list = None, client_id: str = None) -> Dict:
        """
        Sends text to the local LLM and returns structured intelligence components.
        Injects dynamic prompt routing based on the client's mission category and historical feedback.
        """
        logger.debug(f"NLP: Processing intelligence extraction for text ({len(text)} chars)")
        
        dynamic_system_prompt = self.system_prompt
        
        # DYNAMIC PROMPT ROUTING & ONTOLOGY EXPANSION (The "Four Faces")
        dynamic_system_prompt += "\n\nONTOLOGY FILTER: STRICTLY EXCLUDE sports, entertainment, and pop-culture entities (e.g., 'Lionel Messi', 'Taylor Swift', 'FIFA') unless they are explicitly involved in geopolitical, financial, or military events. This is a security-focused intelligence graph."

        if mission_category == 'FINANCIAL' or mission_category == 'TECH_FINANCE':
            verbs = ", ".join(self.ALLOWED_VERBS_FINANCIAL)
            dynamic_system_prompt += f"\n\nLENS: FINANCIAL INVESTIGATION. \nPrioritize extracting venture capital investments, corporate alliances, shell companies, and key personnel (CEOs, Investors). \nALLOWED RELATIONSHIP PREDICATES: {verbs}."
        elif mission_category == 'MILITARY':
            verbs = ", ".join(self.ALLOWED_VERBS_MILITARY)
            dynamic_system_prompt += f"\n\nLENS: TACTICAL THREAT BOARD. \nPrioritize extracting military units, weapon systems, troop movements, and geopolitical alliances. \nALLOWED RELATIONSHIP PREDICATES: {verbs}."
        else:
            verbs = ", ".join(self.ALLOWED_VERBS_GENERAL)
            dynamic_system_prompt += f"\n\nLENS: GENERAL INTELLIGENCE. \nALLOWED RELATIONSHIP PREDICATES: {verbs}."
        
        dynamic_system_prompt += "\n\nCRITICAL LOGIC GUARDRAIL: If the report describes an attack, strike, bombing, or hostile conflict, you MUST NOT use ALLIED_WITH or AFFILIATED_WITH. In these cases, you must use HOSTILE_TO or ATTACKED."
        
        if mission_keywords:
            dynamic_system_prompt += f"\n\nCURRENT MISSION KEYWORDS: {', '.join(mission_keywords)}\nEnsure you extract entities related to these keywords."

        # HITL REINFORCEMENT LEARNING (Negative Few-Shot Injection)
        if client_id:
            try:
                # We need a local DB instance to query feedback
                from pia.core.database import DatabaseManager
                db = DatabaseManager()
                recent_rejections = db.execute_query("""
                    SELECT original_subject, original_predicate, original_object, human_correction 
                    FROM ai_feedback 
                    WHERE client_id = %s AND feedback_type LIKE 'REJECTED%%'
                    ORDER BY created_at DESC LIMIT 5
                """, (client_id,), fetch=True)
                
                if recent_rejections:
                    dynamic_system_prompt += "\n\nCRITICAL NEGATIVE EXAMPLES (Based on previous human feedback for this client):\nDO NOT make the following mistakes again:"
                    for rej in recent_rejections:
                        subj = rej.get('original_subject', '')
                        pred = rej.get('original_predicate', '')
                        obj = rej.get('original_object', '')
                        corr = rej.get('human_correction', '')
                        dynamic_system_prompt += f"\n- REJECTED: [{subj}] --{pred}--> [{obj}]"
                        if corr:
                            dynamic_system_prompt += f" (Reason: {corr})"
            except Exception as e:
                logger.warning(f"Could not load HITL feedback for client {client_id}: {e}")

        selected_model = self._get_next_model()
        logger.debug(f"NLP: Routing request to model: {selected_model}")

        try:
            response = self.client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": dynamic_system_prompt},
                    {"role": "user", "content": f"Analyze this intelligence report:\n\n{text}"}
                ],
                # Removed strict JSON formatting to prevent 'response_format is not supported' errors from mixed providers
                temperature=0.1,
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")

            # Clean markdown code blocks if they exist
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            structured_data = json.loads(content)
            logger.success(f"NLP: Successfully extracted {len(structured_data.get('entities', []))} entities using {selected_model}")
            return structured_data

        except Exception as e:
            logger.error(f"NLP Extraction failed with model {selected_model}: {e}")
            # Mock data for when LLM is unavailable
            return {
                "entities": [], 
                "relationships": [],
                "summary": f"Extraction failed: {str(e)}"
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
        
        selected_model = self._get_next_model()
        
        try:
            response = self.client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "user", "content": prompt}],
                # Removed strict JSON formatting to prevent 'response_format is not supported' errors from mixed providers
                temperature=0.0
            )
            
            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            decision = json.loads(content)
            logger.info(f"NLP Fusion Verification ({selected_model}): {decision.get('match')} ({decision.get('reason')})")
            return bool(decision.get('match'))
        except Exception as e:
            logger.error(f"Fusion verification failed with model {selected_model}: {e}")
            return False

if __name__ == "__main__":
    nlp = NLPManager()
    sample = "SpaceX launched a Falcon 9 rocket from Boca Chica, Texas today."
    print(json.dumps(nlp.extract_intelligence(sample), indent=2))
