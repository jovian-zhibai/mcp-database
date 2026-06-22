"""Base adapter interface for database connections."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class QueryResult:
    """Result of a SQL query."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False

    def to_table(self, max_rows: int = 100) -> str:
        """Format result as an aligned text table."""
        if not self.columns:
            return "No results."

        rows = self.rows[:max_rows]
        # Calculate column widths
        widths = [len(c) for c in self.columns]
        for row in rows:
            for i, val in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(val)))

        # Header
        header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(self.columns))
        separator = "-+-".join("-" * w for w in widths)
        lines = [header, separator]

        # Rows
        for row in rows:
            line = " | ".join(str(row[i]).ljust(widths[i]) if i < len(row) else "" for i in range(len(self.columns)))
            lines.append(line)

        result = "\n".join(lines)
        if self.truncated:
            result += f"\n... ({self.row_count} total rows, showing first {max_rows})"
        return result


@dataclass
class TableInfo:
    """Information about a database table."""

    name: str
    columns: list[dict[str, Any]]
    row_count: int | None = None
    create_sql: str | None = None


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the database."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the database connection."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the connection is alive."""

    @abstractmethod
    def list_databases(self) -> list[str]:
        """List available databases (if applicable)."""

    @abstractmethod
    def list_tables(self, database: str | None = None) -> list[str]:
        """List all tables in the database."""

    @abstractmethod
    def get_table_info(self, table: str, database: str | None = None) -> TableInfo:
        """Get detailed information about a table."""

    @abstractmethod
    def get_schema(self, database: str | None = None) -> str:
        """Get the full database schema as formatted text."""

    @abstractmethod
    def get_columns(self, table: str, database: str | None = None) -> list[dict]:
        """Get column definitions for a table.

        Returns list of dicts with keys: name, type, nullable, default, primary_key.
        """

    @abstractmethod
    def get_indexes(self, table: str, database: str | None = None) -> list[dict]:
        """Get index definitions for a table.

        Returns list of dicts with keys: name, columns (list), unique.
        """

    @abstractmethod
    def get_constraints(self, table: str, database: str | None = None) -> list[dict]:
        """Get foreign key and check constraints for a table.

        Returns list of dicts with keys: name, type (FK/CHECK), columns,
        ref_table, ref_columns (for FK).
        """

    @abstractmethod
    def get_health(self) -> dict:
        """Get database health status.

        Returns dict with keys: status, database_type, tables_count, total_rows,
        largest_tables, connection_latency_ms.
        """

    @abstractmethod
    def execute_query(self, sql: str, database: str | None = None, max_rows: int = 100) -> QueryResult:
        """Execute a read-only SQL query."""

    def execute_write(self, sql: str, database: str | None = None) -> int:
        """Execute a write SQL query (INSERT/UPDATE/DELETE). Returns affected rows.

        Raises NotImplementedError if the adapter is read-only.
        """
        raise NotImplementedError("This adapter is read-only. Use execute_query() for SELECT statements.")

    @property
    @abstractmethod
    def db_type(self) -> str:
        """Return the database type name (e.g., 'sqlite', 'postgresql', 'mysql')."""

    def _is_read_only_query(self, sql: str) -> bool:
        """Check if a query is read-only (SELECT, SHOW, DESCRIBE, EXPLAIN)."""
        normalized = sql.strip().upper()
        # Allow SELECT, SHOW, DESCRIBE, EXPLAIN, WITH (CTE leading to SELECT)
        read_only_prefixes = ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH", "PRAGMA")
        return any(normalized.startswith(prefix) for prefix in read_only_prefixes)
