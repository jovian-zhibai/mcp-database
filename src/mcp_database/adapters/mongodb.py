"""MongoDB database adapter — preview.

Install: pip install 'mcp-database[mongodb]'
URL format: mongodb://user:pass@host:27017/dbname
"""

from __future__ import annotations

from typing import Any

from mcp_database.adapters.base import DatabaseAdapter, QueryResult, TableInfo


class MongoDBAdapter(DatabaseAdapter):
    """Adapter for MongoDB databases — coming soon.

    Full support planned for v0.3.0.
    Currently supports: list_tables, sample_rows, get_table_info.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 27017,
        user: str = "",
        password: str = "",
        database: str = "test",
        read_only: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.default_database = database
        self.read_only = read_only
        self._conn: Any = None
        self._db: Any = None

    def connect(self) -> None:
        try:
            import pymongo
        except ImportError:
            raise ImportError(
                "pymongo is required for MongoDB. Install with: pip install 'mcp-database[mongodb]'"
            )
        uri = f"mongodb://{self.host}:{self.port}"
        if self.user:
            uri = f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}"
        self._conn = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._db = self._conn[self.default_database]
        # Verify connection
        self._conn.admin.command("ping")

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            self._db = None

    def test_connection(self) -> bool:
        try:
            if not self._conn:
                return False
            self._conn.admin.command("ping")
            return True
        except Exception:
            return False

    def list_databases(self) -> list[str]:
        return [self.default_database]

    def list_tables(self, database: str | None = None) -> list[str]:
        db = self._db
        if database:
            db = self._conn[database]
        return db.list_collection_names()

    def get_table_info(self, table: str, database: str | None = None) -> TableInfo:
        db = self._db
        if database:
            db = self._conn[database]
        coll = db[table]
        count = coll.count_documents({})
        # Sample one document to infer fields
        sample = coll.find_one()
        columns = []
        if sample:
            for key, val in sample.items():
                columns.append({
                    "name": key,
                    "type": type(val).__name__ if val is not None else "unknown",
                    "nullable": True,
                    "default": None,
                    "primary_key": key == "_id",
                })
        return TableInfo(name=table, columns=columns, row_count=count, create_sql=None)

    def get_schema(self, database: str | None = None) -> str:
        tables = self.list_tables(database)
        lines = [f"Database: {database or self.default_database}", "", "Collections:"]
        for t in tables:
            info = self.get_table_info(t, database)
            fields = ", ".join(f"{c['name']} ({c['type']})" for c in info.columns)
            lines.append(f"  {t}: {info.row_count} documents, fields: [{fields}]")
        return "\n".join(lines)

    def execute_query(self, sql: str, database: str | None = None, max_rows: int = 100, timeout: int = 30) -> QueryResult:
        raise NotImplementedError(
            "MongoDB does not use SQL. Use the query tool with a JSON filter: "
            '{"collection": "name", "filter": {}, "limit": 10}'
        )

    def execute_write(self, sql: str, database: str | None = None) -> int:
        raise NotImplementedError("MongoDB: coming in v0.3.0")

    @property
    def db_type(self) -> str:
        return "mongodb"

    def get_columns(self, table: str, database: str | None = None) -> list[dict]:
        info = self.get_table_info(table, database)
        return info.columns

    def get_indexes(self, table: str, database: str | None = None) -> list[dict]:
        db = self._db
        if database:
            db = self._conn[database]
        idx_list = db[table].list_indexes()
        result = []
        for idx in idx_list:
            result.append({
                "name": idx["name"],
                "columns": list(idx["key"].keys()),
                "unique": idx.get("unique", False),
            })
        return result

    def get_constraints(self, table: str, database: str | None = None) -> list[dict]:
        return []  # MongoDB has no FK constraints

    def get_health(self) -> dict:
        import time
        start = time.monotonic()
        self.test_connection()
        latency = (time.monotonic() - start) * 1000

        tables = self.list_tables()
        total_docs = 0
        largest = []
        for t in tables:
            count = self._db[t].count_documents({})
            total_docs += count
            largest.append({"name": t, "rows": count})
        largest.sort(key=lambda x: x["rows"], reverse=True)
        for entry in largest[:5]:
            entry["estimated_size"] = f"{entry['rows'] * 0.5:.1f} KB"

        return {
            "status": "healthy",
            "database_type": self.db_type,
            "tables_count": len(tables),
            "total_rows": total_docs,
            "largest_tables": largest[:5],
            "connection_latency_ms": round(latency, 2),
        }

    def explain(self, query: str) -> str:
        return "MongoDB explain: use db.collection.explain() in the mongo shell."

    def sample_rows(self, table: str, limit: int = 5, database: str | None = None) -> list[dict]:
        db = self._db
        if database:
            db = self._conn[database]
        return list(db[table].find().limit(limit))
