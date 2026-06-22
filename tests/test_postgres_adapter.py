"""Tests for PostgreSQL adapter — requires psycopg2 and a running PostgreSQL instance."""

import pytest

# Try importing the adapter
try:
    from mcp_database.adapters.postgres import PostgreSQLAdapter
    HAS_ADAPTER = True
except ImportError:
    HAS_ADAPTER = False

# Check if psycopg2 is available
try:
    import psycopg2  # noqa: F401
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


pytestmark = pytest.mark.skipif(
    not (HAS_ADAPTER and HAS_PSYCOPG2),
    reason="psycopg2 not installed. Install with: pip install 'mcp-database[postgres]'",
)


class TestPostgreSQLAdapterInit:
    def test_default_values(self):
        adapter = PostgreSQLAdapter()
        assert adapter.host == "localhost"
        assert adapter.port == 5432
        assert adapter.user == "postgres"
        assert adapter.default_database == "postgres"
        assert adapter.read_only is True
        assert adapter.db_type == "postgresql"

    def test_custom_values(self):
        adapter = PostgreSQLAdapter(
            host="pg.example.com",
            port=5433,
            user="admin",
            password="secret",
            database="mydb",
            read_only=False,
        )
        assert adapter.host == "pg.example.com"
        assert adapter.port == 5433
        assert adapter.user == "admin"
        assert adapter.default_database == "mydb"
        assert adapter.read_only is False


class TestPostgreSQLAdapterNotConnected:
    def test_get_conn_raises_when_not_connected(self):
        adapter = PostgreSQLAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            adapter._get_conn()

    def test_test_connection_returns_false_when_not_connected(self):
        adapter = PostgreSQLAdapter()
        assert adapter.test_connection() is False


# Integration tests — require a real PostgreSQL database
@pytest.mark.skipif(
    not (HAS_ADAPTER and HAS_PSYCOPG2),
    reason="Requires PostgreSQL database. Set PG_TEST_DSN to run.",
)
class TestPostgreSQLAdapterIntegration:
    """These tests require a real PostgreSQL connection.
    
    Set PG_TEST_DSN env var with connection string, e.g.:
        PG_TEST_DSN=postgres://user:pass@localhost:5432/testdb
    """

    @pytest.fixture
    def pg_adapter(self):
        import os
        dsn = os.environ.get("PG_TEST_DSN")
        if not dsn:
            pytest.skip("PG_TEST_DSN not set")

        from urllib.parse import urlparse
        parsed = urlparse(dsn)
        adapter = PostgreSQLAdapter(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            user=parsed.username or "postgres",
            password=parsed.password or "",
            database=parsed.path.lstrip("/") or "postgres",
            read_only=True,
        )
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_connect_and_disconnect(self, pg_adapter):
        assert pg_adapter.test_connection() is True

    def test_list_tables(self, pg_adapter):
        tables = pg_adapter.list_tables()
        assert isinstance(tables, list)

    def test_execute_query(self, pg_adapter):
        result = pg_adapter.execute_query("SELECT 1 AS num")
        assert result.columns == ["num"]
        assert result.rows[0][0] == 1
