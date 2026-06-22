"""Tests for MySQL adapter — requires pymysql and a running MySQL instance."""

import pytest

# Try importing the adapter
try:
    from mcp_database.adapters.mysql import MySQLAdapter
    HAS_ADAPTER = True
except ImportError:
    HAS_ADAPTER = False

# Check if pymysql is available
try:
    import pymysql  # noqa: F401
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


pytestmark = pytest.mark.skipif(
    not (HAS_ADAPTER and HAS_PYMYSQL),
    reason="pymysql not installed. Install with: pip install 'mcp-database[mysql]'",
)


class TestMySQLAdapterInit:
    def test_default_values(self):
        adapter = MySQLAdapter()
        assert adapter.host == "localhost"
        assert adapter.port == 3306
        assert adapter.user == "root"
        assert adapter.default_database == ""
        assert adapter.read_only is True
        assert adapter.db_type == "mysql"

    def test_custom_values(self):
        adapter = MySQLAdapter(
            host="mysql.example.com",
            port=3307,
            user="admin",
            password="secret",
            database="mydb",
            read_only=False,
        )
        assert adapter.host == "mysql.example.com"
        assert adapter.port == 3307
        assert adapter.user == "admin"
        assert adapter.default_database == "mydb"
        assert adapter.read_only is False


class TestMySQLAdapterNotConnected:
    def test_get_conn_raises_when_not_connected(self):
        adapter = MySQLAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            adapter._get_conn()

    def test_test_connection_returns_false_when_not_connected(self):
        adapter = MySQLAdapter()
        assert adapter.test_connection() is False


# Integration tests — require a real MySQL database
@pytest.mark.skipif(
    not (HAS_ADAPTER and HAS_PYMYSQL),
    reason="Requires MySQL database. Set MYSQL_TEST_DSN to run.",
)
class TestMySQLAdapterIntegration:
    """These tests require a real MySQL connection.
    
    Set MYSQL_TEST_DSN env var with connection string, e.g.:
        MYSQL_TEST_DSN=mysql://user:pass@localhost:3306/testdb
    """

    @pytest.fixture
    def mysql_adapter(self):
        import os
        dsn = os.environ.get("MYSQL_TEST_DSN")
        if not dsn:
            pytest.skip("MYSQL_TEST_DSN not set")

        from urllib.parse import urlparse
        parsed = urlparse(dsn)
        adapter = MySQLAdapter(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=parsed.path.lstrip("/") or "",
            read_only=True,
        )
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_connect_and_disconnect(self, mysql_adapter):
        assert mysql_adapter.test_connection() is True

    def test_list_tables(self, mysql_adapter):
        tables = mysql_adapter.list_tables()
        assert isinstance(tables, list)

    def test_execute_query(self, mysql_adapter):
        result = mysql_adapter.execute_query("SELECT 1 AS num")
        assert result.columns == ["num"]
        assert result.rows[0][0] == 1
