import psycopg2

def main():
    try:
        conn = psycopg2.connect(host="localhost", user="pia", password="password", database="pia")
        cur = conn.cursor()
        
        print("--- EXTENSIONS INSTALLED ---")
        cur.execute("SELECT extname FROM pg_extension;")
        for row in cur.fetchall():
            print(f" - {row[0]}")

        print("--- SCHEMAS ---")
        cur.execute("SELECT schema_name FROM information_schema.schemata;")
        for row in cur.fetchall():
            print(f" - {row[0]}")

        print("--- TABLES IN PIA DATABASE ---")
        cur.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name;
        """)
        rows = cur.fetchall()
        if not rows:
            print("NO TABLES FOUND!")
        for row in rows:
            print(f" - {row[0]}.{row[1]}")
            
    except Exception as e:
        print(f"Failed to connect or query: {e}")

if __name__ == "__main__":
    main()
