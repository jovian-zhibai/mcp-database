"""Tests for query timeout protection."""

import sqlite3

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter


@pytest.fixture
def adapter(tmp_path):
    """Create a SQLite adapter with test data."""
    db_path = tmp_path / "timeout.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, x TEXT)")
    for i in range(5000):
        conn.execute("INSERT INTO t (x) VALUES (?)", (f"row-{i}",))
    conn.commit()
    conn.close()

    adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestQueryTimeout:
    def test_normal_query_default_timeout(self, adapter):
        """Fast queries should complete normally with default timeout."""
        result = adapter.execute_query("SELECT COUNT(*) FROM t")
        assert result.row_count == 1

    def test_normal_query_explicit_timeout(self, adapter):
        """Fast queries with long timeout should complete."""
        result = adapter.execute_query("SELECT COUNT(*) FROM t", timeout=30)
        assert result.row_count == 1

    def test_timeout_protection_triggers(self, adapter):
        """A cross-join with timeout=0.01 should trigger timeout."""
        with pytest.raises(RuntimeError, match="timed out"):
            adapter.execute_query(
                "SELECT COUNT(*) FROM t t1, t t2, t t3, t t4",
                timeout=0.01,
            )
