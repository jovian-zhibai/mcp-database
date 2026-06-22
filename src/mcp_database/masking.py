"""Sensitive data masking for query results.

Detects columns with sensitive names (email, phone, password, etc.)
and masks their values before display.
"""

from __future__ import annotations


# Columns matching these keywords will be masked
_SENSITIVE_KEYWORDS = {
    "email", "mail",
    "phone", "mobile", "tel", "telephone",
    "password", "passwd", "pwd", "secret",
    "ssn", "social_security",
    "card_number", "credit_card", "debit_card",
    "token", "api_key", "apikey", "access_token", "refresh_token",
    "id_card", "id_number", "passport",
}


def is_sensitive_column(col_name: str) -> bool:
    """Check if a column name indicates sensitive data."""
    normalized = col_name.lower().replace("-", "_").replace(" ", "_")
    # Exact match
    if normalized in _SENSITIVE_KEYWORDS:
        return True
    # Contains keyword (e.g., user_email, billing_phone)
    for keyword in _SENSITIVE_KEYWORDS:
        if f"_{keyword}" in normalized or normalized.endswith(f"_{keyword}"):
            return True
    return False


def mask_value(value, col_name: str) -> str:
    """Mask a single value.

    Email: j***@gmail.com
    Phone: 138****1234
    Other: first 2 + *** + last 2
    """
    if value is None:
        return None

    s = str(value)
    if not s:
        return s

    lower_col = col_name.lower()

    # Email pattern
    if "email" in lower_col or "mail" in lower_col:
        if "@" in s:
            parts = s.split("@")
            local = parts[0]
            if len(local) <= 2:
                return f"{'*' * len(local)}@{parts[1]}"
            return f"{local[0]}***@{parts[1]}"

    # Phone pattern
    if "phone" in lower_col or "mobile" in lower_col or "tel" in lower_col:
        if len(s) >= 7:
            return s[:3] + "****" + s[-4:]

    # Default: keep first 2 and last 2
    if len(s) <= 4:
        return "***"
    return s[:2] + "***" + s[-2:]


def mask_sensitive_columns(columns: list[str], rows: list[list]) -> list[list]:
    """Mask sensitive columns in query results.

    Args:
        columns: Column names.
        rows: List of rows (each row is a list of values).

    Returns:
        New list of rows with sensitive values masked.
    """
    # Find which column indices need masking
    sensitive_indices = {
        i for i, col in enumerate(columns) if is_sensitive_column(col)
    }
    if not sensitive_indices:
        return rows

    masked_rows = []
    for row in rows:
        masked_row = list(row)
        for i in sensitive_indices:
            if i < len(masked_row):
                masked_row[i] = mask_value(masked_row[i], columns[i])
        masked_rows.append(masked_row)

    return masked_rows
