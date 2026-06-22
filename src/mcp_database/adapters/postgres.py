"""PostgreSQL database adapter."""

from __future__ import annotations

from typing import Any

from mcp_database.adapters.base import DatabaseAdapter, QueryResult, TableInfo


class PostgreSQLAdapter(DatabaseAdapter):
    """Adapter for PostgreSQL databases."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        database: str = "postgres",
        read_only: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.default_database = database
        self.read_only = read_only
        self._conn: Any = None

    def connect(self) -> None:
        try:
            import psycopg2
        except ImportError:
            raise ImportError(
                "psycopg2 is required for PostgreSQL. Install with: pip install 'mcp-database[postgres]'"
            )
        self._conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.default_database,
        )
        if self.read_only:
            self._conn.set_session(readonly=True)

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            if not self._conn:
                return False
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return True
        except Exception:
            return False

    def list_databases(self) -> list[str]:
        cur = self._get_conn().cursor()
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname")
        rows = cur.fetchall()
        cur.close()
        return [r[0] for r in rows]

    def list_tables(self, database: str | None = None) -> list[str]:
        cur = self._get_conn().cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        rows = cur.fetchall()
        cur.close()
        return [r[0] for r in rows]

    def get_table_info(self, table: str, database: str | None = None) -> TableInfo:
        conn = self._get_conn()
        cur = conn.cursor()

        # Get columns
        cur.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
        col_rows = cur.fetchall()
        columns = [
            {
                "name": r[0],
                "type": r[1],
                "nullable": r[2] == "YES",
                "default": r[3],
                "primary_key": False,  # determined below
            }
            for r in col_rows
        ]

        # Get primary keys
        cur.execute(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = %s::regclass AND i.indisprimary",
            (table,),
        )
        pk_cols = {r[0] for r in cur.fetchall()}
        for col in columns:
            if col["name"] in pk_cols:
                col["primary_key"] = True

        # Get row count (estimate for large tables)
        cur.execute(f"SELECT COUNT(*) FROM \"{table}\"")
        row_count = cur.fetchone()[0]

        # Get create SQL (PostgreSQL doesn't have a single CREATE TABLE statement)
        create_sql = None

        cur.close()
        return TableInfo(name=table, columns=columns, row_count=row_count, create_sql=create_sql)

    def get_schema(self, database: str | None = None) -> str:
        tables = self.list_tables(database)
        parts = []
        for table in tables:
            info = self.get_table_info(table, database)
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
        """Get column definitions from information_schema."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
        rows = cur.fetchall()
        # Get primary keys
        cur.execute(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = %s::regclass AND i.indisprimary",
            (table,),
        )
        pk_cols = {r[0] for r in cur.fetchall()}
        cur.close()

        return [
            {
                "name": r[0],
                "type": r[1],
                "nullable": r[2] == "YES",
                "default": r[3],
                "primary_key": r[0] in pk_cols,
            }
            for r in rows
        ]

    def get_indexes(self, table: str, database: str | None = None) -> list[dict]:
        """Get indexes from pg_indexes."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = %s AND schemaname = 'public' "
            "AND indexname NOT LIKE '%_pkey'",
            (table,),
        )
        rows = cur.fetchall()
        cur.close()

        result = []
        for r in rows:
            # Parse columns from indexdef (e.g., "CREATE UNIQUE INDEX ... ON t (col1, col2)")
            import re
            cols_match = re.search(r"\(([^)]+)\)", r[1])
            cols = [c.strip() for c in cols_match.group(1).split(",")] if cols_match else []
            result.append({
                "name": r[0],
                "columns": cols,
                "unique": "UNIQUE" in r[1].upper(),
            })
        return result

    def get_constraints(self, table: str, database: str | None = None) -> list[dict]:
        """Get foreign key constraints from information_schema."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT kcu.column_name, ccu.table_name AS foreign_table_name, "
            "ccu.column_name AS foreign_column_name, tc.constraint_name "
            "FROM information_schema.table_constraints AS tc "
            "JOIN information_schema.key_column_usage AS kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage AS ccu "
            "  ON ccu.constraint_name = tc.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s",
            (table,),
        )
        rows = cur.fetchall()
        cur.close()

        return [
            {
                "name": r[3],
                "type": "FK",
                "columns": [r[0]],
                "ref_table": r[1],
                "ref_columns": [r[2]],
            }
            for r in rows
        ]

    def execute_query(self, sql: str, database: str | None = None, max_rows: int = 100) -> QueryResult:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        all_rows = cur.fetchall()
        row_count = len(all_rows)
        truncated = row_count > max_rows
        rows = [list(row) for row in all_rows[:max_rows]]
        cur.close()
        return QueryResult(columns=columns, rows=rows, row_count=row_count, truncated=truncated)

    def execute_write(self, sql: str, database: str | None = None) -> int:
        if self.read_only:
            raise NotImplementedError("PostgreSQL adapter is in read-only mode. Set read_only=False to enable writes.")
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(sql)
        affected = cur.rowcount
        conn.commit()
        cur.close()
        return affected

    @property
    def db_type(self) -> str:
        return "postgresql"

    def _get_conn(self) -> Any:
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn
