"""mcp-database — MCP server for multi-database access.

Provides tools for Claude to query, inspect, and manage databases
(SQLite, PostgreSQL, MySQL) through the Model Context Protocol.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from mcp.server.fastmcp import Context, FastMCP

from mcp_database.adapters.base import DatabaseAdapter
from mcp_database.adapters.sqlite import SQLiteAdapter
from mcp_database.config import ServerConfig, load_config_from_env

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------

def _create_adapter(config) -> DatabaseAdapter:
    """Create a database adapter from config."""
    if config.type == "sqlite":
        return SQLiteAdapter(database_path=config.path, read_only=config.read_only)
    if config.type == "postgresql":
        from mcp_database.adapters.postgres import PostgreSQLAdapter

        return PostgreSQLAdapter(
            host=config.host,
            port=config.port or 5432,
            user=config.user,
            password=config.password,
            database=config.database,
            read_only=config.read_only,
        )
    if config.type == "mysql":
        from mcp_database.adapters.mysql import MySQLAdapter

        return MySQLAdapter(
            host=config.host,
            port=config.port or 3306,
            user=config.user,
            password=config.password,
            database=config.database,
            read_only=config.read_only,
        )
    raise ValueError(f"Unsupported database type: {config.type}")


# ---------------------------------------------------------------------------
# Lifespan context
# ---------------------------------------------------------------------------

@dataclass
class AppContext:
    adapters: dict[str, DatabaseAdapter] = field(default_factory=dict)
    config: ServerConfig = field(default_factory=ServerConfig)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage database connections on server startup/shutdown."""
    config = load_config_from_env()
    adapters: dict[str, DatabaseAdapter] = {}

    for db_config in config.databases:
        adapter = _create_adapter(db_config)
        try:
            adapter.connect()
            adapters[db_config.name] = adapter
            logger.info("Connected to %s (%s)", db_config.name, db_config.type)
        except Exception:
            logger.exception("Failed to connect to %s", db_config.name)

    try:
        yield AppContext(adapters=adapters, config=config)
    finally:
        for name, adapter in adapters.items():
            try:
                adapter.disconnect()
                logger.info("Disconnected from %s", name)
            except Exception:
                logger.exception("Error disconnecting from %s", name)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Database Server",
    lifespan=app_lifespan,
)


def _get_adapter(ctx: Context, name: str | None = None) -> DatabaseAdapter:
    """Get a database adapter by name, or the first one if name is None."""
    app_ctx: AppContext = ctx.request_context.lifespan_context
    if not app_ctx.adapters:
        raise RuntimeError("No databases configured.")
    if name:
        if name not in app_ctx.adapters:
            available = ", ".join(app_ctx.adapters.keys())
            raise ValueError(f"Database '{name}' not found. Available: {available}")
        return app_ctx.adapters[name]
    return next(iter(app_ctx.adapters.values()))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_databases(ctx: Context) -> str:
    """List all configured database connections and their types."""
    app_ctx: AppContext = ctx.request_context.lifespan_context
    lines = []
    for name, adapter in app_ctx.adapters.items():
        status = "connected" if adapter.test_connection() else "disconnected"
        lines.append(f"{name} ({adapter.db_type}) — {status}")
    return "\n".join(lines) if lines else "No databases configured."


@mcp.tool()
def list_tables(database: str | None = None, ctx: Context = None) -> str:
    """List all tables in a database.

    Args:
        database: Name of the database connection (optional if only one is configured).
    """
    adapter = _get_adapter(ctx, database)
    tables = adapter.list_tables()
    if not tables:
        return f"No tables found in {database or adapter.db_type}."
    return "\n".join(tables)


