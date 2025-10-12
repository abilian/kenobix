#!/usr/bin/env python3
"""
Tests for KenobiX multi-collection support.

Tests that multiple collections can coexist in the same database,
each with their own schema and indexes.
"""

from __future__ import annotations

import pytest

from kenobix import KenobiX


@pytest.fixture
def db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    """Provide KenobiX database instance."""
    database = KenobiX(str(db_path))
    yield database
    database.close()


class TestCollectionBasics:
    """Test basic collection creation and usage."""

    def test_create_collection(self, db):
        """Test creating a named collection."""
        # Create a collection
        users = db.collection("users", indexed_fields=["user_id", "email"])

        assert users is not None
        assert users.name == "users"

    def test_collection_insert_and_search(self, db):
        """Test basic CRUD on a collection."""
        users = db.collection("users", indexed_fields=["user_id"])

        # Insert
        doc_id = users.insert({"user_id": 1, "name": "Alice"})
        assert doc_id > 0

        # Search
        results = users.search("user_id", 1)
        assert len(results) == 1
        assert results[0]["name"] == "Alice"

    def test_multiple_collections_isolated(self, db):
        """Test that collections are isolated from each other."""
        # Create two collections
        users = db.collection("users", indexed_fields=["user_id"])
        orders = db.collection("orders", indexed_fields=["order_id"])

        # Insert into each
        users.insert({"user_id": 1, "name": "Alice"})
        orders.insert({"order_id": 101, "amount": 99.99})

        # Verify isolation
        assert len(users.all(limit=100)) == 1
        assert len(orders.all(limit=100)) == 1

        # Data from one collection doesn't appear in another
        user_data = users.all(limit=100)[0]
        order_data = orders.all(limit=100)[0]

        assert "name" in user_data
        assert "amount" not in user_data

        assert "amount" in order_data
        assert "name" not in order_data

    def test_collection_reuse(self, db):
        """Test that getting the same collection twice returns the same instance."""
        users1 = db.collection("users")
        users2 = db.collection("users")

        # Should be the same instance (cached)
        assert users1 is users2

    def test_dict_style_access(self, db):
        """Test dictionary-style collection access."""
        # Dict-style access creates collection
        db["users"].insert({"user_id": 1, "name": "Alice"})
        db["orders"].insert({"order_id": 101, "amount": 99.99})

        # Verify
        users = db["users"].all(limit=100)
        orders = db["orders"].all(limit=100)

        assert len(users) == 1
        assert len(orders) == 1
        assert users[0]["name"] == "Alice"
        assert orders[0]["amount"] == 99.99

    def test_list_collections(self, db):
        """Test listing all collections in database."""
        # Create some collections
        db.collection("users")
        db.collection("orders")
        db.collection("products")

        # List them
        collections = db.collections()

        assert "users" in collections
        assert "orders" in collections
        assert "products" in collections


class TestBackwardCompatibility:
    """Test that existing code continues to work."""

    def test_default_collection_insert_search(self, db_path):
        """Test that KenobiX without collections still works (uses 'documents')."""
        # Old-style usage
        db = KenobiX(str(db_path), indexed_fields=["name"])

        # Old API should work
        doc_id = db.insert({"name": "Alice", "age": 30})
        assert doc_id > 0

        results = db.search("name", "Alice")
        assert len(results) == 1
        assert results[0]["age"] == 30

        db.close()

    def test_default_collection_update(self, db_path):
        """Test update on default collection."""
        db = KenobiX(str(db_path), indexed_fields=["name"])

        db.insert({"name": "Alice", "age": 30})
        success = db.update("name", "Alice", {"age": 31})

        assert success is True

        results = db.search("name", "Alice")
        assert results[0]["age"] == 31

        db.close()

    def test_default_collection_remove(self, db_path):
        """Test remove on default collection."""
        db = KenobiX(str(db_path), indexed_fields=["name"])

        db.insert({"name": "Alice"})
        db.insert({"name": "Bob"})

        removed = db.remove("name", "Alice")
        assert removed == 1

        results = db.all(limit=100)
        assert len(results) == 1
        assert results[0]["name"] == "Bob"

        db.close()

    def test_default_collection_all_operations(self, db_path):
        """Test all major operations on default collection."""
        db = KenobiX(str(db_path), indexed_fields=["user_id"])

        # Insert
        db.insert({"user_id": 1, "name": "Alice"})
        db.insert({"user_id": 2, "name": "Bob"})

        # Search
        assert len(db.search("user_id", 1)) == 1

        # All
        assert len(db.all(limit=100)) == 2

        # Update
        db.update("user_id", 1, {"status": "active"})

        # Verify update
        user = db.search("user_id", 1)[0]
        assert user["status"] == "active"

        # Remove
        db.remove("user_id", 2)
        assert len(db.all(limit=100)) == 1

        # Purge
        db.purge()
        assert len(db.all(limit=100)) == 0

        db.close()


