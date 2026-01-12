"""
Tests for JSON export/import utilities.

These tests verify that the JSON export and import functions work correctly.
"""

from __future__ import annotations

import json
import pathlib

from kenobix import KenobiX
from kenobix.migrate import (
    export_to_json,
    import_from_json,
)

# ============================================================================
# export_to_json Tests
# ============================================================================


class TestExportToJson:
    """Tests for the export_to_json function."""

    def test_export_all_collections(self, tmp_path):
        """Test exporting all collections to JSON."""
        db_path = tmp_path / "source.db"
        json_path = tmp_path / "export.json"

        # Create database
        db = KenobiX(str(db_path))
        db.collection("users").insert({"name": "Alice"})
        db.collection("products").insert({"sku": "SKU001"})
        db.close()

        result = export_to_json(str(db_path), str(json_path))

        # 'documents' (default, empty) + 'users' + 'products' = 3 collections
        assert result["collections"] == 3
        assert result["documents"] == 2
        assert result["output_path"] == str(json_path)

        # Verify JSON file
        with pathlib.Path(json_path).open(encoding="utf-8") as f:
            data = json.load(f)
        assert "users" in data
        assert "products" in data
        assert "documents" in data  # default collection
        assert len(data["users"]) == 1
        assert len(data["products"]) == 1
        assert len(data["documents"]) == 0  # default is empty

    def test_export_single_collection(self, tmp_path):
        """Test exporting a specific collection to JSON."""
        db_path = tmp_path / "source.db"
        json_path = tmp_path / "export.json"

        # Create database with multiple collections
        db = KenobiX(str(db_path))
        db.collection("users").insert({"name": "Alice"})
        db.collection("products").insert({"sku": "SKU001"})
        db.close()

        result = export_to_json(str(db_path), str(json_path), collection="users")

        assert result["collections"] == 1
        assert result["documents"] == 1

        # Verify JSON file only has users
        with pathlib.Path(json_path).open(encoding="utf-8") as f:
            data = json.load(f)
        assert "users" in data
        assert "products" not in data


# ============================================================================
# import_from_json Tests
# ============================================================================


class TestImportFromJson:
    """Tests for the import_from_json function."""

    def test_import_basic(self, tmp_path):
        """Test importing from JSON file."""
        json_path = tmp_path / "import.json"
        db_path = tmp_path / "dest.db"

        # Create JSON file
        data = {
            "users": [{"name": "Alice"}, {"name": "Bob"}],
            "products": [{"sku": "SKU001"}],
        }
        with pathlib.Path(json_path).open("w", encoding="utf-8") as f:
            json.dump(data, f)

        result = import_from_json(str(json_path), str(db_path))

        assert result["collections"] == 2
        assert result["documents"] == 3

        # Verify database
        db = KenobiX(str(db_path))
        assert db.collection("users").stats()["document_count"] == 2
        assert db.collection("products").stats()["document_count"] == 1
        db.close()

    def test_import_with_indexed_fields(self, tmp_path):
        """Test importing with indexed fields specification."""
        json_path = tmp_path / "import.json"
        db_path = tmp_path / "dest.db"

        # Create JSON file
        data = {"users": [{"name": "Alice", "email": "alice@example.com"}]}
        with pathlib.Path(json_path).open("w", encoding="utf-8") as f:
            json.dump(data, f)

        result = import_from_json(
            str(json_path),
            str(db_path),
            indexed_fields={"users": ["name", "email"]},
        )

        # Verify import succeeded
        assert result["collections"] == 1
        assert result["documents"] == 1

        # Verify data was imported
        db = KenobiX(str(db_path))
        coll = db.collection("users")
        assert coll.stats()["document_count"] == 1

        # Verify data is searchable (indexes working)
        docs = coll.search("name", "Alice")
        assert len(docs) == 1
        assert docs[0]["email"] == "alice@example.com"
        db.close()

    def test_import_empty_collection(self, tmp_path):
        """Test importing an empty collection."""
        json_path = tmp_path / "import.json"
        db_path = tmp_path / "dest.db"

        # Create JSON file with empty collection
        data = {"empty": []}
        with pathlib.Path(json_path).open("w", encoding="utf-8") as f:
            json.dump(data, f)

        result = import_from_json(str(json_path), str(db_path))

        assert result["documents"] == 0


# ============================================================================
# Round-trip Tests
# ============================================================================


class TestJsonRoundTrip:
    """Tests for JSON export/import round-trips."""

    def test_export_import_roundtrip(self, tmp_path):
        """Test that export followed by import preserves data."""
        source_path = tmp_path / "source.db"
        json_path = tmp_path / "export.json"
        dest_path = tmp_path / "dest.db"

        # Create source database
        source_db = KenobiX(str(source_path))
        coll = source_db.collection("users", indexed_fields=["name"])
        coll.insert({"name": "Alice", "age": 30})
        coll.insert({"name": "Bob", "age": 25})
        source_db.close()

        # Export to JSON
        export_to_json(str(source_path), str(json_path))

        # Import to new database
        import_from_json(str(json_path), str(dest_path), indexed_fields={"users": ["name"]})

        # Verify data
        dest_db = KenobiX(str(dest_path))
        dest_coll = dest_db.collection("users")
        assert dest_coll.stats()["document_count"] == 2

        # Check specific records
        alice = dest_coll.search("name", "Alice")
        assert len(alice) == 1
        assert alice[0]["age"] == 30
        dest_db.close()
