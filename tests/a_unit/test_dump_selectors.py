"""
Unit tests for dump command selector parsing and SQL generation.

These tests verify the selector parsing without database dependencies.
"""

from __future__ import annotations

import pytest

from kenobix.cli.dump import (
    Selector,
    build_query,
    parse_selector,
    selector_to_sql,
)


class TestParseSelector:
    """Tests for parse_selector function."""

    def test_equals_string(self):
        """Should parse simple equals selector."""
        result = parse_selector("name=John")
        assert result.field == "name"
        assert result.operator == "="
        assert result.value == "John"
        assert result.is_null_check is False

    def test_equals_integer(self):
        """Should parse integer value."""
        result = parse_selector("age=25")
        assert result.field == "age"
        assert result.operator == "="
        assert result.value == 25

    def test_equals_float(self):
        """Should parse float value."""
        result = parse_selector("score=3.14")
        assert result.field == "score"
        assert result.operator == "="
        assert result.value == 3.14

    def test_not_equals(self):
        """Should parse not equals operator."""
        result = parse_selector("status!=active")
        assert result.field == "status"
        assert result.operator == "!="
        assert result.value == "active"

    def test_greater_than(self):
        """Should parse greater than operator."""
        result = parse_selector("age>25")
        assert result.field == "age"
        assert result.operator == ">"
        assert result.value == 25

    def test_greater_or_equal(self):
        """Should parse greater or equal operator."""
        result = parse_selector("age>=25")
        assert result.field == "age"
        assert result.operator == ">="
        assert result.value == 25

    def test_less_than(self):
        """Should parse less than operator."""
        result = parse_selector("age<50")
        assert result.field == "age"
        assert result.operator == "<"
        assert result.value == 50

    def test_less_or_equal(self):
        """Should parse less or equal operator."""
        result = parse_selector("age<=50")
        assert result.field == "age"
        assert result.operator == "<="
        assert result.value == 50

    def test_like_pattern(self):
        """Should parse LIKE pattern operator."""
        result = parse_selector("email~%@gmail.com")
        assert result.field == "email"
        assert result.operator == "~"
        assert result.value == "%@gmail.com"

    def test_null_check(self):
        """Should parse null check."""
        result = parse_selector("email=null")
        assert result.field == "email"
        assert result.operator == "="
        assert result.value is None
        assert result.is_null_check is True

    def test_not_null_check(self):
        """Should parse not null check."""
        result = parse_selector("email!=null")
        assert result.field == "email"
        assert result.operator == "!="
        assert result.is_null_check is True

    def test_boolean_true(self):
        """Should parse boolean true."""
        result = parse_selector("active=true")
        assert result.field == "active"
        assert result.value is True

    def test_boolean_false(self):
        """Should parse boolean false."""
        result = parse_selector("active=false")
        assert result.field == "active"
        assert result.value is False

    def test_nested_field(self):
        """Should parse nested field with dot notation."""
        result = parse_selector("address.city=Paris")
        assert result.field == "address.city"
        assert result.value == "Paris"

    def test_deeply_nested_field(self):
        """Should parse deeply nested field."""
        result = parse_selector("user.profile.settings.theme=dark")
        assert result.field == "user.profile.settings.theme"
        assert result.value == "dark"

    def test_invalid_format_raises(self):
        """Should raise ValueError for invalid format."""
        with pytest.raises(ValueError, match="Invalid selector format"):
            parse_selector("invalid")

    def test_invalid_operator_raises(self):
        """Should raise ValueError for invalid operator."""
        with pytest.raises(ValueError, match="Invalid operator"):
            parse_selector("field==value")


class TestSelectorToSql:
    """Tests for selector_to_sql function."""

    def test_equals_string(self):
        """Should generate equals SQL for string."""
        selector = Selector(field="name", operator="=", value="John")
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) = ?"
        assert params == ["$.name", "John"]

    def test_equals_integer(self):
        """Should generate equals SQL for integer."""
        selector = Selector(field="age", operator="=", value=25)
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) = ?"
        assert params == ["$.age", 25]

    def test_not_equals(self):
        """Should generate not equals SQL."""
        selector = Selector(field="status", operator="!=", value="active")
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) != ?"
        assert params == ["$.status", "active"]

    def test_greater_than(self):
        """Should generate greater than SQL."""
        selector = Selector(field="age", operator=">", value=25)
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) > ?"
        assert params == ["$.age", 25]

    def test_like_pattern(self):
        """Should generate LIKE SQL."""
        selector = Selector(field="email", operator="~", value="%@gmail.com")
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) LIKE ?"
        assert params == ["$.email", "%@gmail.com"]

    def test_null_check(self):
        """Should generate IS NULL SQL."""
        selector = Selector(field="email", operator="=", value=None, is_null_check=True)
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) IS NULL"
        assert params == ["$.email"]

    def test_not_null_check(self):
        """Should generate IS NOT NULL SQL."""
        selector = Selector(field="email", operator="!=", value=None, is_null_check=True)
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) IS NOT NULL"
        assert params == ["$.email"]

    def test_boolean_true(self):
        """Should generate boolean true SQL."""
        selector = Selector(field="active", operator="=", value=True)
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) = ?"
        assert params == ["$.active", 1]

    def test_boolean_false(self):
        """Should generate boolean false SQL."""
        selector = Selector(field="active", operator="=", value=False)
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) = ?"
        assert params == ["$.active", 0]

    def test_nested_field(self):
        """Should handle nested field path."""
        selector = Selector(field="address.city", operator="=", value="Paris")
        sql, params = selector_to_sql(selector)
        assert sql == "json_extract(data, ?) = ?"
        assert params == ["$.address.city", "Paris"]


class TestBuildQuery:
    """Tests for build_query function."""

    def test_no_selectors(self):
        """Should build simple SELECT without WHERE."""
        sql, params = build_query("users", [])
        assert sql == "SELECT id, data FROM users"
        assert params == []

    def test_single_selector(self):
        """Should build query with single WHERE condition."""
        selector = Selector(field="name", operator="=", value="John")
        sql, params = build_query("users", [selector])
        assert "WHERE" in sql
        assert "json_extract(data, ?) = ?" in sql
        assert params == ["$.name", "John"]

    def test_multiple_selectors(self):
        """Should AND multiple selectors together."""
        selectors = [
            Selector(field="active", operator="=", value=True),
            Selector(field="age", operator=">", value=25),
        ]
        sql, params = build_query("users", selectors)
        assert "WHERE" in sql
        assert "AND" in sql
        assert len(params) == 4  # 2 for each selector

    def test_limit(self):
        """Should add LIMIT clause."""
        sql, params = build_query("users", [], limit=10)
        assert "LIMIT 10" in sql

    def test_offset(self):
        """Should add OFFSET clause."""
        sql, params = build_query("users", [], limit=10, offset=20)
        assert "LIMIT 10" in sql
        assert "OFFSET 20" in sql

    def test_count_only(self):
        """Should build COUNT query."""
        sql, params = build_query("users", [], count_only=True)
        assert sql == "SELECT COUNT(*) FROM users"

    def test_count_with_selectors(self):
        """Should build COUNT query with WHERE."""
        selector = Selector(field="active", operator="=", value=True)
        sql, params = build_query("users", [selector], count_only=True)
        assert "SELECT COUNT(*) FROM users" in sql
        assert "WHERE" in sql