class TestCollectionTransactions:
    """Test transactions across multiple collections."""

    def test_transaction_across_collections(self, db):
        """Test that transactions work across multiple collections."""
        users = db.collection("users", indexed_fields=["user_id"])
        orders = db.collection("orders", indexed_fields=["order_id"])

        # Transaction across collections
        with db.transaction():
            users.insert({"user_id": 1, "name": "Alice"})
            orders.insert({"order_id": 101, "user_id": 1, "amount": 99.99})

        # Both should exist
        assert len(users.all(limit=100)) == 1
        assert len(orders.all(limit=100)) == 1

    def test_transaction_rollback_across_collections(self, db):
        """Test that rollback works across collections."""
        users = db.collection("users", indexed_fields=["user_id"])
        orders = db.collection("orders", indexed_fields=["order_id"])

        # Transaction that fails
        try:
            with db.transaction():
                users.insert({"user_id": 1, "name": "Alice"})
                orders.insert({"order_id": 101, "user_id": 1})
                msg = "Simulated error"
                raise ValueError(msg)
        except ValueError:
            pass

        # Neither should exist (rolled back)
        assert len(users.all(limit=100)) == 0
        assert len(orders.all(limit=100)) == 0

    def test_default_collection_transactions(self, db_path):
        """Test that transactions still work on default collection."""
        db = KenobiX(str(db_path), indexed_fields=["user_id"])

        # Transaction on default collection
        with db.transaction():
            db.insert({"user_id": 1, "name": "Alice"})
            db.insert({"user_id": 2, "name": "Bob"})

        assert len(db.all(limit=100)) == 2

        # Rollback on default collection
        try:
            with db.transaction():
                db.insert({"user_id": 3, "name": "Carol"})
                msg = "Rollback"
                raise ValueError(msg)
        except ValueError:
            pass

        assert len(db.all(limit=100)) == 2  # Still 2

        db.close()


class TestCollectionIndexes:
    """Test that each collection has its own indexes."""

    def test_collection_specific_indexes(self, db):
        """Test that each collection can have different indexed fields."""
        # Different indexes for each collection
        users = db.collection("users", indexed_fields=["user_id", "email"])
        orders = db.collection("orders", indexed_fields=["order_id", "user_id"])

        # Verify indexes
        assert "user_id" in users.get_indexed_fields()
        assert "email" in users.get_indexed_fields()

        assert "order_id" in orders.get_indexed_fields()
        assert "user_id" in orders.get_indexed_fields()
        assert "email" not in orders.get_indexed_fields()

    def test_indexed_search_on_collection(self, db):
        """Test that indexed searches work on collections."""
        users = db.collection("users", indexed_fields=["email"])

        # Insert test data
        users.insert({"email": "alice@example.com", "name": "Alice"})
        users.insert({"email": "bob@example.com", "name": "Bob"})

        # Search using indexed field
        results = users.search("email", "alice@example.com")
        assert len(results) == 1
        assert results[0]["name"] == "Alice"

        # Verify index is being used with explain
        plan = users.explain("search", "email", "alice@example.com")
        # Should mention index usage
        plan_str = str(plan)
        assert "idx_email" in plan_str or "SEARCH" in plan_str


class TestCollectionPersistence:
    """Test that collections persist across database opens."""

    def test_collection_persists(self, db_path):
        """Test that collections survive database close/reopen."""
        # Create and populate collection
        db = KenobiX(str(db_path))
        users = db.collection("users", indexed_fields=["user_id"])
        users.insert({"user_id": 1, "name": "Alice"})
        db.close()

        # Reopen database
        db = KenobiX(str(db_path))
        users = db.collection("users", indexed_fields=["user_id"])

        # Data should still be there
        results = users.all(limit=100)
        assert len(results) == 1
        assert results[0]["name"] == "Alice"

        db.close()

    def test_multiple_collections_persist(self, db_path):
        """Test that multiple collections persist."""
        # Create multiple collections
        db = KenobiX(str(db_path))
        db["users"].insert({"user_id": 1, "name": "Alice"})
        db["orders"].insert({"order_id": 101, "amount": 99.99})
        db["products"].insert({"product_id": 201, "name": "Widget"})
        db.close()

        # Reopen
        db = KenobiX(str(db_path))
        collections = db.collections()

        assert "users" in collections
        assert "orders" in collections
        assert "products" in collections

        # Verify data
        assert len(db["users"].all(limit=100)) == 1
        assert len(db["orders"].all(limit=100)) == 1
        assert len(db["products"].all(limit=100)) == 1

        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
