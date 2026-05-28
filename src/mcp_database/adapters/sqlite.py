"""SQLite database adapter."""

from __future__ import annotations

import sqlite3
from typing import Any

from mcp_database.adapters.base import DatabaseAdapter, QueryResult, TableInfo


class SQLiteAdapter(DatabaseAdapter):
    """Adapter for SQLite databases."""

    def __init__(self, database_path: str, read_only: bool = True):
        self.database_path = database_path
        self.read_only = read_only
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        uri = f"file:{self.database_path}"
        if self.read_only:
            uri += "?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True)
        self._conn.row_factory = sqlite3.Row

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            if not self._conn:
                return False
            self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def list_databases(self) -> list[str]:
        return ["main"]

    def list_tables(self, database: str | None = None) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]

    def get_table_info(self, table: str, database: str | None = None) -> TableInfo:
        conn = self._get_conn()
        # Get column info
        columns_raw = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        columns = [
            {
                "name": r["name"],
                "type": r["type"],
                "nullable": not r["notnull"],
                "default": r["dflt_value"],
                "primary_key": bool(r["pk"]),
            }
            for r in columns_raw
        ]

        # Get row count
        row_count = conn.execute(f"SELECT COUNT(*) as cnt FROM '{table}'").fetchone()["cnt"]

        # Get create SQL
        create_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        create_sql = create_row["sql"] if create_row else None

        return TableInfo(name=table, columns=columns, row_count=row_count, create_sql=create_sql)

    def get_schema(self, database: str | None = None) -> str:
        conn = self._get_conn()
        tables = self.list_tables()
        parts = []
        for table in tables:
            info = self.get_table_info(table)
            col_lines = []
            for col in info.columns:
                parts_str = [col["type"]]
                if col["primary_key"]:
                    parts_str.append("PRIMARY KEY")
                if not col["nullable"]:
                    parts_str.append("NOT NULL")
                if col["default"] is not None:
                    parts_str.append(f"DEFAULT {col['default']}")
                col_lines.append(f"  {col['name']} {' '.join(parts_str)}")
            parts.append(f"CREATE TABLE {table} (\n" + ",\n".join(col_lines) + "\n);")
        return "\n\n".join(parts) if parts else "No tables found."

    def execute_query(self, sql: str, database: str | None = None, max_rows: int = 100) -> QueryResult:
        conn = self._get_conn()
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        all_rows = cursor.fetchall()
        row_count = len(all_rows)
        truncated = row_count > max_rows
        rows = [list(row) for row in all_rows[:max_rows]]
        return QueryResult(columns=columns, rows=rows, row_count=row_count, truncated=truncated)

    def execute_write(self, sql: str, database: str | None = None) -> int:
        if self.read_only:
            raise NotImplementedError("SQLite adapter is in read-only mode. Set read_only=False to enable writes.")
        conn = self._get_conn()
        cursor = conn.execute(sql)
        conn.commit()
        return cursor.rowcount

    @property
    def db_type(self) -> str:
        return "sqlite"

    def _get_conn(self) -> sqlite3.Connection:
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn
