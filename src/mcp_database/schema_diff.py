"""Schema diff tool — compare table schemas across database connections."""

from __future__ import annotations


from mcp_database.adapters.base import DatabaseAdapter


def diff_schemas(
    source: DatabaseAdapter,
    target: DatabaseAdapter,
    table_name: str | None = None,
) -> dict:
    """Compare schemas between two database adapters.

    Args:
        source: Source database adapter (reference).
        target: Target database adapter (comparison).
        table_name: Optional table name to diff. If None, diff all tables.

    Returns:
        dict with keys: tables_only_in_source, tables_only_in_target,
        modified_tables, identical_tables.
    """
    # Get table lists
    source_tables = source.list_tables()
    target_tables = target.list_tables()

    if table_name:
        if table_name not in source_tables and table_name not in target_tables:
            return {"error": f"Table '{table_name}' not found in either database."}
        source_tables = [t for t in source_tables if t == table_name]
        target_tables = [t for t in target_tables if t == table_name]

    src_set = set(source_tables)
    tgt_set = set(target_tables)

    tables_only_in_source = sorted(src_set - tgt_set)
    tables_only_in_target = sorted(tgt_set - src_set)
    common_tables = sorted(src_set & tgt_set)

    modified_tables: dict[str, dict] = {}
    identical_tables: list[str] = []

    for table in common_tables:
        src_cols = {c["name"]: c for c in source.get_columns(table)}
        tgt_cols = {c["name"]: c for c in target.get_columns(table)}

        src_col_names = set(src_cols.keys())
        tgt_col_names = set(tgt_cols.keys())

        columns_added = sorted(tgt_col_names - src_col_names)
        columns_removed = sorted(src_col_names - tgt_col_names)
        common_cols = sorted(src_col_names & tgt_col_names)

        columns_modified = []
        for col_name in common_cols:
            sc = src_cols[col_name]
            tc = tgt_cols[col_name]

            # Compare type and nullable
            type_changed = sc["type"].upper() != tc["type"].upper()
            nullable_changed = sc.get("nullable", True) != tc.get("nullable", True)

            if type_changed or nullable_changed:
                columns_modified.append({
                    "name": col_name,
                    "source_type": sc["type"],
                    "target_type": tc["type"],
                    "source_nullable": sc.get("nullable", True),
                    "target_nullable": tc.get("nullable", True),
                })

        if columns_added or columns_removed or columns_modified:
            table_diff: dict = {}
            if columns_added:
                table_diff["columns_added"] = [
                    {"name": cn, "type": tgt_cols[cn]["type"],
                     "nullable": tgt_cols[cn].get("nullable", True)}
                    for cn in columns_added
                ]
            if columns_removed:
                table_diff["columns_removed"] = [
                    {"name": cn, "type": src_cols[cn]["type"],
                     "nullable": src_cols[cn].get("nullable", True)}
                    for cn in columns_removed
                ]
            if columns_modified:
                table_diff["columns_modified"] = columns_modified
            modified_tables[table] = table_diff
        else:
            identical_tables.append(table)

    return {
        "tables_only_in_source": tables_only_in_source,
        "tables_only_in_target": tables_only_in_target,
        "modified_tables": modified_tables,
        "identical_tables": identical_tables,
    }
