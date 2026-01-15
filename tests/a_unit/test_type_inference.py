"""
Unit tests for type inference functions.

These tests verify pure functions without database dependencies.
"""

from __future__ import annotations

import pytest

from kenobix.cli.info import infer_json_type, merge_types


class TestInferJsonType:
    """Tests for infer_json_type function."""

    def test_null_type(self):
        """Should return 'null' for None."""
        assert infer_json_type(None) == "null"

    def test_boolean_type(self):
        """Should return 'boolean' for bool values."""
        assert infer_json_type(True) == "boolean"
        assert infer_json_type(False) == "boolean"

    def test_integer_type(self):
        """Should return 'integer' for int values."""
        assert infer_json_type(42) == "integer"
        assert infer_json_type(0) == "integer"
        assert infer_json_type(-100) == "integer"

    def test_number_type(self):
        """Should return 'number' for float values."""
        assert infer_json_type(3.14) == "number"
        assert infer_json_type(0.0) == "number"
        assert infer_json_type(-2.5) == "number"

    def test_string_type(self):
        """Should return 'string' for str values."""
        assert infer_json_type("hello") == "string"
        assert infer_json_type("") == "string"

    def test_array_type(self):
        """Should return 'array' for list values."""
        assert infer_json_type([]) == "array"
        assert infer_json_type([1, 2, 3]) == "array"
        assert infer_json_type(["a", "b"]) == "array"

    def test_object_type(self):
        """Should return 'object' for dict values."""
        assert infer_json_type({}) == "object"
        assert infer_json_type({"key": "value"}) == "object"


class TestMergeTypes:
    """Tests for merge_types function."""

    def test_single_type(self):
        """Should return single type unchanged."""
        assert merge_types({"string"}) == "string"
        assert merge_types({"integer"}) == "integer"
        assert merge_types({"boolean"}) == "boolean"

    def test_nullable_type(self):
        """Should mark nullable types with '?'."""
        assert merge_types({"string", "null"}) == "string?"
        assert merge_types({"integer", "null"}) == "integer?"
        assert merge_types({"boolean", "null"}) == "boolean?"

    def test_only_null(self):
        """Should return 'null' for only null type."""
        assert merge_types({"null"}) == "null"

    def test_numeric_merge(self):
        """Should merge integer and number to number."""
        assert merge_types({"integer", "number"}) == "number"

    def test_multiple_types(self):
        """Should join multiple types with '|'."""
        result = merge_types({"string", "integer"})
        assert "string" in result
        assert "integer" in result
        assert "|" in result

    def test_multiple_types_sorted(self):
        """Should sort multiple types alphabetically."""
        result = merge_types({"string", "boolean", "integer"})
        # Types should be sorted: boolean | integer | string
        assert result == "boolean | integer | string"

    def test_multiple_with_null(self):
        """Should handle multiple types with null."""
        result = merge_types({"string", "integer", "null"})
        assert "?" in result  # Should be nullable
        assert "string" in result
        assert "integer" in result
