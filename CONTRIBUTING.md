# Contributing to mcp-database

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/jovian-zhibai/mcp-database.git
cd mcp-database
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_sqlite_adapter.py -v

# Run with coverage (requires pytest-cov)
pip install pytest-cov
pytest --cov=mcp_database tests/
```

## Code Quality

We use ruff for linting and formatting:

```bash
ruff check src/ tests/
```

CI will run both pytest and ruff on every push and pull request.

## Adding a New Database Adapter

1. Create `src/mcp_database/adapters/your_db.py`
2. Inherit from `DatabaseAdapter` in `adapters/base.py`
3. Implement all abstract methods:
   - `connect()` / `disconnect()` / `test_connection()`
   - `list_databases()` / `list_tables()`
   - `get_table_info()` / `get_schema()`
   - `get_columns()` / `get_indexes()` / `get_constraints()`
   - `get_health()`
   - `execute_query()` / `execute_write()`
   - `db_type` property
4. Register the adapter in `adapters/__init__.py`
5. Add optional dependency in `pyproject.toml` under `[project.optional-dependencies]`
6. Add tests in `tests/test_your_db_adapter.py` with `@pytest.mark.skipif` for environments without the database

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation
- `test:` — adding or updating tests
- `ci:` — CI/CD changes
- `chore:` — other maintenance

## Architecture

```
src/mcp_database/
  __init__.py              # Version info
  server.py                # MCP server entry point (11 tools)
  config.py                # Configuration loading
  connection_manager.py    # Multi-database connection manager
  schema_diff.py           # Cross-database schema comparison
  er_diagram.py            # ER diagram generation (Mermaid format)
  adapters/
    base.py                # Abstract base adapter
    sqlite.py              # SQLite adapter (stdlib)
    postgres.py            # PostgreSQL adapter (psycopg2)
    mysql.py               # MySQL adapter (pymysql)
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
