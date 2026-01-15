"""
Integration tests for dump command.

Tests cover the full dump functionality with real databases.
"""

from __future__ import annotations

import json

import pytest

from kenobix import KenobiX
from kenobix.cli.dump import (
    colorize_json,
    dump_table,
    format_compact,
    format_table,
    truncate_value,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_with_users(db_path):
    """Create database with user records."""
    db = KenobiX(str(db_path))
    users = db.collection("users")
    users.insert({"name": "Alice", "age": 30, "active": True, "email": "alice@example.com"})
    users.insert({"name": "Bob", "age": 25, "active": False, "email": "bob@gmail.com"})
    users.insert({"name": "Charlie", "age": 35, "active": True, "email": None})
    users.insert({"name": "Diana", "age": 28, "active": True, "email": "diana@example.com"})
    db.close()
    return db_path


@pytest.fixture
def db_with_nested(db_path):
    """Create database with nested records."""
    db = KenobiX(str(db_path))
    db.insert({
        "name": "Alice",
        "address": {"city": "Paris", "country": "France"},
        "tags": ["admin", "active"],
    })
    db.insert({
        "name": "Bob",
        "address": {"city": "London", "country": "UK"},
        "tags": ["user"],
    })
    db.insert({
        "name": "Charlie",
        "address": {"city": "Paris", "country": "France"},
        "tags": [],
    })
    db.close()
    return db_path


class TestDumpTableBasic:
    """Tests for basic dump_table functionality."""

    def test_dumps_all_records(self, db_with_users, capsys):
        """Should dump all records by default."""
        dump_table(str(db_with_users), "users", use_color=False)
        captured = capsys.readouterr()

        assert "[4/4 records]" in captured.out
        assert "Alice" in captured.out
        assert "Bob" in captured.out
        assert "Charlie" in captured.out
        assert "Diana" in captured.out

    def test_respects_limit(self, db_with_users, capsys):
        """Should respect limit parameter."""
        dump_table(str(db_with_users), "users", limit=2, use_color=False)
        captured = capsys.readouterr()

        assert "[2/4 records]" in captured.out

    def test_respects_offset(self, db_with_users, capsys):
        """Should respect offset parameter."""
        dump_table(str(db_with_users), "users", limit=2, offset=2, use_color=False)
        captured = capsys.readouterr()

        assert "[2/4 records]" in captured.out

    def test_one_flag(self, db_with_users, capsys):
        """Should show only one record with one=True."""
        dump_table(str(db_with_users), "users", one=True, use_color=False)
        captured = capsys.readouterr()

        assert "[1/4 records]" in captured.out

    def test_count_only(self, db_with_users, capsys):
        """Should show only count with count_only=True."""
        dump_table(str(db_with_users), "users", count_only=True)
        captured = capsys.readouterr()

        assert "4 records" in captured.out
        assert "Alice" not in captured.out


class TestDumpTableFiltering:
    """Tests for dump_table filtering with selectors."""

    def test_equals_filter(self, db_with_users, capsys):
        """Should filter by equals selector."""
        dump_table(str(db_with_users), "users", selectors=["name=Alice"], use_color=False)
        captured = capsys.readouterr()

        assert "[1/1 records]" in captured.out
        assert "Alice" in captured.out
        assert "Bob" not in captured.out

    def test_not_equals_filter(self, db_with_users, capsys):
        """Should filter by not equals selector."""
        dump_table(str(db_with_users), "users", selectors=["name!=Alice"], use_color=False)
        captured = capsys.readouterr()

        assert "[3/3 records]" in captured.out
        assert "Alice" not in captured.out

    def test_greater_than_filter(self, db_with_users, capsys):
        """Should filter by greater than selector."""
        dump_table(str(db_with_users), "users", selectors=["age>30"], use_color=False)
        captured = capsys.readouterr()

        assert "[1/1 records]" in captured.out
        assert "Charlie" in captured.out

    def test_less_than_filter(self, db_with_users, capsys):
        """Should filter by less than selector."""
        dump_table(str(db_with_users), "users", selectors=["age<28"], use_color=False)
        captured = capsys.readouterr()

        assert "[1/1 records]" in captured.out
        assert "Bob" in captured.out

    def test_boolean_filter(self, db_with_users, capsys):
        """Should filter by boolean selector."""
        dump_table(str(db_with_users), "users", selectors=["active=true"], use_color=False)
        captured = capsys.readouterr()

        assert "[3/3 records]" in captured.out
        assert "Bob" not in captured.out

    def test_null_filter(self, db_with_users, capsys):
        """Should filter by null selector."""
        dump_table(str(db_with_users), "users", selectors=["email=null"], use_color=False)
        captured = capsys.readouterr()

        assert "[1/1 records]" in captured.out
        assert "Charlie" in captured.out

    def test_not_null_filter(self, db_with_users, capsys):
        """Should filter by not null selector."""
        dump_table(str(db_with_users), "users", selectors=["email!=null"], use_color=False)
        captured = capsys.readouterr()

        assert "[3/3 records]" in captured.out
        assert "Charlie" not in captured.out

    def test_like_filter(self, db_with_users, capsys):
        """Should filter by LIKE selector."""
        dump_table(str(db_with_users), "users", selectors=["email~%@gmail.com"], use_color=False)
        captured = capsys.readouterr()

        assert "[1/1 records]" in captured.out
        assert "Bob" in captured.out

    def test_multiple_filters(self, db_with_users, capsys):
        """Should AND multiple selectors."""
        dump_table(str(db_with_users), "users", selectors=["active=true", "age>28"], use_color=False)
        captured = capsys.readouterr()

        assert "[2/2 records]" in captured.out
        assert "Alice" in captured.out
        assert "Charlie" in captured.out
        assert "Diana" not in captured.out

    def test_nested_field_filter(self, db_with_nested, capsys):
        """Should filter by nested field selector."""
        dump_table(str(db_with_nested), "documents", selectors=["address.city=Paris"], use_color=False)
        captured = capsys.readouterr()

        assert "[2/2 records]" in captured.out
        assert "Alice" in captured.out
        assert "Charlie" in captured.out
        assert "Bob" not in captured.out

    def test_no_matching_records(self, db_with_users, capsys):
        """Should handle no matching records gracefully."""
        dump_table(str(db_with_users), "users", selectors=["name=Nobody"], use_color=False)
        captured = capsys.readouterr()

        assert "no matching records" in captured.out

    def test_count_with_filter(self, db_with_users, capsys):
        """Should count only matching records."""
        dump_table(str(db_with_users), "users", selectors=["active=true"], count_only=True)
        captured = capsys.readouterr()

        assert "3 records" in captured.out


class TestDumpTableFormats:
    """Tests for dump_table output formats."""

    def test_json_format(self, db_with_users, capsys):
        """Should output pretty JSON by default."""
        dump_table(str(db_with_users), "users", limit=1, output_format="json", use_color=False)
        captured = capsys.readouterr()

        # Should have indentation
        assert "  " in captured.out
        assert '"name"' in captured.out or "'name'" in captured.out

    def test_table_format(self, db_with_users, capsys):
        """Should output table format."""
        dump_table(str(db_with_users), "users", output_format="table", use_color=False)
        captured = capsys.readouterr()

        # Should have column headers
        assert "name" in captured.out
        assert "age" in captured.out
        # Should have separator line
        assert "───" in captured.out

    def test_compact_format(self, db_with_users, capsys):
        """Should output one JSON per line."""
        dump_table(str(db_with_users), "users", output_format="compact", use_color=False)
        captured = capsys.readouterr()

        lines = [l for l in captured.out.strip().split("\n") if l]
        assert len(lines) == 4
        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "_id" in data


class TestDumpTableEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_table_exits(self, db_with_users, capsys):
        """Should exit with error for invalid table."""
        with pytest.raises(SystemExit) as exc_info:
            dump_table(str(db_with_users), "nonexistent", use_color=False)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_invalid_selector_exits(self, db_with_users, capsys):
        """Should exit with error for invalid selector."""
        with pytest.raises(SystemExit) as exc_info:
            dump_table(str(db_with_users), "users", selectors=["invalid"], use_color=False)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid" in captured.err

    def test_empty_table(self, db_path, capsys):
        """Should handle empty table gracefully."""
        # Create an empty table by executing SQL directly
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE empty_table (id INTEGER PRIMARY KEY, data TEXT)")
        conn.commit()
        conn.close()

        dump_table(str(db_path), "empty_table", use_color=False)
        captured = capsys.readouterr()
        assert "no matching records" in captured.out


class TestFormatFunctions:
    """Tests for formatting helper functions."""

    def test_truncate_value_short(self):
        """Should not truncate short values."""
        assert truncate_value("hello", 10) == "hello"

    def test_truncate_value_long(self):
        """Should truncate long values with ellipsis."""
        result = truncate_value("this is a very long string", 10)
        assert len(result) == 10
        assert result.endswith("...")

    def test_colorize_json_no_color(self):
        """Should format JSON without colors."""
        data = {"name": "Alice", "age": 30}
        result = colorize_json(data, use_color=False)
        assert '"name"' in result
        assert '"Alice"' in result
        assert "30" in result

    def test_colorize_json_with_color(self):
        """Should include ANSI codes when color enabled."""
        data = {"name": "Alice"}
        result = colorize_json(data, use_color=True)
        # Should contain ANSI escape codes
        assert "\033[" in result

    def test_format_table_empty(self):
        """Should handle empty records list."""
        result = format_table([], use_color=False)
        assert "no records" in result

    def test_format_table_with_records(self):
        """Should format records as table."""
        records = [
            {"_id": 1, "name": "Alice", "age": 30},
            {"_id": 2, "name": "Bob", "age": 25},
        ]
        result = format_table(records, use_color=False)
        assert "name" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_format_compact(self):
        """Should format as one JSON per line."""
        records = [
            {"_id": 1, "name": "Alice"},
            {"_id": 2, "name": "Bob"},
        ]
        result = format_compact(records)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["name"] == "Alice"
        assert json.loads(lines[1])["name"] == "Bob"


class TestDumpTableWithCollections:
    """Tests for dump with multiple collections."""

    def test_dumps_correct_collection(self, db_path, capsys):
        """Should dump only the specified collection."""
        db = KenobiX(str(db_path))
        users = db.collection("users")
        posts = db.collection("posts")
        users.insert({"name": "User1"})
        users.insert({"name": "User2"})
        posts.insert({"title": "Post1"})
        db.close()

        dump_table(str(db_path), "users", use_color=False)
        captured = capsys.readouterr()

        assert "[2/2 records]" in captured.out
        assert "User1" in captured.out
        assert "Post1" not in captured.out
