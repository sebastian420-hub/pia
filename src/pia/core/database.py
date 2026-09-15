import os
from contextlib import contextmanager

import psycopg2.extensions
from dotenv import load_dotenv
from loguru import logger
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

load_dotenv()

class DatabaseManager:
    """Manages thread-safe database connection pooling for PIA agents."""

    _pool = None

    def __init__(self):
        self._initialize_pool()

    def _initialize_pool(self):
        """Initializes the connection pool if it hasn't been created yet."""
        if DatabaseManager._pool is None:
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "5432")
            user = os.getenv("DB_USER", "pia")
            password = os.getenv("DB_PASSWORD", "password")
            dbname = os.getenv("DB_NAME", "pia")
            minconn = int(os.getenv("DB_MIN_CONN", "1"))
            maxconn = int(os.getenv("DB_MAX_CONN", "10"))

            try:
                DatabaseManager._pool = pool.ThreadedConnectionPool(
                    minconn, maxconn,
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=dbname
                )
                logger.info(f"Initialized ThreadedConnectionPool (min={minconn}, max={maxconn})")
            except Exception as e:
                logger.error(f"Failed to initialize connection pool: {e}")
                raise

    @contextmanager
    def get_connection(self):
        """Context manager to get a connection from the pool and return it safely."""
        conn = DatabaseManager._pool.getconn()
        try:
            yield conn
        finally:
            # Never hand a connection back to the pool with a transaction still open;
            # the next caller sets autocommit, which psycopg2 refuses mid-transaction.
            if not conn.autocommit and conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                conn.rollback()
            DatabaseManager._pool.putconn(conn)

    def execute_query(self, query, params=None, fetch=False):
        """Executes a query using a connection from the pool."""
        with self.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()

    def execute_values(self, query: str, rows, template: str = None, page_size: int = 500):
        """Bulk INSERT ... VALUES %s using psycopg2.extras.execute_values (autocommit)."""
        if not rows:
            return
        from psycopg2.extras import execute_values
        with self.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                execute_values(cur, query, rows, template=template, page_size=page_size)

    def close(self):
        """Closes all connections in the pool."""
        if DatabaseManager._pool:
            DatabaseManager._pool.closeall()
            DatabaseManager._pool = None
            logger.info("Database connection pool closed")
