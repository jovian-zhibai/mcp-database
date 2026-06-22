"""Tests for the get_health() adapter method."""

import sqlite3

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter


@pytest.fixture
def adapter(tmp_path):
    """Create a SQLite adapter with sample data."""
    db_path = tmp_path / "health.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)
    """)
    conn.execute("""
        CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)
    """)
    conn.execute("INSERT INTO users (name) VALUES ('Alice')")
    conn.execute("INSERT INTO users (name) VALUES ('Bob')")
    conn.execute("INSERT INTO users (name) VALUES ('Charlie')")
    conn.execute("INSERT INTO orders (amount) VALUES (10.0)")
    conn.commit()
    conn.close()

    adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestHealth:
    def test_status_healthy(self, adapter):
        result = adapter.get_health()
        assert result["status"] == "healthy"

    def test_database_type(self, adapter):
        result = adapter.get_health()
        assert result["database_type"] == "sqlite"

    def test_tables_count(self, adapter):
        result = adapter.get_health()
        assert result["tables_count"] == 2

    def test_total_rows(self, adapter):
        result = adapter.get_health()
        assert result["total_rows"] == 4  # 3 users + 1 order

    def test_largest_tables(self, adapter):
        result = adapter.get_health()
        assert len(result["largest_tables"]) <= 5
        # users should be largest with 3 rows
        assert result["largest_tables"][0]["name"] == "users"
        assert result["largest_tables"][0]["rows"] == 3

    def test_latency_is_positive(self, adapter):
        result = adapter.get_health()
        assert result["connection_latency_ms"] >= 0

    def test_largest_tables_have_estimated_size(self, adapter):
        result = adapter.get_health()
        for entry in result["largest_tables"]:
            assert "estimated_size" in entry
            assert "KB" in entry["estimated_size"]

    def test_empty_database(self, tmp_path):
        """Health check on an empty database."""
        db_path = tmp_path / "empty.db"
        sqlite3.connect(str(db_path)).close()

        adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
        adapter.connect()
        result = adapter.get_health()
        assert result["status"] == "healthy"
        assert result["tables_count"] == 0
        assert result["total_rows"] == 0
        assert result["largest_tables"] == []
        adapter.disconnect()
