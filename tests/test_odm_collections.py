"""
Tests for ODM Collection Support (Phase 2)

Tests cover:
- Collection name derivation from class names
- Explicit collection names via Meta.collection_name
- Per-model indexed fields via Meta.indexed_fields
- Collection isolation between models
- Backward compatibility
"""

from dataclasses import dataclass

import cattrs
import pytest

from kenobix import Document, KenobiX


# Test models with Meta class
@dataclass
class User(Document):
    """User model with explicit Meta configuration."""

    class Meta:
        collection_name = "users"
        indexed_fields = ["email", "user_id"]

    name: str
    email: str
    user_id: int
    active: bool = True


@dataclass
class Order(Document):
    """Order model with auto-derived collection name."""

    class Meta:
        indexed_fields = ["order_id", "user_id"]

    order_id: int
    user_id: int
    total: float
    status: str = "pending"


@dataclass
class Product(Document):
    """Product model without Meta (should use auto-derived name)."""

    product_id: int
    name: str
    price: float
    stock: int = 0


# Fixtures
@pytest.fixture
def db_path(tmp_path):
    """Temporary database path."""
    return tmp_path / "test_odm_collections.db"


@pytest.fixture
def db(db_path):
    """Create database."""
    database = KenobiX(str(db_path))
    Document.set_database(database)
    yield database
    database.close()


# Collection Name Tests
def test_explicit_collection_name(db):
    """Test that explicit Meta.collection_name is used."""
    assert User._collection_name == "users"


def test_auto_derived_collection_name(db):
    """Test that collection names are auto-derived from class names."""
    # Order → orders
    assert Order._collection_name == "orders"
    # Product → products
    assert Product._collection_name == "products"


def test_collection_name_pluralization(db):
    """Test pluralization rules."""

    @dataclass
    class Category(Document):
        name: str

    @dataclass
    class Address(Document):
        street: str

    @dataclass
    class Box(Document):
        size: str

    # Category → categories (y → ies)
    assert Category._collection_name == "categories"
    # Address → addresses (s → es)
    assert Address._collection_name == "addresses"
    # Box → boxes (x → es)
    assert Box._collection_name == "boxes"


# Collection Isolation Tests
def test_models_use_separate_collections(db):
    """Test that different models use separate collections."""
    # Insert users
    user1 = User(name="Alice", email="alice@example.com", user_id=1)
    user2 = User(name="Bob", email="bob@example.com", user_id=2)
    user1.save()
    user2.save()

    # Insert orders
    order1 = Order(order_id=101, user_id=1, total=99.99)
    order2 = Order(order_id=102, user_id=2, total=149.99)
    order1.save()
    order2.save()

    # Verify separate collections
    assert User.count() == 2
    assert Order.count() == 2

    # Verify collections are listed in database
    collections = db.collections()
    assert "users" in collections
    assert "orders" in collections


def test_collection_isolation_queries(db):
    """Test that queries are isolated to the model's collection."""
    # Create users and orders with same IDs
    user = User(name="Alice", email="alice@example.com", user_id=1)
    user.save()

    order = Order(order_id=1, user_id=1, total=99.99)
    order.save()

    # Query users - should not see orders
    users = User.all()
    assert len(users) == 1
    assert users[0].name == "Alice"

    # Query orders - should not see users
    orders = Order.all()
    assert len(orders) == 1
    assert orders[0].total == 99.99


# Indexed Fields Tests
def test_meta_indexed_fields(db):
    """Test that Meta.indexed_fields are respected."""
    # User has indexed_fields in Meta
    assert "email" in User._indexed_fields_list
    assert "user_id" in User._indexed_fields_list

    # Product has no Meta, so no indexed fields
    assert Product._indexed_fields_list == []


def test_indexed_fields_create_indexes(db):
    """Test that indexed fields actually create database indexes."""
    # Save a user to ensure collection is created
    user = User(name="Alice", email="alice@example.com", user_id=1)
    user.save()

    # Get collection and verify indexed fields
    user_collection = User._get_collection()
    indexed_fields = user_collection.get_indexed_fields()

    assert "email" in indexed_fields
    assert "user_id" in indexed_fields


def test_queries_use_model_indexes(db):
    """Test that queries use the model's indexed fields."""
    # Insert users
    for i in range(10):
        user = User(
            name=f"User{i}",
            email=f"user{i}@example.com",
            user_id=i,
            active=(i % 2 == 0),
        )
        user.save()

    # Query on indexed field (email) - should be fast
    alice = User.get(email="user5@example.com")
    assert alice is not None
    assert alice.user_id == 5

    # Query on non-indexed field (active) - still works
    active_users = User.filter(active=True)
    assert len(active_users) == 5


