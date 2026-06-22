"""Tests for config.py — environment variable parsing and defaults."""


import pytest

from mcp_database.config import (
    DatabaseConfig,
    load_config_from_dict,
    load_config_from_env,
    _parse_url_to_config,
)


class TestDatabaseConfig:
    def test_sqlite_config_valid(self):
        cfg = DatabaseConfig(name="test", type="sqlite", path=":memory:")
        assert cfg.name == "test"
        assert cfg.type == "sqlite"
        assert cfg.path == ":memory:"
        assert cfg.read_only is True

    def test_sqlite_config_missing_path_raises(self):
        with pytest.raises(ValueError, match="path"):
            DatabaseConfig(name="test", type="sqlite")

    def test_postgres_config_missing_host_raises(self):
        with pytest.raises(ValueError, match="host"):
            DatabaseConfig(name="test", type="postgresql", host="")

    def test_mysql_config_missing_host_raises(self):
        with pytest.raises(ValueError, match="host"):
            DatabaseConfig(name="test", type="mysql", host="")

    def test_postgres_config_valid(self):
        cfg = DatabaseConfig(
            name="pg",
            type="postgresql",
            host="db.example.com",
            port=5432,
            user="admin",
            password="secret",
            database="mydb",
            read_only=True,
        )
        assert cfg.host == "db.example.com"
        assert cfg.port == 5432

    def test_read_only_default_true(self):
        cfg = DatabaseConfig(name="t", type="sqlite", path=":memory:")
        assert cfg.read_only is True

    def test_read_only_explicit_false(self):
        cfg = DatabaseConfig(name="t", type="sqlite", path=":memory:", read_only=False)
        assert cfg.read_only is False


class TestLoadConfigFromEnv:
    def test_default_config_no_env(self, monkeypatch):
        """When no env vars are set, returns in-memory SQLite demo."""
        monkeypatch.delenv("MCP_DATABASE_URL", raising=False)
        monkeypatch.delenv("MCP_DATABASE_TYPE", raising=False)
        monkeypatch.delenv("MCP_DATABASE_READ_ONLY", raising=False)
        monkeypatch.delenv("MCP_MAX_ROWS", raising=False)

        cfg = load_config_from_env()
        assert len(cfg.databases) == 1
        assert cfg.databases[0].name == "demo"
        assert cfg.databases[0].type == "sqlite"
        assert cfg.databases[0].path == ":memory:"
        assert cfg.max_rows == 100

    def test_sqlite_url(self, monkeypatch):
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:////tmp/test.db")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")
        monkeypatch.setenv("MCP_DATABASE_READ_ONLY", "true")

        cfg = load_config_from_env()
        assert len(cfg.databases) == 1
        db = cfg.databases[0]
        assert db.name == "main"
        assert db.type == "sqlite"
        assert db.path == "/tmp/test.db"
        assert db.read_only is True

    def test_sqlite_memory_url(self, monkeypatch):
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///:memory:")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")

        cfg = load_config_from_env()
        assert cfg.databases[0].path == ":memory:"

    def test_read_only_false(self, monkeypatch):
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")
        monkeypatch.setenv("MCP_DATABASE_READ_ONLY", "false")

        cfg = load_config_from_env()
        assert cfg.databases[0].read_only is False

    def test_read_only_variants(self, monkeypatch):
        """Test various true/false representations."""
        for val, expected in [
            ("true", True), ("True", True), ("TRUE", True),
            ("1", True), ("yes", True), ("YES", True),
            ("false", False), ("False", False), ("0", False),
            ("no", False),
        ]:
            monkeypatch.setenv("MCP_DATABASE_READ_ONLY", val)
            monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///test.db")
            monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")
            cfg = load_config_from_env()
            assert cfg.databases[0].read_only is expected, f"read_only should be {expected} for '{val}'"

    def test_max_rows_env(self, monkeypatch):
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")
        monkeypatch.setenv("MCP_MAX_ROWS", "50")

        cfg = load_config_from_env()
        assert cfg.max_rows == 50

    def test_max_rows_default(self, monkeypatch):
        monkeypatch.delenv("MCP_MAX_ROWS", raising=False)
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")

        cfg = load_config_from_env()
        assert cfg.max_rows == 100

    def test_query_timeout_env(self, monkeypatch):
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")
        monkeypatch.setenv("MCP_QUERY_TIMEOUT", "15")

        cfg = load_config_from_env()
        assert cfg.query_timeout == 15

    def test_query_timeout_default(self, monkeypatch):
        monkeypatch.delenv("MCP_QUERY_TIMEOUT", raising=False)
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")

        cfg = load_config_from_env()
        assert cfg.query_timeout == 30


class TestLoadConfigFromDict:
    def test_single_database(self):
        data = {
            "databases": [
                {"name": "prod", "type": "sqlite", "path": "/data/prod.db", "read_only": True}
            ]
        }
        cfg = load_config_from_dict(data)
        assert len(cfg.databases) == 1
        assert cfg.databases[0].name == "prod"

    def test_multiple_databases(self):
        data = {
            "databases": [
                {"name": "db1", "type": "sqlite", "path": "/db1.db"},
                {"name": "db2", "type": "sqlite", "path": "/db2.db"},
            ]
        }
        cfg = load_config_from_dict(data)
        assert len(cfg.databases) == 2
        assert cfg.databases[0].name == "db1"
        assert cfg.databases[1].name == "db2"

    def test_max_rows_and_allow_writes(self):
        data = {
            "databases": [
                {"name": "x", "type": "sqlite", "path": ":memory:"}
            ],
            "max_rows": 200,
            "allow_writes": True,
        }
        cfg = load_config_from_dict(data)
        assert cfg.max_rows == 200
        assert cfg.allow_writes is True

    def test_empty_databases(self):
        data = {"databases": []}
        cfg = load_config_from_dict(data)
        assert cfg.databases == []


class TestParseUrlToConfig:
    def test_parse_sqlite_url(self):
        cfg = _parse_url_to_config("sqlite:////tmp/mydb.db", "sqlite", True)
        assert cfg.name == "main"
        assert cfg.type == "sqlite"
        assert cfg.path == "/tmp/mydb.db"
        assert cfg.read_only is True

    def test_parse_sqlite_relative(self):
        cfg = _parse_url_to_config("sqlite:///relative.db", "sqlite", False)
        assert cfg.path == "relative.db"

    def test_parse_postgres_url(self):
        cfg = _parse_url_to_config(
            "postgres://user:pass@host.example.com:5433/mydb",
            "postgresql",
            True,
        )
        assert cfg.type == "postgresql"
        assert cfg.host == "host.example.com"
        assert cfg.port == 5433
        assert cfg.user == "user"
        assert cfg.password == "pass"
        assert cfg.database == "mydb"

    def test_parse_postgres_url_defaults(self):
        cfg = _parse_url_to_config("postgres://localhost/mydb", "postgresql", True)
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.user == "postgres"

    def test_parse_mysql_url(self):
        cfg = _parse_url_to_config(
            "mysql://root:secret@db.internal:3307/app",
            "mysql",
            False,
        )
        assert cfg.type == "mysql"
        assert cfg.host == "db.internal"
        assert cfg.port == 3307
        assert cfg.user == "root"
        assert cfg.password == "secret"
        assert cfg.database == "app"

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            _parse_url_to_config("oracle://localhost/db", "oracle", True)
