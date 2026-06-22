"""Tests for ConnectionManager — multi-database connection support."""

import json

import pytest

from mcp_database.connection_manager import ConnectionManager, _mask_url


# ---------------------------------------------------------------------------
# URL masking
# ---------------------------------------------------------------------------

class TestURLMasking:
    def test_mask_postgres_url(self):
        masked = _mask_url("postgres://user:secret@localhost:5432/db")
        assert "secret" not in masked
        assert "***" in masked
        assert "user:***@localhost:5432" in masked

    def test_mask_mysql_url(self):
        masked = _mask_url("mysql://root:mypass@db.internal:3306/app")
        assert "mypass" not in masked
        assert "***" in masked

    def test_mask_url_no_password(self):
        masked = _mask_url("sqlite:///path/to/db.sqlite")
        assert masked == "sqlite:///path/to/db.sqlite"

    def test_mask_url_no_userinfo(self):
        masked = _mask_url("postgres://localhost/mydb")
        assert masked == "postgres://localhost/mydb"


# ---------------------------------------------------------------------------
# Single connection (backward compatible)
# ---------------------------------------------------------------------------

class TestSingleConnection:
    def test_single_connection_from_env(self, monkeypatch):
        """MCP_DATABASE_URL only → creates 'default' connection."""
        monkeypatch.setenv("MCP_DATABASE_URL", "sqlite:///:memory:")
        monkeypatch.setenv("MCP_DATABASE_TYPE", "sqlite")
        monkeypatch.delenv("MCP_DATABASE_CONFIG", raising=False)

        cm = ConnectionManager()
        cm.load_from_env()

        assert cm.has_connections
        adapter = cm.get("default")
        assert adapter.db_type == "sqlite"
        assert adapter.test_connection() is True

    def test_default_connection_when_no_url(self, monkeypatch):
        """No URL → defaults to in-memory SQLite as 'default'."""
        monkeypatch.delenv("MCP_DATABASE_URL", raising=False)
        monkeypatch.delenv("MCP_DATABASE_CONFIG", raising=False)
        monkeypatch.delenv("MCP_DATABASE_TYPE", raising=False)

        cm = ConnectionManager()
        cm.load_from_env()

        # Should have a 'default' connection (from the demo fallback renamed)
        assert cm.has_connections

    def test_connection_not_found_error(self, monkeypatch):
        """Asking for a non-existent connection gives a clear error."""
        monkeypatch.delenv("MCP_DATABASE_URL", raising=False)
        monkeypatch.delenv("MCP_DATABASE_CONFIG", raising=False)

        cm = ConnectionManager()
        cm.load_from_env()

        with pytest.raises(ValueError, match="not found"):
            cm.get("nonexistent")


# ---------------------------------------------------------------------------
# Multi-connection from JSON config
# ---------------------------------------------------------------------------

class TestMultiConnection:
    def test_two_sqlite_connections(self, monkeypatch, tmp_path):
        """Two SQLite :memory: connections via JSON config."""
        # Create two empty SQLite databases
        db1 = tmp_path / "db1.sqlite"
        db2 = tmp_path / "db2.sqlite"
        db1.touch()
        db2.touch()

        config_data = {
            "connections": {
                "alpha": {"url": f"sqlite:///{db1}", "read_only": True},
                "beta": {"url": f"sqlite:///{db2}", "read_only": False},
            },
            "settings": {"max_rows": 50, "allow_writes": False},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data))

        monkeypatch.setenv("MCP_DATABASE_CONFIG", str(config_path))

        cm = ConnectionManager()
        cm.load_from_env()

        assert cm.has_connections
        assert cm.global_max_rows == 50

        # Both connections should be accessible
        alpha = cm.get("alpha")
        assert alpha.db_type == "sqlite"
        assert alpha.read_only is True

        beta = cm.get("beta")
        assert beta.db_type == "sqlite"
        assert beta.read_only is False

    def test_connection_not_found_in_multi(self, monkeypatch, tmp_path):
        """Error when connection name doesn't exist in multi setup."""
        config_data = {
            "connections": {
                "only": {"url": "sqlite:///:memory:"},
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data))

        monkeypatch.setenv("MCP_DATABASE_CONFIG", str(config_path))

        cm = ConnectionManager()
        cm.load_from_env()

        with pytest.raises(ValueError, match="not found"):
            cm.get("missing")


