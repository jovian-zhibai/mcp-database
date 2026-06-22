"""Tests for schema_diff.py — cross-database schema comparison."""

import sqlite3

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter
from mcp_database.schema_diff import diff_schemas


@pytest.fixture
def source_db(tmp_path):
    """Create a source SQLite database with 3 tables."""
    db_path = tmp_path / "source.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL
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
    return adapter


@pytest.fixture
def target_db(tmp_path):
    """Create a target SQLite database with modified schemas."""
    db_path = tmp_path / "target.db"
    conn = sqlite3.connect(str(db_path))
    # users: has an extra column 'avatar', missing 'legacy_id' (not in source anyway)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email VARCHAR(255) NOT NULL,
            age INTEGER DEFAULT 0,
            avatar TEXT
        )
    """)
    # products: identical to source
    conn.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL
        )
    """)
    # orders: missing (removed)
    # audit_log: only in target
    conn.execute("""
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY,
            action TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
    adapter.connect()
    return adapter


class TestSchemaDiff:
    def test_tables_only_in_source(self, source_db, target_db):
        result = diff_schemas(source_db, target_db)
        assert "orders" in result["tables_only_in_source"]

    def test_tables_only_in_target(self, source_db, target_db):
        result = diff_schemas(source_db, target_db)
        assert "audit_log" in result["tables_only_in_target"]

    def test_identical_tables(self, source_db, target_db):
        result = diff_schemas(source_db, target_db)
        assert "products" in result["identical_tables"]

    def test_modified_table_columns_added(self, source_db, target_db):
        result = diff_schemas(source_db, target_db)
        assert "users" in result["modified_tables"]
        cols_added = result["modified_tables"]["users"].get("columns_added", [])
        col_names = [c["name"] for c in cols_added]
        assert "avatar" in col_names

    def test_modified_table_columns_modified(self, source_db, target_db):
        result = diff_schemas(source_db, target_db)
        assert "users" in result["modified_tables"]
        cols_mod = result["modified_tables"]["users"].get("columns_modified", [])
        email_mod = next((c for c in cols_mod if c["name"] == "email"), None)
        assert email_mod is not None
        assert email_mod["target_nullable"] is False  # NOT NULL in target

    def test_single_table_diff(self, source_db, target_db):
        result = diff_schemas(source_db, target_db, table_name="users")
        assert "users" in result["modified_tables"]
        assert result["tables_only_in_source"] == []
        assert result["tables_only_in_target"] == []

    def test_identical_databases(self, tmp_path):
        """Two identical databases should have no diffs."""
        db1 = tmp_path / "db1.db"
        db2 = tmp_path / "db2.db"

        for db_path in [db1, db2]:
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, x TEXT)")
            conn.commit()
            conn.close()

        a1 = SQLiteAdapter(database_path=str(db1), read_only=True)
        a1.connect()
        a2 = SQLiteAdapter(database_path=str(db2), read_only=True)
        a2.connect()

        result = diff_schemas(a1, a2)
        assert result["tables_only_in_source"] == []
        assert result["tables_only_in_target"] == []
        assert result["modified_tables"] == {}
        assert "t" in result["identical_tables"]

    def test_nonexistent_table(self, source_db, target_db):
        result = diff_schemas(source_db, target_db, table_name="nonexistent")
        assert "error" in result

    def test_empty_databases(self, tmp_path):
        db1 = tmp_path / "empty1.db"
        db2 = tmp_path / "empty2.db"
        for db_path in [db1, db2]:
            sqlite3.connect(str(db_path)).close()

        a1 = SQLiteAdapter(database_path=str(db1), read_only=True)
        a1.connect()
        a2 = SQLiteAdapter(database_path=str(db2), read_only=True)
        a2.connect()

        result = diff_schemas(a1, a2)
        assert result["tables_only_in_source"] == []
        assert result["tables_only_in_target"] == []
        assert result["modified_tables"] == {}
        assert result["identical_tables"] == []
