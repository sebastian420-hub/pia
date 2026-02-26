import psycopg2
from datetime import datetime

try:
    conn = psycopg2.connect(
        host="localhost",
        user="pia",
        password="password",
        database="pia"
    )
    cur = conn.cursor()
    
    # Insert a dummy record to verify trigger
    cur.execute("""
        INSERT INTO intelligence_records (
            source_type, source_agent, content_headline, domain, confidence
        ) VALUES (
            'SYSTEM', 'internal_test', 'Test Heartbeat', 'NATURAL', 0.1
        ) RETURNING uid;
    """)
    uid = cur.fetchone()[0]
    conn.commit()
    print(f"Successfully inserted UIR: {uid}")
    
    # Check analysis queue
    cur.execute("SELECT queue_id FROM analysis_queue WHERE uir_uid = %s", (uid,))
    queue_id = cur.fetchone()
    if queue_id:
        print(f"HEARTBEAT VERIFIED: Analysis Job {queue_id[0]} created.")
    else:
        print("HEARTBEAT FAILED: No queue entry found.")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Internal test failed: {e}")
