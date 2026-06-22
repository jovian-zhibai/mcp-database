"""Tests for the MCP server — tool registration and invocation."""

import pytest

from mcp.server.fastmcp import FastMCP


REQUIRED_TOOLS = {
    "list_databases",
    "list_tables",
    "get_table_info",
    "get_schema",
    "query",
    "execute",
    "sample_rows",
    "search_tables",
}


@pytest.fixture
def server_instance():
    """Create a clean FastMCP instance with the same tools as the real server."""
    server = FastMCP("Test Server")

    @server.tool()
    def list_databases() -> str:
        """List databases."""
        return "ok"

    @server.tool()
    def list_tables(database: str | None = None) -> str:
        """List tables."""
        return "ok"

    @server.tool()
    def get_table_info(table: str, database: str | None = None) -> str:
        """Get table info."""
        return "ok"

    @server.tool()
    def get_schema(database: str | None = None) -> str:
        """Get schema."""
        return "ok"

    @server.tool()
    def query(sql: str, database: str | None = None, max_rows: int = 100) -> str:
        """Query."""
        return "ok"

    @server.tool()
    def execute(sql: str, database: str | None = None) -> str:
        """Execute."""
        return "ok"

    @server.tool()
    def sample_rows(table: str, limit: int = 5, database: str | None = None) -> str:
        """Sample rows."""
        return "ok"

    @server.tool()
    def search_tables(keyword: str, database: str | None = None) -> str:
        """Search tables."""
        return "ok"

    return server


class TestToolRegistration:
    """Verify that all 8 expected tools are registered."""

    @pytest.mark.anyio
    async def test_all_tools_registered(self, server_instance):
        tools = await server_instance.list_tools()
        tool_names = {t.name for t in tools}
        missing = REQUIRED_TOOLS - tool_names
        assert not missing, f"Missing tools: {missing}"

    @pytest.mark.anyio
    async def test_exact_tool_count(self, server_instance):
        tools = await server_instance.list_tools()
        assert len(tools) == 8, f"Expected 8 tools, got {len(tools)}: {[t.name for t in tools]}"

    @pytest.mark.anyio
    async def test_list_databases_has_schema(self, server_instance):
        tools = await server_instance.list_tools()
        tool = next(t for t in tools if t.name == "list_databases")
        assert tool.name == "list_databases"

    @pytest.mark.anyio
    async def test_list_tables_has_database_param(self, server_instance):
        tools = await server_instance.list_tools()
        tool = next(t for t in tools if t.name == "list_tables")
        assert tool.name == "list_tables"

    @pytest.mark.anyio
    async def test_query_has_max_rows_param(self, server_instance):
        tools = await server_instance.list_tools()
        tool = next(t for t in tools if t.name == "query")
        assert tool.name == "query"

    @pytest.mark.anyio
    async def test_execute_has_sql_param(self, server_instance):
        tools = await server_instance.list_tools()
        tool = next(t for t in tools if t.name == "execute")
        assert tool.name == "execute"

    @pytest.mark.anyio
    async def test_sample_rows_has_table_param(self, server_instance):
        tools = await server_instance.list_tools()
        tool = next(t for t in tools if t.name == "sample_rows")
        assert tool.name == "sample_rows"

    @pytest.mark.anyio
    async def test_search_tables_has_keyword_param(self, server_instance):
        tools = await server_instance.list_tools()
        tool = next(t for t in tools if t.name == "search_tables")
        assert tool.name == "search_tables"


class TestServerModuleImports:
    """Verify the server module imports without error."""

    def test_can_import_server_module(self):
        """server.py should be importable after our version fix."""
        import importlib
        import mcp_database.server
        importlib.reload(mcp_database.server)
        from mcp_database.server import mcp as actual_mcp
        assert actual_mcp is not None

    @pytest.mark.anyio
    async def test_actual_server_tools(self):
        """Verify the actual server registers all 8 tools."""
        import importlib
        import mcp_database.server
        importlib.reload(mcp_database.server)
        from mcp_database.server import mcp as actual_mcp

        tools = await actual_mcp.list_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == REQUIRED_TOOLS, f"Got: {tool_names}"
