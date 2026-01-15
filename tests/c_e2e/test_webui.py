"""Tests for KenobiX Web UI module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kenobix import KenobiX


@pytest.fixture
def test_db(tmp_path: Path):
    """Create a test database with sample data."""
    db_path = tmp_path / "test_webui.db"
    db = KenobiX(str(db_path), indexed_fields=["name", "email"])

    # Insert test documents
    db.insert({"name": "Alice", "email": "alice@example.com", "age": 30})
    db.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
    db.insert({"name": "Carol", "email": "carol@test.org", "age": 35})

    # Create another collection
    orders = db.collection("orders", indexed_fields=["user_id", "status"])
    orders.insert({"user_id": 1, "status": "completed", "total": 99.99})
    orders.insert({"user_id": 2, "status": "pending", "total": 149.50})

    db.close()
    return str(db_path)


@pytest.fixture
def webui_app(test_db: str):
    """Initialize the web UI app with test database."""
    from kenobix.webui.app import app, init_app

    init_app(test_db)
    return app


# =============================================================================
# Unit Tests - Helper Functions
# =============================================================================


class TestFormatCellValue:
    """Tests for format_cell_value function."""

    def test_null_value(self):
        """Test formatting of None values."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value(None)
        assert result["display"] == "—"
        assert result["type"] == "null"
        assert result["full"] is None

    def test_boolean_true(self):
        """Test formatting of True."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value(True)
        assert result["display"] == "true"
        assert result["type"] == "boolean"

    def test_boolean_false(self):
        """Test formatting of False."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value(False)
        assert result["display"] == "false"
        assert result["type"] == "boolean"

    def test_integer(self):
        """Test formatting of integers."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value(1234567)
        assert result["display"] == "1,234,567"
        assert result["type"] == "number"

    def test_float(self):
        """Test formatting of floats."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value(3.14159)
        assert result["display"] == "3.14"
        assert result["type"] == "number"

    def test_short_string(self):
        """Test formatting of short strings."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value("Hello World")
        assert result["display"] == "Hello World"
        assert result["type"] == "string"
        assert result["full"] is None

    def test_long_string_truncated(self):
        """Test formatting of long strings (truncated)."""
        from kenobix.webui.app import format_cell_value

        long_string = "A" * 100
        result = format_cell_value(long_string, max_length=50)
        assert len(result["display"]) == 51  # 50 chars + ellipsis
        assert result["display"].endswith("…")
        assert result["type"] == "string truncated"
        assert result["full"] == long_string

    def test_array(self):
        """Test formatting of arrays."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value([1, 2, 3])
        assert result["display"] == "[3 items]"
        assert result["type"] == "array"
        assert result["full"] is not None

    def test_array_single_item(self):
        """Test formatting of single-item array."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value([1])
        assert result["display"] == "[1 item]"

    def test_object(self):
        """Test formatting of objects/dicts."""
        from kenobix.webui.app import format_cell_value

        result = format_cell_value({"a": 1, "b": 2})
        assert result["display"] == "{2 fields}"
        assert result["type"] == "object"
        assert result["full"] is not None


class TestInferTableSchema:
    """Tests for infer_table_schema function."""

    def test_empty_documents(self):
        """Test with empty document list."""
        from kenobix.webui.app import infer_table_schema

        columns = infer_table_schema([], [])
        assert len(columns) == 1
        assert columns[0].name == "_id"

    def test_includes_id_first(self):
        """Test that _id is always first column."""
        from kenobix.webui.app import infer_table_schema

        docs = [{"_id": 1, "name": "Alice", "age": 30}]
        columns = infer_table_schema(docs, [])
        assert columns[0].name == "_id"
        assert columns[0].display_name == "ID"

    def test_indexed_fields_prioritized(self):
        """Test that indexed fields come before non-indexed."""
        from kenobix.webui.app import infer_table_schema

        docs = [{"_id": 1, "name": "Alice", "age": 30, "city": "NYC"}]
        columns = infer_table_schema(docs, ["name"])

        # Find positions
        names = [c.name for c in columns]
        assert names.index("name") < names.index("age")
        assert names.index("name") < names.index("city")

    def test_indexed_marker(self):
        """Test that indexed fields are marked."""
        from kenobix.webui.app import infer_table_schema

        docs = [{"_id": 1, "name": "Alice", "email": "alice@example.com"}]
        columns = infer_table_schema(docs, ["email"])

        email_col = next(c for c in columns if c.name == "email")
        assert email_col.is_indexed is True

        name_col = next(c for c in columns if c.name == "name")
        assert name_col.is_indexed is False

    def test_max_columns_limit(self):
        """Test that column count is limited."""
        from kenobix.webui.app import infer_table_schema

        docs = [{"_id": 1, "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7}]
        columns = infer_table_schema(docs, [], max_columns=4)
        assert len(columns) == 4

    def test_column_display_name_formatting(self):
        """Test that column names are formatted nicely."""
        from kenobix.webui.app import infer_table_schema

        docs = [{"_id": 1, "user_name": "Alice", "firstName": "Alice"}]
        columns = infer_table_schema(docs, [])

        names = {c.name: c.display_name for c in columns}
        assert names["user_name"] == "User Name"
        assert names["firstName"] == "First Name"


class TestSearch:
    """Tests for search functions."""

    def test_search_collection(self, test_db: str):
        """Test searching within a collection."""
        from kenobix.webui.app import get_db, init_app, search_collection

        init_app(test_db)

        with get_db() as db:
            results = search_collection(db, "documents", "alice")
            assert len(results) == 1
            assert results[0].doc["name"] == "Alice"

    def test_search_case_insensitive(self, test_db: str):
        """Test that search is case-insensitive."""
        from kenobix.webui.app import get_db, init_app, search_collection

        init_app(test_db)

        with get_db() as db:
            results_lower = search_collection(db, "documents", "alice")
            results_upper = search_collection(db, "documents", "ALICE")
            # SQLite LIKE is case-insensitive for ASCII
            assert len(results_lower) == len(results_upper)

    def test_search_multiple_matches(self, test_db: str):
        """Test search with multiple matches."""
        from kenobix.webui.app import get_db, init_app, search_collection

        init_app(test_db)

        with get_db() as db:
            results = search_collection(db, "documents", "example.com")
            assert len(results) == 2  # Alice and Bob have example.com emails

    def test_search_no_matches(self, test_db: str):
        """Test search with no matches."""
        from kenobix.webui.app import get_db, init_app, search_collection

        init_app(test_db)

        with get_db() as db:
            results = search_collection(db, "documents", "nonexistent")
            assert len(results) == 0

    def test_search_all_collections(self, test_db: str):
        """Test searching across all collections."""
        from kenobix.webui.app import get_db, init_app, search_all_collections

        init_app(test_db)

        with get_db() as db:
            results = search_all_collections(db, "1")
            # Should find in both documents (IDs) and orders (user_id)
            assert len(results) >= 1

    def test_search_special_characters(self, test_db: str):
        """Test search with special SQL characters."""
        from kenobix.webui.app import get_db, init_app, search_collection

        init_app(test_db)

        with get_db() as db:
            # % and _ should be escaped
            results = search_collection(db, "documents", "%")
            # Should not match anything (% is escaped)
            assert len(results) == 0

    def test_snippet_creation(self):
        """Test search snippet creation."""
        from kenobix.webui.app import _create_snippet

        data = "This is a test string with the word hello in it"
        snippet = _create_snippet(data, "hello", context_chars=10)
        assert "hello" in snippet
        assert len(snippet) < len(data) + 10  # Should be truncated

    def test_snippet_at_start(self):
        """Test snippet when match is at start."""
        from kenobix.webui.app import _create_snippet

        data = "hello world this is a long string"
        snippet = _create_snippet(data, "hello", context_chars=10)
        assert snippet.startswith("hello")

    def test_snippet_at_end(self):
        """Test snippet when match is at end."""
        from kenobix.webui.app import _create_snippet

        data = "this is a long string ending with hello"
        snippet = _create_snippet(data, "hello", context_chars=10)
        assert snippet.endswith("hello")


# =============================================================================
# Integration Tests - Routes
# =============================================================================


class TestIndexRoute:
    """Tests for the index (/) route."""

    def test_index_returns_200(self, webui_app, test_db: str):
        """Test that index page returns 200."""
        from kenobix.webui.app import init_app, render

        init_app(test_db)
        # We can't easily test Bottle routes directly without WebTest,
        # so we test the render function instead
        from kenobix.webui.app import get_collection_info, get_db

        with get_db() as db:
            collection_names = db.collections()
            collections = [get_collection_info(db, name) for name in collection_names]
            total_docs = sum(c["count"] for c in collections)

            html = render(
                "index.html",
                collections=collections,
                total_docs=total_docs,
                db_size=0,
                db_path=test_db,
            )

            assert "KenobiX Explorer" in html
            assert "documents" in html
            assert "orders" in html


class TestCollectionRoute:
    """Tests for collection view routes."""

    def test_collection_view_renders(self, webui_app, test_db: str):
        """Test that collection view renders correctly."""
        from kenobix.webui.app import (
            Pagination,
            get_collection_info,
            get_db,
            get_documents_paginated,
            get_indexed_fields,
            infer_table_schema,
            init_app,
            render,
        )

        init_app(test_db)

        with get_db() as db:
            info = get_collection_info(db, "documents")
            docs = get_documents_paginated(db, "documents", 20, 0)
            indexed = get_indexed_fields(db, "documents")
            columns = infer_table_schema(docs, indexed)
            pagination = Pagination(page=1, per_page=20, total=info["count"])

            html = render(
                "collection.html",
                collection="documents",
                documents=docs,
                columns=columns,
                pagination=pagination,
                total=info["count"],
                indexed=indexed,
            )

            assert "documents" in html
            assert "Alice" in html
            assert "Bob" in html


class TestSearchRoute:
    """Tests for search routes."""

    def test_search_page_renders_empty(self, webui_app, test_db: str):
        """Test that empty search page renders."""
        from kenobix.webui.app import get_db, init_app, render

        init_app(test_db)

        with get_db() as db:
            collections = db.collections()

            html = render(
                "search.html",
                query="",
                results={},
                total_results=0,
                collections=collections,
                selected_collection="",
            )

            assert "Search" in html
            assert "All collections" in html

    def test_search_page_renders_with_results(self, webui_app, test_db: str):
        """Test that search page renders with results."""
        from kenobix.webui.app import get_db, init_app, render, search_all_collections

        init_app(test_db)

        with get_db() as db:
            collections = db.collections()
            results = search_all_collections(db, "alice")
            total_results = sum(len(r) for r in results.values())

            html = render(
                "search.html",
                query="alice",
                results=results,
                total_results=total_results,
                collections=collections,
                selected_collection="",
            )

            assert "alice" in html
            assert "result" in html.lower()


class TestAPIRoutes:
    """Tests for API routes."""

    def test_api_search(self, webui_app, test_db: str):
        """Test the search API returns correct format."""
        from kenobix.webui.app import get_db, init_app, search_all_collections

        init_app(test_db)

        with get_db() as db:
            results = search_all_collections(db, "alice")

            # Simulate API serialization
            serialized = {}
            for coll_name, coll_results in results.items():
                serialized[coll_name] = [
                    {
                        "id": r.doc_id,
                        "document": r.doc,
                        "snippet": r.snippet,
                    }
                    for r in coll_results
                ]

            response_data = {
                "query": "alice",
                "collection": None,
                "results": serialized,
                "total": sum(len(r) for r in results.values()),
            }

            # Verify it serializes to JSON
            json_str = json.dumps(response_data)
            parsed = json.loads(json_str)

            assert parsed["query"] == "alice"
            assert parsed["total"] >= 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_collection(self, tmp_path: Path):
        """Test handling of empty collection."""
        from kenobix.webui.app import (
            get_db,
            get_documents_paginated,
            infer_table_schema,
            init_app,
        )

        db_path = tmp_path / "empty.db"
        db = KenobiX(str(db_path))
        db.close()

        init_app(str(db_path))

        with get_db() as db:
            docs = get_documents_paginated(db, "documents", 20, 0)
            assert len(docs) == 0

            columns = infer_table_schema(docs, [])
            assert len(columns) == 1  # Just _id

    def test_document_with_nested_objects(self, tmp_path: Path):
        """Test handling of documents with nested objects."""
        from kenobix.webui.app import format_cell_value

        nested_doc = {
            "user": {"name": "Alice", "address": {"city": "NYC"}},
            "tags": ["python", "database"],
        }

        user_cell = format_cell_value(nested_doc["user"])
        assert user_cell["type"] == "object"
        assert "2 fields" in user_cell["display"]

        tags_cell = format_cell_value(nested_doc["tags"])
        assert tags_cell["type"] == "array"
        assert "2 items" in tags_cell["display"]

    def test_pagination_edge_cases(self):
        """Test pagination helper with edge cases."""
        from kenobix.webui.app import Pagination

        # Empty collection
        p = Pagination(page=1, per_page=20, total=0)
        assert p.total_pages == 1
        assert p.has_next is False
        assert p.has_prev is False

        # Single page
        p = Pagination(page=1, per_page=20, total=10)
        assert p.total_pages == 1
        assert p.has_next is False

        # Multiple pages
        p = Pagination(page=2, per_page=20, total=50)
        assert p.total_pages == 3
        assert p.has_next is True
        assert p.has_prev is True

        # Last page
        p = Pagination(page=3, per_page=20, total=50)
        assert p.has_next is False
        assert p.has_prev is True
