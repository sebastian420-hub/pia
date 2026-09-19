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

DONE = os.path.join("data", "gdelt_backfill.done")


def export_urls(days: int):
    """
    GDELT publishes one export every 15 minutes at a predictable URL, so the URLs are generated
    rather than read from masterfilelist.txt (128 MB, and a slow link stalls on it). A slot
    GDELT never published answers 404 and is skipped.
    """
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    now -= timedelta(minutes=now.minute % 15 + 15)          # the latest slot may not be out yet
    t = now - timedelta(days=days)
    urls = []
    while t <= now:
        urls.append(f"http://data.gdeltproject.org/gdeltv2/{t.strftime('%Y%m%d%H%M%S')}.export.CSV.zip")
        t += timedelta(minutes=15)
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
    # downloads run ahead of ingestion (the link is the bottleneck, the database is not)
    from concurrent.futures import ThreadPoolExecutor
    from pia.agents.gdelt_agent import fetch_export

    def get(url):
        try:
            return url, fetch_export(url), None
        except requests.exceptions.HTTPError as e:
            return url, None, ("skip" if getattr(e.response, "status_code", 0) == 404 else str(e))
        except Exception as e:
            return url, None, str(e)

    done_n = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for url, text, err in pool.map(get, urls):
            done_n += 1
            if text is None:
                if err != "skip":
                    logger.warning(f"{url}: {err}")
                continue
            try:
                kept = agent.ingest(text, url)
            except Exception as e:
                logger.warning(f"{url}: ingest failed: {e}")
                continue
            total += kept
            with open(DONE, "a") as fh:
                fh.write(url + "\n")
            if done_n % 8 == 0:
                logger.info(f"{done_n}/{len(urls)} files, {total} events kept")
    relations.rebuild(agent.db)
    logger.success(f"backfill done: {total} events kept from {len(urls)} files")
    agent.db.close()


if __name__ == "__main__":
    main()
