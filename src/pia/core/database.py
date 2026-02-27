import os
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    """Manages database connections and executions for PIA agents."""
    
    def __init__(self):
        self._conn = None

    def get_connection(self):
        """Returns a singleton-style connection, fetching config from env."""
        if self._conn is None or self._conn.closed:
            # Refresh from environment every time we open a new connection
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "5432")
            user = os.getenv("DB_USER", "pia")
            password = os.getenv("DB_PASSWORD", "password")
            dbname = os.getenv("DB_NAME", "pia")

            try:
                conn_kwargs = {
                    "host": host,
                    "port": port,
                    "user": user,
                    "database": dbname
                }
                if password:
                    conn_kwargs["password"] = password
                
                self._conn = psycopg2.connect(**conn_kwargs)
                # Set autocommit to True for simple agent operations
                self._conn.autocommit = True
                logger.info(f"Connected to PIA Database: {dbname} on {host}")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
        return self._conn

    def execute_query(self, query, params=None, fetch=False):
        """Executes a query (single or multi-statement) and optionally fetches results."""
        conn = self.get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # Use psycopg2's native multi-statement support
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
            except Exception as e:
                # logger.error(f"Query execution failed: {e}")
                raise e

    def close(self):
        """Closes the connection."""
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed")
