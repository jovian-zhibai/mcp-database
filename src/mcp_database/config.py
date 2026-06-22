"""Configuration for mcp-database server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    """Configuration for a single database connection."""

    name: str
    type: str  # sqlite, postgresql, mysql
    # SQLite
    path: str = ""
    # PostgreSQL / MySQL
    host: str = "localhost"
    port: int = 0
    user: str = ""
    password: str = ""
    database: str = ""
    # Options
    read_only: bool = True

    def __post_init__(self) -> None:
        if self.type == "sqlite" and not self.path:
            raise ValueError(f"Database '{self.name}': 'path' is required for SQLite")
        if self.type in ("postgresql", "mysql") and not self.host:
            raise ValueError(f"Database '{self.name}': 'host' is required for {self.type}")


@dataclass
class ServerConfig:
    """Server-level configuration."""

    databases: list[DatabaseConfig] = field(default_factory=list)
    max_rows: int = 100
    allow_writes: bool = False
    query_timeout: int = 30
    mask_sensitive: bool = False


def load_config_from_env() -> ServerConfig:
    """Load configuration from environment variables.

    Supports:
        MCP_DATABASE_URL - single database URL (sqlite:///path or postgres://...)
        MCP_DATABASE_TYPE - database type (default: sqlite)
        MCP_DATABASE_READ_ONLY - read-only mode (default: true)
        MCP_MAX_ROWS - max rows to return (default: 100)
    """
    db_url = os.environ.get("MCP_DATABASE_URL", "")
    db_type = os.environ.get("MCP_DATABASE_TYPE", "sqlite")
    read_only = os.environ.get("MCP_DATABASE_READ_ONLY", "true").lower() in ("true", "1", "yes")

    def _int_env(key: str, default: int) -> int:
        val = os.environ.get(key, "")
        if not val:
            return default
        try:
            return int(val)
        except ValueError:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Invalid value for %s: '%s', using default %d", key, val, default)
            return default

    max_rows = _int_env("MCP_MAX_ROWS", 100)
    query_timeout = _int_env("MCP_QUERY_TIMEOUT", 30)
    mask_sensitive = os.environ.get("MCP_MASK_SENSITIVE", "false").lower() in ("true", "1", "yes")

    if db_url:
        config = _parse_url_to_config(db_url, db_type, read_only)
        return ServerConfig(databases=[config], max_rows=max_rows, allow_writes=not read_only, query_timeout=query_timeout, mask_sensitive=mask_sensitive)

    # Default: in-memory SQLite for demo/testing
    return ServerConfig(
        databases=[
            DatabaseConfig(name="demo", type="sqlite", path=":memory:", read_only=False)
        ],
        max_rows=max_rows,
        query_timeout=query_timeout,
        mask_sensitive=mask_sensitive,
    )


def load_config_from_dict(data: dict) -> ServerConfig:
    """Load configuration from a dictionary (e.g., parsed YAML)."""
    databases = []
    for db_data in data.get("databases", []):
        databases.append(DatabaseConfig(**db_data))
    return ServerConfig(
        databases=databases,
        max_rows=data.get("max_rows", 100),
        allow_writes=data.get("allow_writes", False),
        query_timeout=data.get("query_timeout", 30),
        mask_sensitive=data.get("mask_sensitive", False),
    )


def _parse_url_to_config(url: str, db_type: str, read_only: bool) -> DatabaseConfig:
    """Parse a database URL into a DatabaseConfig."""
    if db_type == "sqlite":
        # sqlite:///path/to/db.sqlite or sqlite:///:memory:
        path = url.replace("sqlite:///", "").replace("sqlite://", "")
        return DatabaseConfig(name="main", type="sqlite", path=path, read_only=read_only)

    if db_type == "postgresql":
        # postgres://user:password@host:port/database
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return DatabaseConfig(
            name="main",
            type="postgresql",
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            user=parsed.username or "postgres",
            password=parsed.password or "",
            database=parsed.path.lstrip("/") or "postgres",
            read_only=read_only,
        )

    if db_type == "mysql":
        # mysql://user:password@host:port/database
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return DatabaseConfig(
            name="main",
            type="mysql",
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=parsed.path.lstrip("/") or "",
            read_only=read_only,
        )

    raise ValueError(f"Unsupported database type: {db_type}")
