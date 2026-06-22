"""Tests for ER diagram generation."""

import sqlite3

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter
from mcp_database.er_diagram import generate_er_diagram


@pytest.fixture
def adapter(tmp_path):
    """Create a SQLite adapter with related tables."""
    db_path = tmp_path / "er.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            department_id INTEGER,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)
    conn.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

    adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
    adapter.connect()
    yield adapter
    adapter.disconnect()


@pytest.fixture
def empty_adapter(tmp_path):
    db_path = tmp_path / "empty.db"
    sqlite3.connect(str(db_path)).close()
    adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestERDiagram:
    def test_starts_with_erDiagram(self, adapter):
        result = generate_er_diagram(adapter)
        assert result.startswith("erDiagram")

    def test_includes_all_tables(self, adapter):
        result = generate_er_diagram(adapter)
        assert "departments" in result
        assert "users" in result
        assert "orders" in result

    def test_includes_columns_with_types(self, adapter):
        result = generate_er_diagram(adapter)
        assert "INTEGER" in result
        assert "TEXT" in result
        assert "REAL" in result

    def test_includes_primary_keys(self, adapter):
        result = generate_er_diagram(adapter)
        assert "PK" in result

    def test_includes_foreign_keys(self, adapter):
        result = generate_er_diagram(adapter)
        assert "FK" in result

    def test_includes_relationships(self, adapter):
        result = generate_er_diagram(adapter)
        assert "||--o{" in result
        # Should have 2 relationships: users -> departments, orders -> users
        assert result.count("||--o{") >= 2

    def test_empty_database(self, empty_adapter):
        result = generate_er_diagram(empty_adapter)
        assert "No tables found" in result

    def test_unsupported_format(self, adapter):
        result = generate_er_diagram(adapter, format="graphviz")
        assert "Unsupported format" in result

    def test_no_duplicate_relationships(self, adapter):
        result = generate_er_diagram(adapter)
        lines = result.split("\n")
        rel_lines = [line for line in lines if "||--" in line]
        assert len(rel_lines) == len(set(rel_lines)), "Duplicate relationships found"
