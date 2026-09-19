import os
import json
import random
from typing import List, Dict, Optional
from openai import OpenAI
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

PROJECT_URL = "https://github.com/sebastian420-hub/pia"


class ExtractionError(RuntimeError):
    """The LLM call failed or returned something that is not the expected JSON."""


def parse_llm_json(content: str) -> Dict:
    """
    Strips markdown fences and parses the JSON object an extraction prompt asked for.
    Raises ExtractionError on empty, truncated, or non-object output so callers can
    mark the job FAILED instead of silently storing nothing.
    """
    if not content or not content.strip():
        raise ExtractionError("Empty response from LLM")
    text = content.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    # Some models add prose before/after the object: keep the outermost braces.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ExtractionError(f"No JSON object in LLM output: {text[:120]!r}")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Invalid/truncated JSON from LLM: {e}") from e
    if not isinstance(data, dict):
        raise ExtractionError("LLM output is not a JSON object")
    return data


class NLPManager:
    """
    Standardized NLP interface for the PIA. 
    Handles entity extraction and relationship inference via local LLM.
    """

    def __init__(self):
        # OpenRouter configuration (Standardized for the Brain)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        
        # Model rotation pool (comma-separated LLM_MODEL_POOL, or a single LLM_MODEL).
        # Default is the free tier; expect rate limits and lower extraction quality.
        pool_env = os.getenv("LLM_MODEL_POOL") or os.getenv("LLM_MODEL") or (
            "arcee-ai/trinity-large-preview:free,"
            "stepfun/step-3.5-flash:free,"
            "z-ai/glm-4.5-air:free"
        )
        self.model_pool = [m.strip() for m in pool_env.split(",") if m.strip()]
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
        # Long document chunks (1500 chars) overflowed the old 500-token cap and
        # produced truncated JSON.
        self.max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1500"))

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY is not set; every LLM call will fail.")

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "missing-openrouter-key",
            default_headers={
                "HTTP-Referer": PROJECT_URL,
                "X-Title": "PIA-Core Intelligence Agent"
            }
        )
        
        self.system_prompt = """
You extract structured facts from one news article for a knowledge graph. Output ONLY a JSON object:

{
  "summary": "two sentences, neutral, no opinion",
  "country_context": "country the story is mainly about, or null",
  "mentions": [
    {"surface": "exact string as written", "kind": "PERSON|ORG|COUNTRY|PLACE|VESSEL|AIRCRAFT|EVENT", "role": "ACTOR|TARGET|LOCATION|MENTIONED"}
  ],
  "events": [
    {"actor": "surface from mentions", "action": "ONE OF THE ACTIONS BELOW", "target": "surface from mentions or null",
     "location": "surface from mentions or null", "date": "YYYY-MM-DD or null", "precision": "day|month",
     "topic": "ONE OF THE TOPICS BELOW", "quote": "the exact sentence from the article that states this",
     "confidence": 0.0-1.0}
  ]
}

ACTIONS: STATEMENT, APPEAL, COOPERATE, MEET, AGREE, AID, VISIT, ACCUSE, REJECT, THREATEN, PROTEST, SANCTION,
COERCE, ARREST, ATTACK, APPOINT, RESIGN, ELECT, ACQUIRE, INVEST, DEPLOY, DISASTER, OTHER

TOPICS (what the action is ABOUT, not the action itself): nuclear, sanctions, trade, territory, military,
security, diplomacy, detention, migration, energy, technology, cyber, elections, human_rights, humanitarian,
economy, health, environment, crime, other

Rules:
1. Mentions are specific named things only: people, organisations, countries, places, ships, aircraft.
   Never generic roles or groups ("the president", "officials", "protesters", "the army", "a pipeline").
2. A capital or seat used as the government ("Beijing warned", "the Kremlin said") is the COUNTRY; write the
   surface as in the text and kind COUNTRY.
3. An event needs an actor that DID something to a target. Reporting, quoting or describing is not an event.
   A journalist or outlet reporting is never an actor.
4. Prefer a directed action with a target over STATEMENT: "X accused Y" → ACCUSE with target Y;
   "X warned Y" → THREATEN; "X summoned Y's ambassador" → COERCE with target Y; "X sanctioned Y" → SANCTION.
   Use STATEMENT only when the announcement itself is the news (a policy, a decision) and there is no target.
5. When the target is a country's ship, aircraft, forces, embassy or government, the target is the COUNTRY.
6. Entertainment, sport and awards are not events for this graph: skip them (0 events).
7. Use the article's own words in "quote"; do not paraphrase. If the text does not state it, do not extract it.
8. Prefer fewer, certain events over many doubtful ones. 0 events is a valid answer.
9. Dates: use the publication date when the text says "today"/"yesterday" relative to it.
10. Topic is the subject: "US granted visas to Iranian officials for the UN" → action OTHER, topic migration;
    "talks on the nuclear programme" → topic nuclear; "strikes on a base" → topic military; tariffs → trade.
"""

    def _get_next_model(self) -> str:
        """Returns a random model from the rotation pool to distribute load."""
        return random.choice(self.model_pool)

    def extract_events(self, text: str, headline: str = "", published: str = "", outlet: str = "",
                       mission_keywords: list = None) -> Dict:
        """Full-article extraction: summary, mentions, events (see system prompt). Raises ExtractionError."""
        prompt = self.system_prompt
        if mission_keywords:
            prompt += f"\nThe agency is currently watching: {', '.join(mission_keywords)}. Do not invent mentions for them."
        user = f"OUTLET: {outlet or 'unknown'}\nPUBLISHED: {published or 'unknown'}\nHEADLINE: {headline}\n\nARTICLE:\n{text[:12000]}"
        selected_model = self._get_next_model()
        try:
            response = self.client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user}],
                temperature=0.1,
                max_tokens=self.max_output_tokens,
            )
        except Exception as e:
            raise ExtractionError(f"LLM call failed ({selected_model}): {e}") from e
        data = parse_llm_json(response.choices[0].message.content)
        data.setdefault("mentions", [])
        data.setdefault("events", [])
        data["mentions"] = [m for m in data["mentions"] if isinstance(m, dict) and m.get("surface")]
        data["events"] = [e for e in data["events"] if isinstance(e, dict) and e.get("actor") and e.get("action")]
        logger.success(f"NLP: {len(data['mentions'])} mentions, {len(data['events'])} events ({selected_model})")
        return data

    def choose_candidate(self, surface: str, context: dict, candidates: List[Dict]) -> Optional[int]:
        """Tie-break for identity resolution: returns the index of the right candidate, or None."""
        lines = "\n".join(
            f"{i}. {c['qid']} — {c.get('label')} — {c.get('description') or 'no description'}" for i, c in enumerate(candidates))
        prompt = f"""An article mentions "{surface}". Which of these Wikidata items is it?
Article headline: {context.get('headline', '')}
Country context: {context.get('country_qid') or context.get('country_context') or 'unknown'}
Sentence: {context.get('sentence', '')}

Candidates:
{lines}

Answer ONLY with JSON: {{"index": <number>}} or {{"index": null}} if none of them fits."""
        try:
            response = self.client.chat.completions.create(
                model=self._get_next_model(), messages=[{"role": "user", "content": prompt}], temperature=0.0, max_tokens=50)
            data = parse_llm_json(response.choices[0].message.content)
            idx = data.get("index")
            return int(idx) if isinstance(idx, (int, float)) else None
        except Exception as e:
            logger.warning(f"choose_candidate failed: {e}")
            return None

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
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return []
