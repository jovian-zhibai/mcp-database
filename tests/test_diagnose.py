"""Tests for the diagnose_connection tool."""

import sqlite3


from mcp_database.adapters.sqlite import SQLiteAdapter


class TestDiagnoseConnection:
    def test_diagnose_healthy_in_memory(self):
        """Diagnose an in-memory SQLite database."""
        adapter = SQLiteAdapter(database_path=":memory:", read_only=True)
        adapter.connect()
        result = adapter.diagnose_connection()
        assert result["status"] == "connected"
        assert result["database_type"] == "sqlite"
        assert result["tables_accessible"] is True
        assert "latency_ms" in result
        adapter.disconnect()

    def test_diagnose_file_db(self, tmp_path):
        """Diagnose a file-based SQLite database."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
        adapter.connect()
        result = adapter.diagnose_connection()
        assert result["status"] == "connected"
        assert "file exists: True" in result["url"]
        assert result["server_version"] is not None
        adapter.disconnect()

    def test_diagnose_missing_file(self, tmp_path):
        """Diagnose a non-existent file."""
        adapter = SQLiteAdapter(database_path="/nonexistent/path.db", read_only=True)
        result = adapter.diagnose_connection()
        assert result["status"] == "failed"
        assert len(result["errors"]) > 0
        assert "file exists: False" in result["url"]
