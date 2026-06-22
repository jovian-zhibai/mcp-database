"""mcp-database — MCP server for multi-database access.

Provides tools for Claude to query, inspect, and manage databases
(SQLite, PostgreSQL, MySQL) through the Model Context Protocol.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from mcp.server.fastmcp import Context, FastMCP

from mcp_database.adapters.base import DatabaseAdapter
from mcp_database.connection_manager import ConnectionManager
from mcp_database.er_diagram import generate_er_diagram as _generate_er_diagram
from mcp_database.schema_diff import diff_schemas

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan context
# ---------------------------------------------------------------------------

@dataclass
class AppContext:
    connection_manager: ConnectionManager = field(default_factory=ConnectionManager)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Load connections on startup, disconnect on shutdown."""
    cm = ConnectionManager()
    cm.load_from_env()

    if not cm.has_connections:
        logger.warning("No database connections configured.")

    try:
        yield AppContext(connection_manager=cm)
    finally:
        cm.disconnect_all()


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Database Server",
    lifespan=app_lifespan,
)


def _get_adapter(ctx: Context, connection_name: str = "default") -> DatabaseAdapter:
    """Get a database adapter by connection name."""
    app_ctx: AppContext = ctx.request_context.lifespan_context
    return app_ctx.connection_manager.get(connection_name)


def _get_manager(ctx: Context) -> ConnectionManager:
    """Get the ConnectionManager from app context."""
    app_ctx: AppContext = ctx.request_context.lifespan_context
    return app_ctx.connection_manager


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_databases(ctx: Context) -> str:
    """List all configured database connections and their status.

    Returns JSON with connection names, types, status, and masked URLs.
    """
    cm = _get_manager(ctx)
    connections = cm.list_all()
    if not connections:
        return "No databases configured."
    return json.dumps(connections, indent=2, ensure_ascii=False)


