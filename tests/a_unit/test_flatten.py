"""
Unit tests for record flattening functions.

These tests verify pure functions without database dependencies.
"""

from __future__ import annotations

import json

import pytest

from kenobix.cli.export import (
    escape_sql_identifier,
    escape_sql_value,
    flatten_record,
    flatten_value,
    get_all_columns,
    infer_sql_type,
)


class TestFlattenValue:
    """Tests for flatten_value function."""

    def test_primitive_value(self):
        """Should return primitive values with prefix key."""
        assert flatten_value("hello", "name") == {"name": "hello"}
        assert flatten_value(42, "age") == {"age": 42}
        assert flatten_value(True, "active") == {"active": True}

    def test_nested_dict(self):
        """Should flatten nested dict with double underscore notation."""
        value = {"city": "Paris", "country": "France"}
        result = flatten_value(value, "address")
        assert result == {"address.city": "Paris", "address.country": "France"}

    def test_deeply_nested_dict(self):
        """Should flatten deeply nested dicts."""
        value = {"geo": {"lat": 48.8, "lng": 2.3}}
        result = flatten_value(value, "location")
        assert result == {"location.geo.lat": 48.8, "location.geo.lng": 2.3}

    def test_list_value(self):
        """Should convert list to JSON string."""
        value = [1, 2, 3]
        result = flatten_value(value, "items")
        assert result == {"items": "[1, 2, 3]"}

    def test_empty_prefix(self):
        """Should handle empty prefix for top-level dict."""
        value = {"a": 1, "b": 2}
        result = flatten_value(value, "")
        assert result == {"a": 1, "b": 2}


class TestFlattenRecord:
    """Tests for flatten_record function."""

    def test_flat_record(self):
        """Should return flat record unchanged."""
        record = {"name": "Alice", "age": 30}
        result = flatten_record(record)
        assert result == {"name": "Alice", "age": 30}

    def test_nested_record(self):
        """Should flatten nested dicts."""
        record = {"name": "Alice", "address": {"city": "Paris"}}
        result = flatten_record(record)
        assert result == {"name": "Alice", "address.city": "Paris"}

    def test_record_with_list(self):
        """Should convert lists to JSON strings."""
        record = {"name": "Alice", "tags": ["admin", "user"]}
        result = flatten_record(record)
        assert result["name"] == "Alice"
        assert result["tags"] == '["admin", "user"]'

    def test_record_with_id(self):
        """Should preserve _id field."""
        record = {"_id": 1, "name": "Alice"}
        result = flatten_record(record)
        assert result == {"_id": 1, "name": "Alice"}


class TestGetAllColumns:
    """Tests for get_all_columns function."""

    def test_single_record(self):
        """Should return columns from single record."""
        records = [{"name": "Alice", "age": 30}]
        result = get_all_columns(records)
        assert "name" in result
        assert "age" in result

    def test_multiple_records_different_columns(self):
        """Should collect all unique columns."""
        records = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "email": "bob@example.com"},
        ]
        result = get_all_columns(records)
        assert set(result) == {"name", "age", "email"}

    def test_id_first(self):
        """Should put _id column first."""
        records = [{"_id": 1, "name": "Alice", "age": 30}]
        result = get_all_columns(records)
        assert result[0] == "_id"

    def test_columns_sorted(self):
        """Should sort non-_id columns alphabetically."""
        records = [{"_id": 1, "zebra": 1, "apple": 2, "mango": 3}]
        result = get_all_columns(records)
        assert result == ["_id", "apple", "mango", "zebra"]


class TestInferSqlType:
    """Tests for infer_sql_type function."""

    def test_none_returns_text(self):
        """Should return TEXT for None."""
        assert infer_sql_type(None) == "TEXT"

    def test_bool_returns_integer(self):
        """Should return INTEGER for bool (SQLite stores as 0/1)."""
        assert infer_sql_type(True) == "INTEGER"
        assert infer_sql_type(False) == "INTEGER"

    def test_int_returns_integer(self):
        """Should return INTEGER for int."""
        assert infer_sql_type(42) == "INTEGER"

    def test_float_returns_real(self):
        """Should return REAL for float."""
        assert infer_sql_type(3.14) == "REAL"

    def test_string_returns_text(self):
        """Should return TEXT for string."""
        assert infer_sql_type("hello") == "TEXT"

    def test_list_returns_text(self):
        """Should return TEXT for list (stored as JSON)."""
        assert infer_sql_type([1, 2, 3]) == "TEXT"

    def test_dict_returns_text(self):
        """Should return TEXT for dict (stored as JSON)."""
        assert infer_sql_type({"a": 1}) == "TEXT"


class TestEscapeSqlValue:
    """Tests for escape_sql_value function."""

    def test_none_returns_null(self):
        """Should return NULL for None."""
        assert escape_sql_value(None) == "NULL"

    def test_bool_returns_integer(self):
        """Should return 1/0 for bool."""
        assert escape_sql_value(True) == "1"
        assert escape_sql_value(False) == "0"

    def test_int_returns_string(self):
        """Should return int as string."""
        assert escape_sql_value(42) == "42"

    def test_float_returns_string(self):
        """Should return float as string."""
        assert escape_sql_value(3.14) == "3.14"

    def test_string_quoted(self):
        """Should quote strings."""
        assert escape_sql_value("hello") == "'hello'"

    def test_string_escapes_quotes(self):
        """Should escape single quotes in strings."""
        assert escape_sql_value("it's") == "'it''s'"
        assert escape_sql_value("a'b'c") == "'a''b''c'"

    def test_list_as_json(self):
        """Should convert list to JSON string."""
        result = escape_sql_value([1, 2, 3])
        assert result == "'[1, 2, 3]'"

    def test_dict_as_json(self):
        """Should convert dict to JSON string."""
        result = escape_sql_value({"a": 1})
        assert result == "'{\"a\": 1}'"


class TestEscapeSqlIdentifier:
    """Tests for escape_sql_identifier function."""

    def test_simple_identifier(self):
        """Should return simple identifiers unchanged."""
        assert escape_sql_identifier("name") == "name"
        assert escape_sql_identifier("user_id") == "user_id"

    def test_reserved_word(self):
        """Should quote SQL reserved words."""
        assert escape_sql_identifier("order") == '"order"'
        assert escape_sql_identifier("select") == '"select"'
        assert escape_sql_identifier("table") == '"table"'

    def test_hyphen_replaced(self):
        """Should replace hyphens with underscores."""
        assert escape_sql_identifier("first-name") == "first_name"

    def test_double_underscore_preserved(self):
        """Should preserve double underscores (from flattening)."""
        assert escape_sql_identifier("address__city") == "address__city"
