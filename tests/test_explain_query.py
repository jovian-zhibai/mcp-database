"""Tests for the explain_query tool."""

import sqlite3

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter


@pytest.fixture
def adapter(tmp_path):
    """Create a SQLite adapter with test data."""
    db_path = tmp_path / "explain.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        )
    """)
    conn.execute("CREATE INDEX idx_users_name ON users(name)")
    conn.execute("INSERT INTO users (name, email) VALUES ('Alice', 'a@test.com')")
    conn.execute("INSERT INTO users (name, email) VALUES ('Bob', 'b@test.com')")
    conn.commit()
    conn.close()

    adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestExplainQuery:
    def test_explain_select(self, adapter):
        result = adapter.explain("SELECT * FROM users")
        assert "SCAN" in result or "SEARCH" in result or "users" in result

    def test_explain_with_filter(self, adapter):
        result = adapter.explain("SELECT * FROM users WHERE name = 'Alice'")
        assert "users" in result

    def test_explain_with_join(self, adapter):
        result = adapter.explain("SELECT * FROM users u JOIN users u2 ON u.id = u2.id")
        assert len(result) > 0
