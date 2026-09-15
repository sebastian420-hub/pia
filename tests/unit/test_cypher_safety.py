"""
The graph layer must never build SQL or Cypher by string concatenation with data.
These tests drive DatabaseManager.execute_cypher against a fake connection and
inspect exactly what would be sent to PostgreSQL.
"""
import json
import re
from unittest.mock import MagicMock

import pytest

from pia.core import database as dbmod
from pia.core.database import CypherLabelError, DatabaseManager, assert_safe_label

HOSTILE_NAMES = [
    'x" }) RETURN 1 //',
    "a $$; DROP TABLE entities; --",
    'back\\slash" $$ evil',
]


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.description = [("v",)]

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [{"v": '{"ok": true}'}]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fake_db(monkeypatch):
    cursor = FakeCursor()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.autocommit = False
    conn.status = 0
    pool = MagicMock()
    pool.getconn.return_value = conn
    monkeypatch.setattr(DatabaseManager, "_pool", pool)
    db = DatabaseManager.__new__(DatabaseManager)
    return db, cursor


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_names_never_appear_in_sql_text(fake_db, name):
    db, cursor = fake_db
    db.execute_cypher("pia_graph", "MERGE (a:ENTITY {name: $name})", {"name": name})

    sql_texts = [sql for sql, _ in cursor.calls]
    assert not any(name in sql for sql in sql_texts), "raw name leaked into SQL text"
    assert not any("$$" in sql for sql in sql_texts), "plain $$ quoting must not be used"

    prepare = next(sql for sql, _ in cursor.calls if sql.startswith("PREPARE"))
    tags = re.findall(r"\$pia_[0-9a-f]{32}\$", prepare)
    assert len(tags) == 2 and tags[0] == tags[1], "cypher text must be wrapped in one random tag"
    assert ", $1) AS (v agtype)" in prepare

    execute_call = next((sql, p) for sql, p in cursor.calls if sql.startswith("EXECUTE"))
    assert json.loads(execute_call[1][0]) == {"name": name}


def test_prepared_statement_is_deallocated(fake_db):
    db, cursor = fake_db
    db.execute_cypher("pia_graph", "MATCH (n) RETURN n")
    assert cursor.calls[-1][0].startswith("DEALLOCATE")


def test_random_tag_differs_per_call(fake_db):
    db, cursor = fake_db
    query = "MATCH (a:ENTITY {name: $name}) RETURN a"
    db.execute_cypher("pia_graph", query, {"name": "SpaceX"})
    db.execute_cypher("pia_graph", query, {"name": "SpaceX"})
    prepares = [sql for sql, _ in cursor.calls if sql.startswith("PREPARE")]
    tags = [re.search(r"\$pia_[0-9a-f]{32}\$", p).group(0) for p in prepares]
    assert tags[0] != tags[1]
    assert all(query in p for p in prepares)


def test_graph_name_is_validated(fake_db):
    db, _ = fake_db
    with pytest.raises(ValueError):
        db.execute_cypher("pia'); DROP TABLE x; --", "MATCH (n) RETURN n")


@pytest.mark.parametrize("label", ["WORKS_FOR", "A", "ALLIED_WITH_2"])
def test_valid_labels_pass(label):
    assert assert_safe_label(label) == label


@pytest.mark.parametrize("label", ["", "works_for", "OWNS]->(x) DETACH DELETE", "A" * 41, None, "WITH SPACE"])
def test_bad_labels_are_rejected(label):
    with pytest.raises(CypherLabelError):
        assert_safe_label(label)


def test_parse_agtype_strips_suffix():
    assert dbmod.DatabaseManager.parse_agtype('{"name": "x", "depth": 2}::vertex') == {"name": "x", "depth": 2}
    assert dbmod.DatabaseManager.parse_agtype("not json") == "not json"
    assert dbmod.DatabaseManager.parse_agtype(None) is None
