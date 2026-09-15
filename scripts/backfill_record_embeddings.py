"""
Backfills intelligence_records.embedding for records ingested before the analyst
started persisting embeddings. Safe to re-run; stops when nothing is left.

    python scripts/backfill_record_embeddings.py [--limit 500]
"""
import argparse
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "src"))

from loguru import logger

from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager


def main(limit: int):
    db = DatabaseManager()
    nlp = NLPManager()
    rows = db.execute_query("""
        SELECT uid, content_headline, content_summary
        FROM intelligence_records
        WHERE embedding IS NULL
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,), fetch=True) or []
    logger.info(f"{len(rows)} records without embedding (batch limit {limit})")

    done = 0
    for r in rows:
        text = (r['content_summary'] or r['content_headline'] or "").strip()
        if not text:
            continue
        vec = nlp.generate_embedding(text.lower())
        if not vec:
            logger.warning(f"No embedding for {r['uid']}; stopping (check OPENROUTER_API_KEY / EMBEDDING_MODEL)")
            break
        db.execute_query("UPDATE intelligence_records SET embedding = %s::vector WHERE uid = %s", (vec, r['uid']))
        done += 1
    logger.success(f"Backfilled {done} record embeddings.")
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    main(ap.parse_args().limit)
