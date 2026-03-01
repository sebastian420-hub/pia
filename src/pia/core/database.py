import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv
from contextlib import contextmanager

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
            DatabaseManager._pool.putconn(conn)

    def execute_query(self, query, params=None, fetch=False):
        """Executes a query using a connection from the pool."""
        with self.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    cur.execute(query, params)
                    if fetch:
                        return cur.fetchall()
                except Exception as e:
                    # logger.error(f"Query execution failed: {e}")
                    raise e

    def execute_cypher(self, graph_name: str, cypher_query: str, params: dict = None):
        """
        Executes a Cypher query safely within Apache AGE.
        Automatically handles LOAD 'age' and search_path.
        """
        # Apache AGE's cypher() function requires the query to be a string.
        # We use dollar-quoting ($$...) to wrap the Cypher block.
        # The caller MUST ensure names inside the cypher_query are escaped 
        # using the _safe_cypher_name helper to prevent injection.
        setup_sql = f"LOAD 'age'; SET search_path = public, ag_catalog;"
        full_query = f"{setup_sql} SELECT * FROM cypher(%s, $$ {cypher_query} $$) as (v agtype);"
        
        return self.execute_query(full_query, (graph_name,), fetch=True)

    def close(self):
        """Closes all connections in the pool."""
        if DatabaseManager._pool:
            DatabaseManager._pool.closeall()
            DatabaseManager._pool = None
            logger.info("Database connection pool closed")
