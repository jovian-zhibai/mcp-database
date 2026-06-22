"""Tests for MongoDB adapter — requires pymongo and a running MongoDB instance."""

import pytest

try:
    from mcp_database.adapters.mongodb import MongoDBAdapter
    HAS_ADAPTER = True
except ImportError:
    HAS_ADAPTER = False

try:
    import pymongo  # noqa: F401
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

pytestmark = pytest.mark.skipif(
    not (HAS_ADAPTER and HAS_PYMONGO),
    reason="pymongo not installed. Install with: pip install 'mcp-database[mongodb]'",
)


class TestMongoDBAdapterInit:
    def test_default_values(self):
        adapter = MongoDBAdapter()
        assert adapter.host == "localhost"
        assert adapter.port == 27017
        assert adapter.default_database == "test"
        assert adapter.read_only is True
        assert adapter.db_type == "mongodb"

    def test_custom_values(self):
        adapter = MongoDBAdapter(
            host="mongo.example.com",
            port=27018,
            user="admin",
            password="secret",
            database="mydb",
            read_only=False,
        )
        assert adapter.host == "mongo.example.com"
        assert adapter.port == 27018
        assert adapter.default_database == "mydb"
        assert adapter.read_only is False


class TestMongoDBAdapterNotConnected:
    def test_test_connection_returns_false(self):
        adapter = MongoDBAdapter()
        assert adapter.test_connection() is False