@mcp.tool()
def get_table_info(table: str, database: str | None = None, ctx: Context = None) -> str:
    """Get detailed information about a table: columns, types, row count.

    Args:
        table: Table name.
        database: Name of the database connection (optional if only one is configured).
    """
    adapter = _get_adapter(ctx, database)
    info = adapter.get_table_info(table)

    lines = [f"Table: {info.name}", f"Rows: {info.row_count}", "", "Columns:"]
    for col in info.columns:
        parts = [col["name"], col["type"]]
        if col["primary_key"]:
            parts.append("PK")
        if not col["nullable"]:
            parts.append("NOT NULL")
        if col["default"] is not None:
            parts.append(f"DEFAULT {col['default']}")
        lines.append(f"  {' '.join(parts)}")

    if info.create_sql:
        lines.extend(["", "CREATE SQL:", info.create_sql])

    return "\n".join(lines)


@mcp.tool()
def get_schema(database: str | None = None, ctx: Context = None) -> str:
    """Get the full database schema (CREATE TABLE statements for all tables).

    Args:
        database: Name of the database connection (optional if only one is configured).
    """
    adapter = _get_adapter(ctx, database)
    return adapter.get_schema()


@mcp.tool()
def query(sql: str, database: str | None = None, max_rows: int = 100, ctx: Context = None) -> str:
    """Execute a read-only SQL query (SELECT, SHOW, DESCRIBE, EXPLAIN) and return results.

    Args:
        sql: SQL query to execute.
        database: Name of the database connection (optional if only one is configured).
        max_rows: Maximum number of rows to return (default: 100).
    """
    adapter = _get_adapter(ctx, database)
    app_ctx: AppContext = ctx.request_context.lifespan_context
    max_rows = min(max_rows, app_ctx.config.max_rows)

    result = adapter.execute_query(sql, max_rows=max_rows)
    return result.to_table(max_rows=max_rows)


@mcp.tool()
def execute(sql: str, database: str | None = None, ctx: Context = None) -> str:
    """Execute a write SQL statement (INSERT, UPDATE, DELETE). Only works if writes are enabled.

    Args:
        sql: SQL statement to execute.
        database: Name of the database connection (optional if only one is configured).
    """
    adapter = _get_adapter(ctx, database)
    app_ctx: AppContext = ctx.request_context.lifespan_context

    if not app_ctx.config.allow_writes:
        return "Error: Write operations are disabled. Set allow_writes=True in config to enable."

    if adapter._is_read_only_query(sql):
        return "Error: Use the 'query' tool for SELECT statements."

    affected = adapter.execute_write(sql)
    return f"OK. {affected} row(s) affected."


@mcp.tool()
def sample_rows(table: str, limit: int = 5, database: str | None = None, ctx: Context = None) -> str:
    """Get a sample of rows from a table to understand its data.

    Args:
        table: Table name.
        limit: Number of rows to sample (default: 5, max: 20).
        database: Name of the database connection (optional if only one is configured).
    """
    adapter = _get_adapter(ctx, database)
    limit = min(limit, 20)
    result = adapter.execute_query(f"SELECT * FROM \"{table}\" LIMIT {limit}", max_rows=limit)
    return result.to_table(max_rows=limit)


@mcp.tool()
def search_tables(keyword: str, database: str | None = None, ctx: Context = None) -> str:
    """Search for tables or columns matching a keyword.

    Args:
        keyword: Keyword to search for in table and column names.
        database: Name of the database connection (optional if only one is configured).
    """
    adapter = _get_adapter(ctx, database)
    keyword_lower = keyword.lower()
    matches = []

    for table_name in adapter.list_tables():
        if keyword_lower in table_name.lower():
            matches.append(f"Table: {table_name}")

        info = adapter.get_table_info(table_name)
        for col in info.columns:
            if keyword_lower in col["name"].lower():
                matches.append(f"  {table_name}.{col['name']} ({col['type']})")

    return "\n".join(matches) if matches else f"No matches for '{keyword}'."


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("db://databases")
def resource_databases(ctx: Context) -> str:
    """List all configured databases."""
    app_ctx: AppContext = ctx.request_context.lifespan_context
    lines = []
    for name, adapter in app_ctx.adapters.items():
        lines.append(f"- {name} ({adapter.db_type})")
    return "\n".join(lines) if lines else "No databases configured."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