@mcp.tool()
def list_tables(
    database: str | None = None,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """List all tables in a database.

    Args:
        database: Name of the database within the connection (optional).
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    tables = adapter.list_tables(database)
    if not tables:
        return f"No tables found in {connection_name}."
    return "\n".join(tables)


@mcp.tool()
def get_table_info(
    table: str,
    database: str | None = None,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Get detailed information about a table: columns, types, row count.

    Args:
        table: Table name.
        database: Name of the database within the connection (optional).
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    info = adapter.get_table_info(table, database)

    lines = [f"Table: {info.name}", f"Rows: {info.row_count}", "", "Columns:"]
    for col in info.columns:
        parts = [col["name"], col["type"]]
        if col.get("primary_key"):
            parts.append("PK")
        if not col.get("nullable", True):
            parts.append("NOT NULL")
        if col.get("default") is not None:
            parts.append(f"DEFAULT {col['default']}")
        lines.append(f"  {' '.join(parts)}")

    if info.create_sql:
        lines.extend(["", "CREATE SQL:", info.create_sql])

    return "\n".join(lines)


@mcp.tool()
def get_schema(
    database: str | None = None,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Get the full database schema (CREATE TABLE statements for all tables).

    Args:
        database: Name of the database within the connection (optional).
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    return adapter.get_schema(database)


@mcp.tool()
def query(
    sql: str,
    database: str | None = None,
    max_rows: int = 100,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Execute a read-only SQL query (SELECT, SHOW, DESCRIBE, EXPLAIN) and return results.

    Args:
        sql: SQL query to execute.
        database: Name of the database within the connection (optional).
        max_rows: Maximum number of rows to return (default: 100).
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    cm = _get_manager(ctx)
    max_rows = min(max_rows, cm.global_max_rows)

    try:
        result = adapter.execute_query(sql, database=database, max_rows=max_rows, timeout=cm.query_timeout)
    except RuntimeError as e:
        return f"Error: {e}"

    return result.to_table(max_rows=max_rows)


@mcp.tool()
def execute(
    sql: str,
    database: str | None = None,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Execute a write SQL statement (INSERT, UPDATE, DELETE). Only works if writes are enabled.

    Args:
        sql: SQL statement to execute.
        database: Name of the database within the connection (optional).
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    cm = _get_manager(ctx)

    if not cm.allow_writes:
        return "Error: Write operations are disabled. Set allow_writes=True in config to enable."

    if adapter._is_read_only_query(sql):
        return "Error: Use the 'query' tool for SELECT statements."

    affected = adapter.execute_write(sql, database=database)
    return f"OK. {affected} row(s) affected."


@mcp.tool()
def sample_rows(
    table: str,
    limit: int = 5,
    database: str | None = None,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Get a sample of rows from a table to understand its data.

    Args:
        table: Table name.
        limit: Number of rows to sample (default: 5, max: 20).
        database: Name of the database within the connection (optional).
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    cm = _get_manager(ctx)
    limit = min(limit, 20)
    try:
        result = adapter.execute_query(f"SELECT * FROM \"{table}\" LIMIT {limit}", max_rows=limit, timeout=cm.query_timeout)
    except RuntimeError as e:
        return f"Error: {e}"
    return result.to_table(max_rows=limit)


@mcp.tool()
def search_tables(
    keyword: str,
    database: str | None = None,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Search for tables or columns matching a keyword.

    Args:
        keyword: Keyword to search for in table and column names.
        database: Name of the database within the connection (optional).
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    keyword_lower = keyword.lower()
    matches = []

    for table_name in adapter.list_tables(database):
        if keyword_lower in table_name.lower():
            matches.append(f"Table: {table_name}")

        info = adapter.get_table_info(table_name, database)
        for col in info.columns:
            if keyword_lower in col["name"].lower():
                matches.append(f"  {table_name}.{col['name']} ({col['type']})")

    return "\n".join(matches) if matches else f"No matches for '{keyword}'."


@mcp.tool()
def schema_diff(
    source_connection: str,
    target_connection: str,
    table_name: str = "",
    ctx: Context = None,
) -> str:
    """Compare schemas between two database connections.

    Args:
        source_connection: Source connection name.
        target_connection: Target connection name.
        table_name: Optional table name to diff. If empty, diff all tables.
    """
    cm = _get_manager(ctx)
    source = cm.get(source_connection)
    target = cm.get(target_connection)

    result = diff_schemas(
        source,
        target,
        table_name=table_name if table_name else None,
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def check_health(
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Check database health: latency, table count, row count, largest tables.

    Args:
        connection_name: Name of the database connection (default: "default").
    """
    adapter = _get_adapter(ctx, connection_name)
    result = adapter.get_health()
    result["connection_name"] = connection_name
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def generate_er_diagram(
    connection_name: str = "default",
    format: str = "mermaid",
    ctx: Context = None,
) -> str:
    """Generate an ER (Entity-Relationship) diagram in Mermaid format.

    Args:
        connection_name: Name of the database connection (default: "default").
        format: Output format. Currently only 'mermaid' is supported.
    """
    adapter = _get_adapter(ctx, connection_name)
    return _generate_er_diagram(adapter, format=format)


@mcp.tool()
def explain_query(
    query: str,
    connection_name: str = "default",
    ctx: Context = None,
) -> str:
    """Explain the execution plan for a SELECT query.

    Args:
        query: SQL SELECT or WITH...SELECT statement to explain.
        connection_name: Name of the database connection (default: "default").
    """
    # Security: only allow SELECT-like queries
    normalized = query.strip().upper()
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        return "Error: Only SELECT or WITH...SELECT queries can be explained."

    adapter = _get_adapter(ctx, connection_name)
    return adapter.explain(query.strip().rstrip(";"))


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("db://databases")
def resource_databases(ctx: Context) -> str:
    """List all configured databases."""
    cm = _get_manager(ctx)
    connections = cm.list_all()
    if not connections:
        return "No databases configured."
    lines = []
    for conn in connections:
        if conn["status"] == "connected":
            lines.append(f"- {conn['name']} ({conn['type']}) — {conn['status']}")
        else:
            lines.append(f"- {conn['name']} — {conn['status']}: {conn.get('error', 'unknown')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
