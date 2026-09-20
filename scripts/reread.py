"""Re-read one or more reports with the current prompt: drop their article-read events and queue them again.

    python scripts/reread.py <uid> [<uid> …]
    python scripts/reread.py --headline "Ed Sheeran"        # every report whose headline matches
"""
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger

from pia.core.database import DatabaseManager


def main(args):
    db = DatabaseManager()
    try:
        if args and args[0] == "--headline":
            rows = db.execute_query("SELECT uid FROM intelligence_records WHERE content_headline ILIKE %s AND content_raw IS NOT NULL",
                                    (f"%{args[1]}%",), fetch=True) or []
            uids = [str(r["uid"]) for r in rows]
        else:
            uids = args
        for uid in uids:
            n = db.execute_query("DELETE FROM events WHERE report_uid = %s AND origin = 'llm' RETURNING 1", (uid,), fetch=True) or []
            db.execute_query("DELETE FROM mentions WHERE report_uid = %s", (uid,))
            db.execute_query("""
                INSERT INTO analysis_queue (uir_uid, trigger_type, priority, status)
                SELECT %s, 'REREAD', 'HIGH', 'PENDING'
                WHERE NOT EXISTS (SELECT 1 FROM analysis_queue WHERE uir_uid = %s AND status IN ('PENDING','PROCESSING'))
            """, (uid, uid))
            logger.info(f"{uid}: {len(n)} events dropped, queued")
        logger.success(f"{len(uids)} reports queued for re-reading")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
