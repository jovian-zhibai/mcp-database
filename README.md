# mcp-database

[![PyPI](https://img.shields.io/pypi/v/mcp-database)](https://pypi.org/project/mcp-database/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-orange)](https://modelcontextprotocol.io)

**MCP server for multi-database access — query, inspect schema, and manage SQLite, PostgreSQL, and MySQL databases through Claude.**

## Why mcp-database?

| Problem | Solution |
|---------|----------|
| Need to query a database from Claude Code / Claude Desktop | One MCP server, multiple database support |
| Existing database MCP servers are JS/Go only | Pure Python, uses official `mcp` SDK |
| Worried about accidental writes | Read-only by default, writes opt-in |
| Don't know the schema | Built-in schema inspection, table info, search |

## Quick Start

```bash
# Install
pip install mcp-database

# Run with a SQLite database
MCP_DATABASE_URL=sqlite:///path/to/your.db mcp-database
```

### Claude Code Integration

```bash
# Add to Claude Code
claude mcp add mcp-database -- mcp-database

# Or with a specific database
claude mcp add mcp-database -e MCP_DATABASE_URL=sqlite:///path/to/db.sqlite -- mcp-database
```

### Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "database": {
      "command": "mcp-database",
      "env": {
        "MCP_DATABASE_URL": "sqlite:///path/to/your.db"
      }
    }
  }
}
```

## Supported Databases

| Database | Status | Install |
|----------|--------|---------|
| **SQLite** | Built-in | `pip install mcp-database` |
| **PostgreSQL** | Optional | `pip install 'mcp-database[postgres]'` |
| **MySQL** | Optional | `pip install 'mcp-database[mysql]'` |
| **All** | Optional | `pip install 'mcp-database[all]'` |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_DATABASE_URL` | `sqlite:///:memory:` | Database connection URL |
| `MCP_DATABASE_TYPE` | `sqlite` | Database type: `sqlite`, `postgresql`, `mysql` |
| `MCP_DATABASE_READ_ONLY` | `true` | Enable read-only mode |
| `MCP_MAX_ROWS` | `100` | Maximum rows returned per query |

### Connection URLs

```bash
# SQLite
MCP_DATABASE_URL=sqlite:///path/to/db.sqlite
MCP_DATABASE_URL=sqlite:///:memory:

# PostgreSQL
MCP_DATABASE_URL=postgres://user:password@localhost:5432/mydb
MCP_DATABASE_TYPE=postgresql

# MySQL
MCP_DATABASE_URL=mysql://user:password@localhost:3306/mydb
MCP_DATABASE_TYPE=mysql
```

## Available Tools

Once connected, Claude can use these tools:

| Tool | Description |
|------|-------------|
| `list_databases` | List all configured database connections |
| `list_tables` | List all tables in a database |
| `get_table_info` | Get detailed table info (columns, types, row count) |
| `get_schema` | Get full database schema (CREATE TABLE statements) |
| `query` | Execute a read-only SQL query (SELECT, SHOW, DESCRIBE) |
| `execute` | Execute a write statement (INSERT, UPDATE, DELETE) — opt-in only |
| `sample_rows` | Get sample rows from a table |
| `search_tables` | Search for tables or columns by keyword |

## Examples

Ask Claude things like:

- "What tables are in my database?"
- "Show me the schema for the users table"
- "Query the top 10 orders by amount"
- "Find all columns related to 'email'"
- "Sample some rows from the products table"

## Security

- **Read-only by default** — queries are safe, no data modification
- **Write opt-in** — set `allow_writes=True` and `MCP_DATABASE_READ_ONLY=false` to enable
- **Read-only detection** — write tool rejects SELECT statements (use `query` instead)
- **Row limits** — configurable max rows to prevent accidental large result sets

## Development

```bash
# Clone and install for development
git clone https://github.com/Jansen003/mcp-database.git
cd mcp-database
pip install -e ".[dev]"

# Run tests
pytest

# Run with Inspector UI
mcp dev src/mcp_database/server.py
```

## License

MIT — see [LICENSE](LICENSE).