# Backward Compatibility Tests
def test_models_without_meta_use_default_collection(db):
    """Test that models without Meta still work (using auto-derived names)."""

    @dataclass
    class LegacyModel(Document):
        """Model without Meta class."""

        value: str

    # Should use auto-derived collection name
    assert LegacyModel._collection_name == "legacymodels"

    # Should still work
    doc = LegacyModel(value="test")
    doc.save()
    assert doc._id is not None

    retrieved = LegacyModel.get_by_id(doc._id)
    assert retrieved.value == "test"


# Mixed Model Operations
def test_transactions_across_model_collections(db):
    """Test that transactions work across different model collections."""
    with db.transaction():
        user = User(name="Alice", email="alice@example.com", user_id=1)
        user.save()

        order = Order(order_id=101, user_id=1, total=99.99)
        order.save()

    # Both should be committed
    assert User.count() == 1
    assert Order.count() == 1


def test_transaction_rollback_across_models(db):
    """Test that rollback works across different model collections."""
    # Insert initial data in both collections to ensure tables exist
    user = User(name="Alice", email="alice@example.com", user_id=1)
    user.save()

    order_initial = Order(order_id=100, user_id=1, total=50.00)
    order_initial.save()

    # Try transaction that fails
    try:
        with db.transaction():
            order = Order(order_id=101, user_id=1, total=99.99)
            order.save()

            # This should cause rollback
            msg = "Intentional failure"
            raise RuntimeError(msg)
    except RuntimeError:
        pass

    # User should still exist, order 101 should not (rolled back)
    assert User.count() == 1
    assert Order.count() == 1  # Only the initial order 100

    # Verify order 101 doesn't exist
    orders = Order.all()
    assert len(orders) == 1
    assert orders[0].order_id == 100


def test_multiple_models_with_same_field_names(db):
    """Test that models with same field names don't interfere."""
    # Both User and Order have user_id field
    user = User(name="Alice", email="alice@example.com", user_id=1)
    user.save()

    order = Order(order_id=101, user_id=999, total=99.99)  # Different user_id value
    order.save()

    # Queries should be isolated
    users_with_id_1 = User.filter(user_id=1)
    assert len(users_with_id_1) == 1

    orders_with_user_999 = Order.filter(user_id=999)
    assert len(orders_with_user_999) == 1


# Collection Statistics
def test_collection_stats(db):
    """Test that collection statistics work per model."""
    # Insert data
    for i in range(5):
        user = User(name=f"User{i}", email=f"user{i}@example.com", user_id=i)
        user.save()

    for i in range(3):
        order = Order(order_id=100 + i, user_id=i, total=99.99 * (i + 1))
        order.save()

    # Get collection stats
    user_collection = User._get_collection()
    user_stats = user_collection.stats()

    assert user_stats["collection"] == "users"
    assert user_stats["document_count"] == 5
    assert "email" in user_stats["indexed_fields"]
    assert "user_id" in user_stats["indexed_fields"]

    order_collection = Order._get_collection()
    order_stats = order_collection.stats()

    assert order_stats["collection"] == "orders"
    assert order_stats["document_count"] == 3


# Edge Cases
def test_empty_meta_class(db):
    """Test model with empty Meta class."""

    @dataclass
    class EmptyMeta(Document):
        class Meta:
            pass

        value: str

    # Should use auto-derived name
    assert EmptyMeta._collection_name == "emptymetas"
    assert EmptyMeta._indexed_fields_list == []


def test_meta_with_only_collection_name(db):
    """Test Meta with only collection_name."""

    @dataclass
    class CustomName(Document):
        class Meta:
            collection_name = "my_custom_collection"

        value: str

    assert CustomName._collection_name == "my_custom_collection"
    assert CustomName._indexed_fields_list == []


def test_meta_with_only_indexed_fields(db):
    """Test Meta with only indexed_fields."""

    @dataclass
    class IndexedOnly(Document):
        class Meta:
            indexed_fields = ["field1", "field2"]

        field1: str
        field2: int

    # Should auto-derive collection name
    assert IndexedOnly._collection_name == "indexedonlies"
    assert IndexedOnly._indexed_fields_list == ["field1", "field2"]
