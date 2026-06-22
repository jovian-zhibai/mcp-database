# mcp-database

[![PyPI](https://img.shields.io/pypi/v/mcp-database)](https://pypi.org/project/mcp-database/)
[![CI](https://github.com/jovian-zhibai/mcp-database/actions/workflows/ci.yml/badge.svg)](https://github.com/jovian-zhibai/mcp-database/actions/workflows/ci.yml)
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

## Why mcp-database? (vs alternatives)

| Feature | mcp-database | @modelcontextprotocol/sqlite | Other MCP DB Servers |
|---------|:-----------:|:----------------------------:|:--------------------:|
| Multi-database (SQLite + PG + MySQL) | ✅ | ❌ SQLite only | Varies |
| Multi-connection | ✅ | ❌ | ❌ |
| Schema diff | ✅ | ❌ | ❌ |
| ER diagram (Mermaid) | ✅ | ❌ | ❌ |
| Health check | ✅ | ❌ | ❌ |
| Explain query | ✅ | ❌ | ❌ |
| Data masking | ✅ | ❌ | ❌ |
| Query timeout | ✅ | ❌ | ❌ |
| Read-only default | ✅ | ✅ | Varies |
| Pure Python | ✅ | ❌ (TypeScript) | Varies |

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

### Cursor Integration

Add to your Cursor MCP settings (Settings → MCP):

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

### Windsurf Integration

Add to `~/.codeium/windsurf/mcp_config.json`:

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

### Other MCP-Compatible Tools

mcp-database works with any tool that supports the MCP protocol.
The configuration pattern is the same: point the tool to the
`mcp-database` command and set `MCP_DATABASE_URL`.

## Supported Databases

| Database | Status | Install |
|----------|--------|---------|
| **SQLite** | Built-in | `pip install mcp-database` |
| **PostgreSQL** | Optional | `pip install 'mcp-database[postgres]'` |
| **MySQL** | Optional | `pip install 'mcp-database[mysql]'` |
| **MongoDB** | Preview | `pip install 'mcp-database[mongodb]'` |
| **All** | Optional | `pip install 'mcp-database[all]'` |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_DATABASE_URL` | `sqlite:///:memory:` | Database connection URL |
| `MCP_DATABASE_TYPE` | `sqlite` | Database type: `sqlite`, `postgresql`, `mysql` |
| `MCP_DATABASE_READ_ONLY` | `true` | Enable read-only mode |
| `MCP_MAX_ROWS` | `100` | Maximum rows returned per query |
| `MCP_QUERY_TIMEOUT` | `30` | Query timeout in seconds |
| `MCP_MASK_SENSITIVE` | `false` | Mask sensitive columns (email, phone, token, etc.) |
| `MCP_DATABASE_CONFIG` | — | Path to JSON config file for multiple connections |

### Multiple Connections

To connect to multiple databases simultaneously, create a JSON config file:

```json
{
  "connections": {
    "prod": {"url": "postgres://user:pass@host:5432/db", "read_only": true},
    "staging": {"url": "postgres://user:pass@host:5432/staging", "read_only": true},
    "local": {"url": "sqlite:///dev.db", "read_only": false}
  },
  "settings": {
    "max_rows": 100,
    "allow_writes": false
  }
}
```

Set `MCP_DATABASE_CONFIG` to the file path. All tools accept an optional `connection_name` parameter (defaults to `"default"`).

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
| `schema_diff` | Compare schemas between two database connections |
| `check_health` | Get database health metrics (table count, row counts, latency) |
| `generate_er_diagram` | Generate Mermaid ER diagram from database schema |
| `explain_query` | Explain the execution plan for a SELECT query |
| `diagnose_connection` | Diagnose connection issues with troubleshooting hints |

## Examples

Ask Claude things like:

- "What tables are in my database?"
- "Show me the schema for the users table"
- "Query the top 10 orders by amount"
- "Find all columns related to 'email'"
- "Sample some rows from the products table"
- "Compare schemas between staging and production"
- "Generate an ER diagram for my database"
- "How large are my tables?"

## Security

- **Read-only by default** — queries are safe, no data modification
- **Write opt-in** — set `allow_writes=True` and `MCP_DATABASE_READ_ONLY=false` to enable
- **Read-only detection** — write tool rejects SELECT statements (use `query` instead)
- **Row limits** — configurable max rows to prevent accidental large result sets
- **Query timeout** — configurable timeout (default 30s) to prevent slow queries from blocking
- **Data masking** — optionally mask sensitive columns (emails, phones, tokens) with `MCP_MASK_SENSITIVE=true`

## Integration with Mergewall

Use mcp-database as the storage backend for
[Mergewall](https://github.com/jovian-zhibai/Mergewall) audit data:

```bash
# 1. Create audit database
MCP_DATABASE_URL=sqlite:///mergewall-audit.db mcp-database

# 2. Ask Claude: "Create the mergewall_audit table using the schema resource"
# 3. Configure Mergewall to export audit data
#    (See Mergewall docs for database export configuration)
```

This gives you SQL-queryable governance history instead of flat JSONL files.

## Development

```bash
# Clone and install for development
git clone https://github.com/jovian-zhibai/mcp-database.git
cd mcp-database
pip install -e ".[dev]"

# Run tests
pytest

# Run with Inspector UI
mcp dev src/mcp_database/server.py
```

## License

MIT — see [LICENSE](LICENSE).
