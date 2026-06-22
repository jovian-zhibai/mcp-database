"""SQLite database adapter."""

from __future__ import annotations

import sqlite3
import threading

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

    def get_columns(self, table: str, database: str | None = None) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        return [
            {
                "name": r["name"],
                "type": r["type"],
                "nullable": not r["notnull"],
                "default": r["dflt_value"],
                "primary_key": bool(r["pk"]),
            }
            for r in rows
        ]

    def get_indexes(self, table: str, database: str | None = None) -> list[dict]:
        conn = self._get_conn()
        indexes = conn.execute(f"PRAGMA index_list('{table}')").fetchall()
        result = []
        for idx in indexes:
            cols = conn.execute(f"PRAGMA index_info('{idx['name']}')").fetchall()
            result.append({
                "name": idx["name"],
                "columns": [c["name"] for c in cols] if cols else [],
                "unique": bool(idx["unique"]),
            })
        return result

    def get_constraints(self, table: str, database: str | None = None) -> list[dict]:
        conn = self._get_conn()
        fks = conn.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
        return [
            {
                "name": f"fk_{fk['from']}_to_{fk['table']}_{fk['to']}",
                "type": "FK",
                "columns": [fk["from"]],
                "ref_table": fk["table"],
                "ref_columns": [fk["to"]],
            }
            for fk in fks
        ]

    def get_health(self) -> dict:
        import time

        conn = self._get_conn()
        start = time.monotonic()
        conn.execute("SELECT 1")
        latency = (time.monotonic() - start) * 1000

        tables = self.list_tables()
        tables_count = len(tables)
        total_rows = 0
        largest_tables: list[dict] = []

        for table in tables:
            rows = conn.execute(f"SELECT COUNT(*) FROM \"{table}\"").fetchone()[0]
            total_rows += rows
            largest_tables.append({"name": table, "rows": rows})

        # Sort by rows descending, take top 5
        largest_tables.sort(key=lambda x: x["rows"], reverse=True)
        largest_tables = largest_tables[:5]

        # Estimate size using page_count * page_size
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        estimated_size_bytes = page_count * page_size

        # Distribute estimated size proportionally
        for entry in largest_tables:
            if total_rows > 0:
                ratio = entry["rows"] / total_rows
            else:
                ratio = 1.0 / len(largest_tables) if largest_tables else 0
            entry["estimated_size"] = f"{estimated_size_bytes * ratio / 1024:.1f} KB"

        return {
            "status": "healthy",
            "database_type": self.db_type,
            "tables_count": tables_count,
            "total_rows": total_rows,
            "largest_tables": largest_tables,
            "connection_latency_ms": round(latency, 2),
        }

    def explain(self, query: str) -> str:
        conn = self._get_conn()
        rows = conn.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
        lines = []
        for r in rows:
            lines.append(f"{r['id']}|{r['parent']}|{r['notused']}|{r['detail']}")
        return "\n".join(lines) if lines else "No plan available."

    def diagnose_connection(self) -> dict:
        import os
        import time

        result = {
            "status": "unknown",
            "database_type": self.db_type,
            "read_only": self.read_only,
            "ssl": False,
            "errors": [],
        }

        # Check file existence
        if self.database_path not in (":memory:", ""):
            exists = os.path.exists(self.database_path)
            result["url"] = f"sqlite:///{self.database_path} (file exists: {exists}"
            if exists:
                size = os.path.getsize(self.database_path)
                result["url"] += f", size: {size / (1024*1024):.1f}MB)"
            else:
                result["url"] += ")"
                result["errors"].append(
                    f"Database file not found: {self.database_path}. "
                    "Create it with sqlite3 {self.database_path} or use :memory:."
                )
                result["status"] = "failed"
                return result
        else:
            result["url"] = "sqlite:///:memory:"

        # Try connection
        try:
            if not self._conn:
                self.connect()
            start = time.monotonic()
            self._conn.execute("SELECT 1")
            result["latency_ms"] = round((time.monotonic() - start) * 1000, 2)
            result["server_version"] = self._conn.execute("SELECT sqlite_version()").fetchone()[0]
            result["status"] = "connected"
            result["tables_accessible"] = True
        except Exception as e:
            result["status"] = "failed"
            result["errors"].append(str(e))
            result["tables_accessible"] = False

        return result

    def execute_query(self, sql: str, database: str | None = None, max_rows: int = 100, timeout: int = 30) -> QueryResult:
        conn = self._get_conn()
        timer = threading.Timer(timeout, conn.interrupt)
        timer.start()
        try:
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            all_rows = cursor.fetchall()
            row_count = len(all_rows)
            truncated = row_count > max_rows
            rows = [list(row) for row in all_rows[:max_rows]]
            return QueryResult(columns=columns, rows=rows, row_count=row_count, truncated=truncated)
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e).lower():
                raise RuntimeError(f"Query timed out after {timeout} seconds")
            raise
        finally:
            timer.cancel()

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
