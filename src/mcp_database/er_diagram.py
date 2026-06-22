"""ER diagram generator — outputs Mermaid erDiagram format."""

from __future__ import annotations

from mcp_database.adapters.base import DatabaseAdapter


def generate_er_diagram(adapter: DatabaseAdapter, format: str = "mermaid") -> str:
    """Generate an ER diagram string for the given adapter.

    Args:
        adapter: Database adapter to introspect.
        format: Output format. Currently only "mermaid" is supported.

    Returns:
        Mermaid erDiagram string that can be rendered by Mermaid.js / Claude.
    """
    if format not in ("mermaid",):
        return f"Unsupported format: {format}. Use 'mermaid'."

    tables = adapter.list_tables()
    if not tables:
        return "No tables found."

    lines: list[str] = []
    relationships: list[str] = []

    # Track which columns are foreign keys per table
    fk_columns: dict[str, dict[str, list[str]]] = {}  # table -> {col: [ref_table, ref_col]}

    for table in tables:
        columns = adapter.get_columns(table)
        fks = adapter.get_constraints(table)

        # Build FK lookup
        for fk in fks:
            if table not in fk_columns:
                fk_columns[table] = {}
            fk_columns[table][fk["columns"][0]] = [fk["ref_table"], fk["ref_columns"][0]]

        # Entity definition
        lines.append(f"    {table} {{")
        for col in columns:
            parts = [col["type"]]
            if col.get("primary_key"):
                parts.append("PK")
            if col["name"] in fk_columns.get(table, {}):
                parts.append("FK")
            lines.append(f"        {col['type']} {col['name']} {' '.join(parts)}")
        lines.append("    }")

        # Relationships
        for fk in fks:
            ref = fk["ref_table"]
            # Basic cardinality: if FK column is also PK, use ||--||, otherwise ||--o{
            col_is_pk = any(
                c["name"] == fk["columns"][0] and c.get("primary_key")
                for c in columns
            )
            cardinality = "||--||" if col_is_pk else "||--o{"
            rel = f"    {table} {cardinality} {ref} : has"
            if rel not in relationships:
                relationships.append(rel)

    output = "erDiagram\n"
    output += "\n".join(lines) + "\n"
    if relationships:
        output += "\n".join(relationships) + "\n"
    else:
        output += "    %% No foreign key relationships found\n"

    return output
