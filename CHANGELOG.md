# Changelog

## 0.2.0 (2026-06-22)

### Added
- Multi-database connection support via JSON config (`MCP_DATABASE_CONFIG`)
- `schema_diff` tool for cross-database schema comparison
- `check_health` tool for database diagnostics (latency, table count, row counts, largest tables)
- `generate_er_diagram` tool with Mermaid erDiagram output
- `explain_query` tool for query plan analysis (EXPLAIN QUERY PLAN / FORMAT=JSON)
- Query timeout protection (`MCP_QUERY_TIMEOUT`, default 30s)
- Data masking for sensitive columns (`MCP_MASK_SENSITIVE`)
- Competitive comparison table in README
- CONTRIBUTING.md and .editorconfig
- GitHub Actions CI with Python 3.10/3.11/3.12 matrix
- PyPI auto-publish workflow on tag push

### Fixed
- CI pipeline reliability (removed anyio marker conflicts, added test timeout)
- Git history unified to single author (jovian-zhibai)
- README references unified to jovian-zhibai
- JSON config error handling (missing url field, bad syntax)
- Environment variable type conversion errors

## 0.1.0 (2026-05-28)

### Added
- Initial release
- SQLite, PostgreSQL, MySQL adapter support
- 8 MCP tools: list_databases, list_tables, get_table_info, get_schema, query, execute, sample_rows, search_tables
- Read-only by default with write opt-in
- Environment variable configuration (MCP_DATABASE_URL, MCP_DATABASE_TYPE, MCP_DATABASE_READ_ONLY, MCP_MAX_ROWS)
