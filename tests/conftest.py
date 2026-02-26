import pytest
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture(scope="session")
def db_conn():
    """Provides a connection to the test database."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "pia"),
        password=os.getenv("DB_PASSWORD", "password"),
        database=os.getenv("DB_NAME", "pia")
    )
    yield conn
    conn.close()

@pytest.fixture
def cursor(db_conn):
    """Provides a cursor for a single test."""
    cur = db_conn.cursor()
    yield cur
    db_conn.rollback()
    cur.close()
