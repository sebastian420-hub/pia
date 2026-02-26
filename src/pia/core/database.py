import os
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    """Manages database connections and executions for PIA agents."""
    
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.user = os.getenv("DB_USER", "pia")
        self.password = os.getenv("DB_PASSWORD", "password")
        self.dbname = os.getenv("DB_NAME", "pia")
        self._conn = None

    def get_connection(self):
        """Returns a singleton-style connection."""
        if self._conn is None or self._conn.closed:
            try:
                conn_kwargs = {
                    "host": self.host,
                    "port": self.port,
                    "user": self.user,
                    "database": self.dbname
                }
                if self.password:
                    conn_kwargs["password"] = self.password
                
                self._conn = psycopg2.connect(**conn_kwargs)
                # Set autocommit to True for simple agent operations
                self._conn.autocommit = True
                logger.info(f"Connected to PIA Database: {self.dbname} on {self.host}")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
        return self._conn

    def execute_query(self, query, params=None, fetch=False):
        """Executes a query and optionally fetches results."""
        conn = self.get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise

    def close(self):
        """Closes the connection."""
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed")
