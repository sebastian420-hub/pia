"""Seed the verb catalogue (idempotent) and fill embeddings for verbs that have none."""
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger

from pia.core.database import DatabaseManager
from pia.kg.verbs import VerbCatalogue


def main():
    db = DatabaseManager()
    try:
        embed = None
        if os.getenv("OPENROUTER_API_KEY"):
            from pia.core.nlp import NLPManager
            embed = NLPManager().generate_embedding
        cat = VerbCatalogue(db, embed=embed)
        n = cat.seed()
        e = cat.embed_missing(limit=500)
        logger.success(f"verbs seeded: {n} new, {len(cat._by_phrase)} total, {e} embeddings written")
    finally:
        db.close()


if __name__ == "__main__":
    main()
