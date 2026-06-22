"""MySQL database adapter."""

from __future__ import annotations

from typing import Any

from mcp_database.adapters.base import DatabaseAdapter, QueryResult, TableInfo


class MySQLAdapter(DatabaseAdapter):
    """Adapter for MySQL databases."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "",
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
            import pymysql
        except ImportError:
            raise ImportError(
                "pymysql is required for MySQL. Install with: pip install 'mcp-database[mysql]'"
            )
        self._conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.default_database or None,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        if self.read_only:
            cur = self._conn.cursor()
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.close()

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
        cur.execute("SHOW DATABASES")
        rows = cur.fetchall()
        cur.close()
        return [r["Database"] for r in rows]

    def list_tables(self, database: str | None = None) -> list[str]:
        conn = self._get_conn()
        cur = conn.cursor()
        if database:
            cur.execute(f"SHOW TABLES FROM `{database}`")
        else:
            cur.execute("SHOW TABLES")
        rows = cur.fetchall()
        cur.close()
        # The column name varies: "Tables_in_{database}" or "Tables_in_{current_db}"
        return [list(r.values())[0] for r in rows]

    def get_table_info(self, table: str, database: str | None = None) -> TableInfo:
        conn = self._get_conn()
        cur = conn.cursor()

        table_ref = f"`{database}`.`{table}`" if database else f"`{table}`"

        # Get columns
        cur.execute(f"DESCRIBE {table_ref}")
        col_rows = cur.fetchall()
        columns = [
            {
                "name": r["Field"],
                "type": r["Type"],
                "nullable": r["Null"] == "YES",
                "default": r["Default"],
                "primary_key": r["Key"] == "PRI",
            }
            for r in col_rows
        ]

        # Get row count
        cur.execute(f"SELECT COUNT(*) as cnt FROM {table_ref}")
        row_count = cur.fetchone()["cnt"]

        # Get create SQL
        cur.execute(f"SHOW CREATE TABLE {table_ref}")
        create_row = cur.fetchone()
        create_sql = create_row.get("Create Table") if create_row else None

        cur.close()
        return TableInfo(name=table, columns=columns, row_count=row_count, create_sql=create_sql)

    def get_schema(self, database: str | None = None) -> str:
        tables = self.list_tables(database)
        parts = []
        for table in tables:
            info = self.get_table_info(table, database)
            if info.create_sql:
                parts.append(info.create_sql)
            else:
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
        """Get column definitions via DESCRIBE."""
        conn = self._get_conn()
        cur = conn.cursor()
        table_ref = f"`{database}`.`{table}`" if database else f"`{table}`"
        cur.execute(f"DESCRIBE {table_ref}")
        rows = cur.fetchall()
        cur.close()

        return [
            {
                "name": r["Field"],
                "type": r["Type"],
                "nullable": r["Null"] == "YES",
                "default": r["Default"],
                "primary_key": r["Key"] == "PRI",
            }
            for r in rows
        ]

    def get_indexes(self, table: str, database: str | None = None) -> list[dict]:
        """Get indexes via SHOW INDEX."""
        conn = self._get_conn()
        cur = conn.cursor()
        table_ref = f"`{database}`.`{table}`" if database else f"`{table}`"
        cur.execute(f"SHOW INDEX FROM {table_ref}")
        rows = cur.fetchall()
        cur.close()

        # Group by index name
        idx_map: dict[str, dict] = {}
        for r in rows:
            name = r["Key_name"]
            if name == "PRIMARY":
                continue
            if name not in idx_map:
                idx_map[name] = {
                    "name": name,
                    "columns": [],
                    "unique": not r["Non_unique"],
                }
            idx_map[name]["columns"].append(r["Column_name"])

        return list(idx_map.values())

    def get_constraints(self, table: str, database: str | None = None) -> list[dict]:
        """Get foreign keys from information_schema."""
        conn = self._get_conn()
        cur = conn.cursor()
        db_filter = database or self.default_database
        cur.execute(
            "SELECT column_name, referenced_table_name, referenced_column_name, constraint_name "
            "FROM information_schema.key_column_usage "
            "WHERE table_name = %s AND table_schema = %s AND referenced_table_name IS NOT NULL",
            (table, db_filter),
        )
        rows = cur.fetchall()
        cur.close()

        return [
            {
                "name": r["constraint_name"] or f"fk_{r['column_name']}",
                "type": "FK",
                "columns": [r["column_name"]],
                "ref_table": r["referenced_table_name"],
                "ref_columns": [r["referenced_column_name"]],
            }
            for r in rows
        ]

    def execute_query(self, sql: str, database: str | None = None, max_rows: int = 100) -> QueryResult:
        conn = self._get_conn()
        cur = conn.cursor()
        if database:
            cur.execute(f"USE `{database}`")
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        all_rows = cur.fetchall()
        row_count = len(all_rows)
        truncated = row_count > max_rows
        rows = [[row.get(c) for c in columns] for row in all_rows[:max_rows]]
        cur.close()
        return QueryResult(columns=columns, rows=rows, row_count=row_count, truncated=truncated)

    def execute_write(self, sql: str, database: str | None = None) -> int:
        if self.read_only:
            raise NotImplementedError("MySQL adapter is in read-only mode. Set read_only=False to enable writes.")
        conn = self._get_conn()
        cur = conn.cursor()
        if database:
            cur.execute(f"USE `{database}`")
        cur.execute(sql)
        affected = cur.rowcount
        conn.commit()
        cur.close()
        return affected

    @property
    def db_type(self) -> str:
        return "mysql"

    def _get_conn(self) -> Any:
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn
