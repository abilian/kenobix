"""
Tests for database migration utilities.

These tests verify that the migrate functions work correctly
for SQLite databases. PostgreSQL tests require psycopg2 and a running server.
"""

from __future__ import annotations

import pytest

from kenobix import KenobiX
from kenobix.migrate import (
    get_backend_type,
    migrate,
    migrate_collection,
)

# ============================================================================
# get_backend_type Tests
# ============================================================================


class TestGetBackendType:
    """Tests for backend type detection."""

    def test_sqlite_file_path(self):
        """Test that file paths are detected as SQLite."""
        assert get_backend_type("mydb.db") == "sqlite"
        assert get_backend_type("/path/to/database.db") == "sqlite"
        assert get_backend_type("data.sqlite") == "sqlite"

    def test_postgresql_url(self):
        """Test that PostgreSQL URLs are detected correctly."""
        assert get_backend_type("postgresql://localhost/db") == "postgresql"
        assert get_backend_type("postgresql://user:pass@host:5432/db") == "postgresql"
        assert get_backend_type("postgres://localhost/db") == "postgresql"

    def test_memory_sqlite(self):
        """Test that :memory: is detected as SQLite."""
        assert get_backend_type(":memory:") == "sqlite"


# ============================================================================
# migrate Tests (SQLite to SQLite)
# ============================================================================


class TestMigrate:
    """Tests for the migrate function."""

    def test_migrate_empty_database(self, tmp_path):
        """Test migrating an empty database (only default collection)."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create empty source - KenobiX creates a default 'documents' collection
        source_db = KenobiX(str(source_path))
        source_db.close()

        result = migrate(str(source_path), str(dest_path))

        # Default 'documents' collection exists but is empty
        assert result["collections"] == 1  # default 'documents' collection
        assert result["documents"] == 0
        assert result["source_type"] == "sqlite"
        assert result["dest_type"] == "sqlite"

    def test_migrate_single_collection(self, tmp_path):
        """Test migrating a single collection."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create source with data
        source_db = KenobiX(str(source_path))
        coll = source_db.collection("users", indexed_fields=["name", "email"])
        coll.insert({"name": "Alice", "email": "alice@example.com"})
        coll.insert({"name": "Bob", "email": "bob@example.com"})
        source_db.close()

        result = migrate(str(source_path), str(dest_path))

        # 'documents' (default) + 'users' = 2 collections
        assert result["collections"] == 2
        assert result["documents"] == 2
        assert result["source_type"] == "sqlite"
        assert result["dest_type"] == "sqlite"

        # Verify destination data
        dest_db = KenobiX(str(dest_path))
        dest_coll = dest_db.collection("users")
        assert dest_coll.stats()["document_count"] == 2
        dest_db.close()

    def test_migrate_multiple_collections(self, tmp_path):
        """Test migrating multiple collections."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create source with multiple collections
        source_db = KenobiX(str(source_path))
        users = source_db.collection("users", indexed_fields=["name"])
        users.insert({"name": "Alice"})
        users.insert({"name": "Bob"})

        products = source_db.collection("products", indexed_fields=["sku"])
        products.insert({"sku": "SKU001", "name": "Widget"})
        source_db.close()

        result = migrate(str(source_path), str(dest_path))

        # 'documents' (default) + 'users' + 'products' = 3 collections
        assert result["collections"] == 3
        assert result["documents"] == 3

        # Verify destination
        dest_db = KenobiX(str(dest_path))
        assert dest_db.collection("users").stats()["document_count"] == 2
        assert dest_db.collection("products").stats()["document_count"] == 1
        dest_db.close()

    def test_migrate_with_progress_callback(self, tmp_path):
        """Test that progress callback is called."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create source with data
        source_db = KenobiX(str(source_path))
        coll = source_db.collection("users")
        coll.insert({"name": "Alice"})
        source_db.close()

        messages = []

        def on_progress(msg):
            messages.append(msg)

        migrate(str(source_path), str(dest_path), on_progress=on_progress)

        assert len(messages) > 0
        assert any("sqlite" in msg for msg in messages)

    def test_migrate_same_source_dest_raises(self, tmp_path):
        """Test that same source and destination raises ValueError."""
        db_path = tmp_path / "db.db"

        with pytest.raises(ValueError, match="Source and destination cannot be the same"):
            migrate(str(db_path), str(db_path))

    def test_migrate_large_batch(self, tmp_path):
        """Test migrating with batched inserts."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create source with enough documents to require batching
        source_db = KenobiX(str(source_path))
        coll = source_db.collection("docs")
        docs = [{"idx": i, "data": f"document_{i}"} for i in range(150)]
        coll.insert_many(docs)
        source_db.close()

        result = migrate(str(source_path), str(dest_path), batch_size=50)

        assert result["documents"] == 150

        # Verify all documents made it
        dest_db = KenobiX(str(dest_path))
        assert dest_db.collection("docs").stats()["document_count"] == 150
        dest_db.close()


# ============================================================================
# migrate_collection Tests
# ============================================================================


class TestMigrateCollection:
    """Tests for the migrate_collection function."""

    def test_migrate_single_collection_basic(self, tmp_path):
        """Test migrating a specific collection."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create source
        source_db = KenobiX(str(source_path))
        coll = source_db.collection("users", indexed_fields=["name"])
        coll.insert({"name": "Alice"})
        coll.insert({"name": "Bob"})
        source_db.close()

        result = migrate_collection(str(source_path), str(dest_path), "users")

        assert result["collection"] == "users"
        assert result["documents"] == 2

    def test_migrate_collection_empty(self, tmp_path):
        """Test migrating an empty collection."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create empty collection
        source_db = KenobiX(str(source_path))
        source_db.collection("empty")
        source_db.close()

        result = migrate_collection(str(source_path), str(dest_path), "empty")

        assert result["documents"] == 0

    def test_migrate_collection_with_custom_indexed_fields(self, tmp_path):
        """Test migrating with custom indexed fields."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"

        # Create source
        source_db = KenobiX(str(source_path))
        coll = source_db.collection("users", indexed_fields=["name"])
        coll.insert({"name": "Alice", "email": "alice@example.com"})
        source_db.close()

        # Migrate with different indexed fields
        result = migrate_collection(
            str(source_path),
            str(dest_path),
            "users",
            indexed_fields=["email"],
        )

        # Verify migration succeeded
        assert result["documents"] == 1

        # Verify data was migrated
        dest_db = KenobiX(str(dest_path))
        dest_coll = dest_db.collection("users")
        assert dest_coll.stats()["document_count"] == 1

        # Verify the document data is correct
        docs = dest_coll.all()
        assert len(docs) == 1
        assert docs[0]["email"] == "alice@example.com"
        dest_db.close()


# ============================================================================
# Migration Round-trip Tests
# ============================================================================


class TestMigrateRoundTrip:
    """Tests for migration round-trips."""

    def test_migrate_roundtrip(self, tmp_path):
        """Test that migrate preserves data correctly."""
        source_path = tmp_path / "source.db"
        dest_path = tmp_path / "dest.db"
        roundtrip_path = tmp_path / "roundtrip.db"

        # Create source
        source_db = KenobiX(str(source_path))
        coll = source_db.collection("users", indexed_fields=["name", "email"])
        original_docs = [
            {"name": "Alice", "email": "alice@example.com", "active": True},
            {"name": "Bob", "email": "bob@example.com", "active": False},
        ]
        for doc in original_docs:
            coll.insert(doc)
        source_db.close()

        # Migrate to dest
        migrate(str(source_path), str(dest_path))

        # Migrate back to roundtrip
        migrate(str(dest_path), str(roundtrip_path))

        # Verify data
        roundtrip_db = KenobiX(str(roundtrip_path))
        roundtrip_coll = roundtrip_db.collection("users")
        assert roundtrip_coll.stats()["document_count"] == 2

        # Verify all documents
        all_docs = roundtrip_coll.all()
        names = {doc["name"] for doc in all_docs}
        assert names == {"Alice", "Bob"}
        roundtrip_db.close()
