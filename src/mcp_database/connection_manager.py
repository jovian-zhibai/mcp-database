"""Multi-database connection manager.

Supports:
- Single connection via MCP_DATABASE_URL (backward compatible)
- Multiple connections via MCP_DATABASE_CONFIG JSON file
- Per-connection read_only and max_rows settings
- URL masking for security
"""

from __future__ import annotations

import json
import logging
import os
from urllib.parse import urlparse, urlunparse

from mcp_database.adapters.base import DatabaseAdapter
from mcp_database.adapters.sqlite import SQLiteAdapter
from mcp_database.config import DatabaseConfig, load_config_from_env, _parse_url_to_config

logger = logging.getLogger(__name__)


def _mask_url(url: str) -> str:
    """Replace password in a URL with ***."""
    parsed = urlparse(url)
    if parsed.password:
        # Build a netloc with masked password
        userinfo = f"{parsed.username or ''}:***"
        netloc = f"{userinfo}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        masked = parsed._replace(netloc=netloc)
        return urlunparse(masked)
    return url


class ConnectionManager:
    """Manages multiple database connections via adapters."""

    def __init__(self):
        self.connections: dict[str, DatabaseAdapter] = {}
        self._connection_configs: dict[str, DatabaseConfig] = {}
        self._connection_urls: dict[str, str] = {}
        self._connection_errors: dict[str, str] = {}
        self.global_max_rows: int = 100
        self.allow_writes: bool = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_from_env(self) -> None:
        """Load connection(s) from environment variables.

        MCP_DATABASE_URL — single connection (backward compatible), name="default".
        MCP_DATABASE_CONFIG — path to JSON file with multiple connections.
        """
        config_path = os.environ.get("MCP_DATABASE_CONFIG", "")

        if config_path:
            self.load_from_config(config_path)
            return

        # Single connection (backward compatible)
        server_cfg = load_config_from_env()
        self.global_max_rows = server_cfg.max_rows
        self.allow_writes = server_cfg.allow_writes

        for db_cfg in server_cfg.databases:
            name = db_cfg.name
            if name == "demo" and not os.environ.get("MCP_DATABASE_URL"):
                name = "default"
            elif name == "main":
                name = "default"
            self._add_connection(name, db_cfg)

    def load_from_config(self, config_path: str) -> None:
        """Load connections from a JSON configuration file.

        JSON format:
        {
            "connections": {
                "prod": {"url": "postgres://...", "read_only": true, "max_rows": 50},
                "staging": {"url": "postgres://...", "read_only": true},
                "local": {"url": "sqlite:///dev.db", "read_only": false}
            },
            "settings": {
                "max_rows": 100,
                "allow_writes": false
            }
        }
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            data = json.load(f)

        settings = data.get("settings", {})
        self.global_max_rows = settings.get("max_rows", 100)
        self.allow_writes = settings.get("allow_writes", False)

        connections = data.get("connections", {})
        for name, conn_data in connections.items():
            url = conn_data["url"]
            read_only = conn_data.get("read_only", True)
            max_rows = conn_data.get("max_rows")

            # Determine type from URL scheme
            db_type = self._guess_type_from_url(url)
            db_cfg = _parse_url_to_config(url, db_type, read_only)
            db_cfg.name = name

            self._add_connection(name, db_cfg, url=url, per_conn_max_rows=max_rows)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _add_connection(
        self,
        name: str,
        db_cfg: DatabaseConfig,
        url: str | None = None,
        per_conn_max_rows: int | None = None,
    ) -> None:
        """Create adapter and connect. Record errors without failing."""
        adapter = self._create_adapter(db_cfg)
        self._connection_configs[name] = db_cfg
        if url:
            self._connection_urls[name] = url

        try:
            adapter.connect()
            self.connections[name] = adapter
            logger.info("Connected to %s (%s)", name, adapter.db_type)
        except Exception as e:
            self._connection_errors[name] = str(e)
            logger.warning("Failed to connect to %s: %s", name, e)

    def _create_adapter(self, config: DatabaseConfig) -> DatabaseAdapter:
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

    @staticmethod
    def _guess_type_from_url(url: str) -> str:
        """Guess database type from URL scheme."""
        scheme = url.split("://")[0] if "://" in url else ""
        type_map = {
            "sqlite": "sqlite",
            "postgres": "postgresql",
            "postgresql": "postgresql",
            "mysql": "mysql",
        }
        return type_map.get(scheme, "sqlite")

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, name: str = "default") -> DatabaseAdapter:
        """Get a connected adapter by name.

        Raises ValueError if the connection doesn't exist or failed to connect.
        """
        if name in self.connections:
            return self.connections[name]

        if name in self._connection_errors:
            raise ValueError(
                f"Connection '{name}' failed: {self._connection_errors[name]}"
            )

        available = list(self.connections.keys())
        if available:
            raise ValueError(
                f"Connection '{name}' not found. Available: {', '.join(sorted(available))}"
            )
        raise ValueError(f"No connections configured. Connection '{name}' not found.")

    def get_connection_error(self, name: str) -> str | None:
        """Return error message if a connection failed, or None."""
        return self._connection_errors.get(name)

    def list_all(self) -> list[dict]:
        """Return metadata for all connections (connected + failed).

        URLs are masked for security.
        """
        result = []
        for name, adapter in self.connections.items():
            entry: dict = {
                "name": name,
                "type": adapter.db_type,
                "status": "connected",
            }
            if name in self._connection_urls:
                entry["url"] = _mask_url(self._connection_urls[name])
            result.append(entry)

        for name in sorted(self._connection_errors.keys()):
            entry: dict = {
                "name": name,
                "status": "error",
                "error": self._connection_errors[name],
            }
            if name in self._connection_urls:
                entry["url"] = _mask_url(self._connection_urls[name])
            result.append(entry)

        return result

    def disconnect_all(self) -> None:
        """Disconnect all adapters."""
        for name, adapter in list(self.connections.items()):
            try:
                adapter.disconnect()
                logger.info("Disconnected from %s", name)
            except Exception:
                logger.exception("Error disconnecting from %s", name)
        self.connections.clear()
        self._connection_errors.clear()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def has_connections(self) -> bool:
        return len(self.connections) > 0