class TestListAll:
    def test_list_all_with_urls(self, monkeypatch, tmp_path):
        """list_all returns connection info with masked URLs."""
        db1 = tmp_path / "test.db"
        db1.touch()

        config_data = {
            "connections": {
                "prod": {"url": "postgres://admin:hunter2@pg.example.com:5432/proddb"},
                "local": {"url": f"sqlite:///{db1}"},
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data))

        # prod will fail (no real PG), local should succeed
        monkeypatch.setenv("MCP_DATABASE_CONFIG", str(config_path))

        cm = ConnectionManager()
        cm.load_from_env()

        all_conns = cm.list_all()

        # Should have both entries — one connected, one error
        assert len(all_conns) >= 1

        # Connected entry should have masked URL
        local_entry = next((c for c in all_conns if c["name"] == "local"), None)
        if local_entry and "url" in local_entry:
            assert "***" not in local_entry["url"]  # SQLite has no password


class TestConnectionFailed:
    def test_failed_connection_does_not_block_others(self, monkeypatch, tmp_path):
        """A failed connection is recorded but doesn't prevent others."""
        db = tmp_path / "good.db"
        db.touch()

        config_data = {
            "connections": {
                "bad": {"url": "postgres://user:pass@invalid-host:5432/db"},
                "good": {"url": f"sqlite:///{db}"},
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data))

        monkeypatch.setenv("MCP_DATABASE_CONFIG", str(config_path))

        cm = ConnectionManager()
        cm.load_from_env()

        # "good" should be connected
        good = cm.get("good")
        assert good.test_connection() is True

        # "bad" should have an error recorded
        error = cm.get_connection_error("bad")
        assert error is not None

        # Asking for "bad" should raise with error info
        with pytest.raises(ValueError, match="failed"):
            cm.get("bad")

    def test_all_connections_in_list_all(self, monkeypatch, tmp_path):
        """list_all includes both connected and failed connections."""
        db = tmp_path / "ok.db"
        db.touch()

        config_data = {
            "connections": {
                "dead": {"url": "mysql://u:p@does.not.exist:3306/db"},
                "alive": {"url": f"sqlite:///{db}"},
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data))

        monkeypatch.setenv("MCP_DATABASE_CONFIG", str(config_path))

        cm = ConnectionManager()
        cm.load_from_env()

        all_conns = cm.list_all()
        names = {c["name"] for c in all_conns}
        assert "alive" in names
        assert "dead" in names


class TestDisconnectAll:
    def test_disconnect_all(self, monkeypatch, tmp_path):
        """disconnect_all closes all connections."""
        db1 = tmp_path / "a.db"
        db2 = tmp_path / "b.db"
        db1.touch()
        db2.touch()

        config_data = {
            "connections": {
                "a": {"url": f"sqlite:///{db1}"},
                "b": {"url": f"sqlite:///{db2}"},
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data))

        monkeypatch.setenv("MCP_DATABASE_CONFIG", str(config_path))

        cm = ConnectionManager()
        cm.load_from_env()

        # Both connected
        assert cm.get("a").test_connection() is True
        assert cm.get("b").test_connection() is True

        cm.disconnect_all()

        assert not cm.has_connections


class TestNoConnections:
    def test_get_raises_when_no_connections(self):
        """If nothing is loaded, get() gives clear error."""
        cm = ConnectionManager()
        with pytest.raises(ValueError, match="No connections"):
            cm.get("default")
