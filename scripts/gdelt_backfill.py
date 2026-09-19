"""
Replay GDELT through the current agent code.

  python scripts/gdelt_backfill.py --days 7 [--keep]

Deletes events with origin = 'gdelt' (reports stay; they are matched by URL) unless --keep,
then walks GDELT's master file list for the last N days (96 export files per day), ingests each
through GdeltAgent.ingest, and rebuilds relations at the end. Resumable: files already done are
listed in data/gdelt_backfill.done.
"""
import argparse
import os
import sys
import time

sys.path.append(os.path.join(os.getcwd(), "src"))
import requests
from loguru import logger

from pia.agents.gdelt_agent import GdeltAgent
from pia.kg import relations

MASTER = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
DONE = os.path.join("data", "gdelt_backfill.done")


def export_urls(days: int):
    r = requests.get(MASTER, timeout=120)
    r.raise_for_status()
    cutoff = time.strftime("%Y%m%d", time.gmtime(time.time() - days * 86400))
    urls = []
    for line in r.text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].endswith(".export.CSV.zip"):
            stamp = parts[2].rsplit("/", 1)[-1][:8]
            if stamp >= cutoff:
                urls.append(parts[2])
    return urls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--keep", action="store_true", help="do not delete existing GDELT events first")
    args = ap.parse_args()

    agent = GdeltAgent(name="gdelt_backfill", interval_sec=10 ** 9)
    agent.setup()
    if not args.keep:
        n = agent.db.execute_query("DELETE FROM events WHERE origin = 'gdelt' RETURNING 1", fetch=True) or []
        logger.info(f"deleted {len(n)} GDELT events")
        open(DONE, "w").close()
    done = set(open(DONE).read().split()) if os.path.exists(DONE) else set()
    urls = [u for u in export_urls(args.days) if u not in done]
    logger.info(f"{len(urls)} export files to replay")
    total = 0
    for i, url in enumerate(urls, 1):
        try:
            kept = agent.ingest_url(url)
        except Exception as e:
            logger.warning(f"{url}: {e}")
            continue
        total += kept
        with open(DONE, "a") as fh:
            fh.write(url + "\n")
        if i % 8 == 0:
            logger.info(f"{i}/{len(urls)} files, {total} events kept")
    relations.rebuild(agent.db)
    logger.success(f"backfill done: {total} events kept from {len(urls)} files")
    agent.db.close()


if __name__ == "__main__":
    main()
