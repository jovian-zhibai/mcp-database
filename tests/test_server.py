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
    "schema_diff",
    "check_health",
    "generate_er_diagram",
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

    @server.tool()
    def schema_diff(source_connection: str, target_connection: str, table_name: str = "") -> str:
        """Schema diff."""
        return "ok"

    @server.tool()
    def check_health(connection_name: str = "default") -> str:
        """Health check."""
        return "ok"

    @server.tool()
    def generate_er_diagram(connection_name: str = "default", format: str = "mermaid") -> str:
        """ER diagram."""
        return "ok"

    return server


class TestToolRegistration:
    """Verify that all 11 expected tools are registered on a fresh server instance."""

    @pytest.mark.anyio
    async def test_all_tools_registered(self, server_instance):
        tools = await server_instance.list_tools()
        tool_names = {t.name for t in tools}
        missing = REQUIRED_TOOLS - tool_names
        assert not missing, f"Missing tools: {missing}"

    @pytest.mark.anyio
    async def test_exact_tool_count(self, server_instance):
        tools = await server_instance.list_tools()
        assert len(tools) == 11, f"Expected 11 tools, got {len(tools)}: {[t.name for t in tools]}"

    @pytest.mark.anyio
    async def test_list_databases_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "list_databases" for t in tools)

    @pytest.mark.anyio
    async def test_list_tables_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "list_tables" for t in tools)

    @pytest.mark.anyio
    async def test_query_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "query" for t in tools)

    @pytest.mark.anyio
    async def test_execute_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "execute" for t in tools)

    @pytest.mark.anyio
    async def test_sample_rows_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "sample_rows" for t in tools)

    @pytest.mark.anyio
    async def test_search_tables_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "search_tables" for t in tools)

    @pytest.mark.anyio
    async def test_schema_diff_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "schema_diff" for t in tools)

    @pytest.mark.anyio
    async def test_check_health_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "check_health" for t in tools)

    @pytest.mark.anyio
    async def test_generate_er_diagram_present(self, server_instance):
        tools = await server_instance.list_tools()
        assert any(t.name == "generate_er_diagram" for t in tools)


class TestServerModuleImport:
    """Verify the real server module can be imported cleanly (once)."""

    def test_can_import_server_module(self):
        """server.py should import without error."""
        from mcp_database.server import mcp as actual_mcp
        assert actual_mcp is not None
        assert actual_mcp.name == "Database Server"

    @pytest.mark.anyio
    async def test_actual_server_tools_match_expected(self):
        """Verify the real server registers exactly the 11 expected tools."""
        from mcp_database.server import mcp as actual_mcp

        tools = await actual_mcp.list_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == REQUIRED_TOOLS, f"Got: {tool_names}"
