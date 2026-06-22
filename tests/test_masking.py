"""Tests for sensitive data masking."""

import sqlite3


from mcp_database.adapters.sqlite import SQLiteAdapter
from mcp_database.masking import is_sensitive_column, mask_value, mask_sensitive_columns


class TestIsSensitiveColumn:
    def test_email_is_sensitive(self):
        assert is_sensitive_column("email") is True

    def test_phone_is_sensitive(self):
        assert is_sensitive_column("phone") is True

    def test_password_is_sensitive(self):
        assert is_sensitive_column("password") is True

    def test_token_is_sensitive(self):
        assert is_sensitive_column("api_key") is True

    def test_name_is_not_sensitive(self):
        assert is_sensitive_column("name") is False

    def test_id_is_not_sensitive(self):
        assert is_sensitive_column("id") is False

    def test_amount_is_not_sensitive(self):
        assert is_sensitive_column("amount") is False

    def test_user_email_is_sensitive(self):
        assert is_sensitive_column("user_email") is True

    def test_billing_phone_is_sensitive(self):
        assert is_sensitive_column("billing_phone") is True


class TestMaskValue:
    def test_mask_email(self):
        masked = mask_value("john.doe@gmail.com", "email")
        assert "john.doe" not in masked
        assert "***" in masked
        assert "@gmail.com" in masked

    def test_mask_email_short(self):
        masked = mask_value("a@b.com", "email")
        # Short local part (≤2 chars): fully starred
        assert "@b.com" in masked
        assert "a" not in masked

    def test_mask_phone(self):
        masked = mask_value("13812345678", "phone")
        assert "138****5678" in masked

    def test_mask_default(self):
        masked = mask_value("abcdefgh", "secret_token")
        assert "ab***gh" in masked or "***" in masked

    def test_mask_none(self):
        assert mask_value(None, "email") is None

    def test_mask_empty(self):
        assert mask_value("", "email") == ""


class TestMaskColumns:
    def test_mask_email_column(self):
        columns = ["id", "name", "email"]
        rows = [
            [1, "Alice", "alice@test.com"],
            [2, "Bob", "bob@test.com"],
        ]
        masked = mask_sensitive_columns(columns, rows)
        assert masked[0][0] == 1  # id unchanged
        assert masked[0][1] == "Alice"  # name unchanged
        assert "alice@test.com" not in str(masked[0][2])  # email masked

    def test_no_sensitive_columns_unchanged(self):
        columns = ["id", "name", "age"]
        rows = [[1, "Alice", 30]]
        masked = mask_sensitive_columns(columns, rows)
        assert masked == rows

    def test_multiple_sensitive_columns(self):
        columns = ["id", "email", "phone"]
        rows = [[1, "alice@test.com", "13812345678"]]
        masked = mask_sensitive_columns(columns, rows)
        assert "alice" not in str(masked[0][1])
        assert "13812345678" not in str(masked[0][2])


class TestMaskingIntegration:
    """Integration test: query with mask_sensitive via the masking module."""

    def test_query_output_masking(self, tmp_path):
        db_path = tmp_path / "mask.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT)")
        conn.execute("INSERT INTO users (name, email, phone) VALUES ('Alice', 'alice@test.com', '13812345678')")
        conn.commit()
        conn.close()

        adapter = SQLiteAdapter(database_path=str(db_path), read_only=True)
        adapter.connect()

        result = adapter.execute_query("SELECT * FROM users")
        # Apply masking
        result.rows = mask_sensitive_columns(result.columns, result.rows)

        output = result.to_table()
        assert "alice@test.com" not in output
        assert "13812345678" not in output
        assert "***" in output
        assert "Alice" in output  # name not masked

        adapter.disconnect()
