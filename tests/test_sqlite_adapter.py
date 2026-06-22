"""Tests for the SQLite adapter."""

import sqlite3

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter


@pytest.fixture
def sample_db(tmp_path):
    """Create a temporary SQLite database with sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            age INTEGER DEFAULT 0
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
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Alice', 'alice@test.com', 30)")
    conn.execute("INSERT INTO users (name, email, age) VALUES ('Bob', 'bob@test.com', 25)")
    conn.execute("INSERT INTO orders (user_id, amount) VALUES (1, 99.99)")
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def adapter(sample_db):
    """Create a connected SQLite adapter."""
    db = SQLiteAdapter(database_path=sample_db, read_only=True)
    db.connect()
    yield db
    db.disconnect()


class TestSQLiteConnection:
    def test_connect_and_test(self, adapter):
        assert adapter.test_connection() is True

    def test_disconnect(self, sample_db):
        db = SQLiteAdapter(database_path=sample_db)
        db.connect()
        db.disconnect()
        assert db.test_connection() is False

    def test_db_type(self, adapter):
        assert adapter.db_type == "sqlite"


class TestSQLiteListTables:
    def test_list_tables(self, adapter):
        tables = adapter.list_tables()
        assert "users" in tables
        assert "orders" in tables

    def test_list_tables_empty(self, tmp_path):
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        db = SQLiteAdapter(database_path=str(db_path))
        db.connect()
        tables = db.list_tables()
        assert tables == []
        db.disconnect()


class TestSQLiteTableInfo:
    def test_get_table_info(self, adapter):
        info = adapter.get_table_info("users")
        assert info.name == "users"
        assert info.row_count == 2
        assert len(info.columns) == 4

        # Check column details
        id_col = next(c for c in info.columns if c["name"] == "id")
        assert id_col["primary_key"] is True
        assert id_col["type"] == "INTEGER"

        name_col = next(c for c in info.columns if c["name"] == "name")
        assert name_col["nullable"] is False

    def test_get_table_info_with_data(self, adapter):
        info = adapter.get_table_info("orders")
        assert info.row_count == 1


class TestSQLiteSchema:
    def test_get_schema(self, adapter):
        schema = adapter.get_schema()
        assert "users" in schema
        assert "orders" in schema
        assert "CREATE TABLE" in schema

    def test_get_schema_empty(self, tmp_path):
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        db = SQLiteAdapter(database_path=str(db_path))
        db.connect()
        schema = db.get_schema()
        assert schema == "No tables found."
        db.disconnect()


class TestSQLiteQuery:
    def test_select_all(self, adapter):
        result = adapter.execute_query("SELECT * FROM users")
        assert result.row_count == 2
        assert "id" in result.columns
        assert "name" in result.columns

    def test_select_with_limit(self, adapter):
        result = adapter.execute_query("SELECT * FROM users LIMIT 1", max_rows=1)
        assert result.row_count == 1

    def test_select_with_where(self, adapter):
        result = adapter.execute_query("SELECT * FROM users WHERE name = 'Alice'")
        assert result.row_count == 1
        assert result.rows[0][1] == "Alice"

    def test_to_table_format(self, adapter):
        result = adapter.execute_query("SELECT name, email FROM users")
        table = result.to_table()
        assert "Alice" in table
        assert "Bob" in table
        assert "name" in table

    def test_empty_result(self, adapter):
        result = adapter.execute_query("SELECT * FROM users WHERE id = 999")
        assert result.row_count == 0


class TestSQLiteReadOnly:
    def test_read_only_rejects_write(self, adapter):
        with pytest.raises(NotImplementedError, match="read-only"):
            adapter.execute_write("INSERT INTO users (name) VALUES ('Charlie')")

    def test_read_only_false_allows_write(self, sample_db):
        db = SQLiteAdapter(database_path=sample_db, read_only=False)
        db.connect()
        affected = db.execute_write("INSERT INTO users (name, email) VALUES ('Charlie', 'c@test.com')")
        assert affected == 1
        db.disconnect()


class TestSQLiteEdgeCases:
    def test_max_rows_truncation(self, sample_db):
        conn = sqlite3.connect(sample_db)
        for i in range(10):
            conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", (f"User{i}", f"u{i}@test.com"))
        conn.commit()
        conn.close()

        db = SQLiteAdapter(database_path=sample_db, read_only=True)
        db.connect()
        result = db.execute_query("SELECT * FROM users", max_rows=3)
        assert len(result.rows) == 3
        assert result.truncated is True
        assert result.row_count == 12
        db.disconnect()
