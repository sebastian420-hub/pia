import json
import os
import re
import secrets
from contextlib import contextmanager

import psycopg2.extensions
from dotenv import load_dotenv
from loguru import logger
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

load_dotenv()

# Relationship labels are the one thing Cypher cannot take as a parameter,
# so they are validated against this shape (and the NLP verb allowlist) before use.
CYPHER_LABEL_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,39}$")


class CypherLabelError(ValueError):
    """Raised when a relationship label is not a safe Cypher identifier."""


def assert_safe_label(label: str) -> str:
    """Returns the label if it is a safe Cypher identifier, else raises."""
    if not isinstance(label, str) or not CYPHER_LABEL_RE.match(label):
        raise CypherLabelError(f"Unsafe Cypher label: {label!r}")
    return label


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

    def execute_cypher(self, graph_name: str, cypher_query: str, params: dict = None):
        """
        Executes a Cypher query in Apache AGE safely.

        - Data never goes into the query text: values go in `params` and are
          referenced as $name inside the Cypher text. AGE only accepts the
          parameter map through a prepared statement, hence PREPARE / EXECUTE /
          DEALLOCATE on one connection.
        - AGE requires the Cypher text to be a dollar-quoted constant, so it is
          wrapped in a tag with 128 random bits ($pia_<hex>$ ... $pia_<hex>$).
          Nothing in the text can close that quote, and the text itself carries
          no user data anyway.
        - Relationship labels cannot be parameters: validate them with
          `assert_safe_label` before formatting them into `cypher_query`.

        Returns a list of dicts with one key, 'v', holding the agtype text of each row.
        """
        if not re.fullmatch(r"[A-Za-z0-9_]+", graph_name or ""):
            raise ValueError(f"Unsafe graph name: {graph_name!r}")
        tag = f"$pia_{secrets.token_hex(16)}$"
        if tag in cypher_query:  # astronomically unlikely; refuse rather than guess
            raise ValueError("Cypher text collides with the quote tag")
        param_json = json.dumps(params or {})
        with self.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("LOAD 'age'; SET search_path = public, ag_catalog;")
                cur.execute(
                    f"PREPARE _pia_cypher(agtype) AS "
                    f"SELECT * FROM cypher('{graph_name}', {tag}{cypher_query}{tag}, $1) AS (v agtype);"
                )
                try:
                    cur.execute("EXECUTE _pia_cypher(%s::agtype);", (param_json,))
                    return cur.fetchall() if cur.description else []
                finally:
                    cur.execute("DEALLOCATE _pia_cypher;")

    @staticmethod
    def parse_agtype(value):
        """Best-effort conversion of an agtype text value to Python (maps/lists/scalars)."""
        if value is None:
            return None
        text = str(value)
        # AGE appends ::vertex / ::edge / ::path to composite values
        text = re.sub(r"::(vertex|edge|path)$", "", text.strip())
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return text

    def close(self):
        """Closes all connections in the pool."""
        if DatabaseManager._pool:
            DatabaseManager._pool.closeall()
            DatabaseManager._pool = None
            logger.info("Database connection pool closed")
