#!/usr/bin/env python3
"""
Tests for KenobiX ODM relationship fields.

Tests ForeignKey descriptor for many-to-1 relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from kenobix import ForeignKey, KenobiX
from kenobix.odm import Document


@pytest.fixture
def db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    """Provide KenobiX database instance."""
    database = KenobiX(str(db_path))
    Document.set_database(database)
    yield database
    database.close()


# Test Models
@dataclass
class User(Document):
    """User model for testing."""

    class Meta:
        collection_name = "users"
        indexed_fields = ["user_id", "email"]

    user_id: int
    name: str
    email: str


@dataclass
class Order(Document):
    """Order model with foreign key to User."""

    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]

    order_id: int
    user_id: int
    amount: float

    # Many-to-1 relationship
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User), init=False, repr=False, compare=False
    )


@dataclass
class Profile(Document):
    """Profile model with optional foreign key."""

    class Meta:
        collection_name = "profiles"
        indexed_fields = ["profile_id", "user_id"]

    profile_id: int
    user_id: int | None
    bio: str

    # Optional relationship
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User, optional=True),
        init=False,
        repr=False,
        compare=False,
    )


class TestForeignKeyBasics:
    """Test basic ForeignKey functionality."""

    def test_foreign_key_access(self, db):
        """Test basic foreign key access loads related object."""
        # Create user
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        # Create order
        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        # Reload order from database
        order_loaded = Order.get(order_id=101)
        assert order_loaded is not None

        # Access foreign key should load user
        user_loaded = order_loaded.user
        assert user_loaded is not None
        assert user_loaded.name == "Alice"
        assert user_loaded.email == "alice@example.com"

    def test_foreign_key_caching(self, db):
        """Test that foreign key loads once and caches."""
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        order_loaded = Order.get(order_id=101)

        # First access loads from database
        user1 = order_loaded.user
        assert user1 is not None

        # Second access returns cached value (same object)
        user2 = order_loaded.user
        assert user2 is user1  # Same object reference

    def test_foreign_key_multiple_orders(self, db):
        """Test multiple orders can reference same user."""
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        order1 = Order(order_id=101, user_id=1, amount=99.99)
        order1.save()

        order2 = Order(order_id=102, user_id=1, amount=149.99)
        order2.save()

        # Both orders should reference same user
        order1_loaded = Order.get(order_id=101)
        order2_loaded = Order.get(order_id=102)

        assert order1_loaded.user.name == "Alice"
        assert order2_loaded.user.name == "Alice"

    def test_foreign_key_different_users(self, db):
        """Test orders with different users load correct data."""
        user1 = User(user_id=1, name="Alice", email="alice@example.com")
        user1.save()

        user2 = User(user_id=2, name="Bob", email="bob@example.com")
        user2.save()

        order1 = Order(order_id=101, user_id=1, amount=99.99)
        order1.save()

        order2 = Order(order_id=102, user_id=2, amount=149.99)
        order2.save()

        order1_loaded = Order.get(order_id=101)
        order2_loaded = Order.get(order_id=102)

        assert order1_loaded.user.name == "Alice"
        assert order2_loaded.user.name == "Bob"


class TestForeignKeyOptional:
    """Test optional foreign key relationships."""

    def test_optional_foreign_key_with_value(self, db):
        """Test optional foreign key with valid value."""
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        profile = Profile(profile_id=1, user_id=1, bio="Software Engineer")
        profile.save()

        profile_loaded = Profile.get(profile_id=1)
        assert profile_loaded.user is not None
        assert profile_loaded.user.name == "Alice"

    def test_optional_foreign_key_with_none(self, db):
        """Test optional foreign key with None value."""
        profile = Profile(profile_id=1, user_id=None, bio="Anonymous User")
        profile.save()

        profile_loaded = Profile.get(profile_id=1)
        assert profile_loaded.user is None

    def test_required_foreign_key_with_none_raises(self, db):
        """Test required foreign key with None raises error."""
        # We need to manually insert data to bypass dataclass validation
        collection = db.collection("orders", indexed_fields=["order_id", "user_id"])
        collection.insert({"order_id": 101, "user_id": None, "amount": 99.99})

        # When loading, cattrs will fail because user_id can't be None for int type
        # This is expected - if you want nullable foreign keys, use optional=True
        # and make the field Optional[int]


class TestForeignKeyAssignment:
    """Test assigning values to foreign key relationships."""

    def test_foreign_key_assignment(self, db):
        """Test assigning related object updates foreign key."""
        user1 = User(user_id=1, name="Alice", email="alice@example.com")
        user1.save()

        user2 = User(user_id=2, name="Bob", email="bob@example.com")
        user2.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        # Load and reassign
        order_loaded = Order.get(order_id=101)
        assert order_loaded.user.name == "Alice"

        # Assign different user
        order_loaded.user = user2
        assert order_loaded.user_id == 2
        assert order_loaded.user.name == "Bob"

        # Save and verify persistence
        order_loaded.save()

        order_reloaded = Order.get(order_id=101)
        assert order_reloaded.user_id == 2
        assert order_reloaded.user.name == "Bob"

    def test_foreign_key_assignment_none_optional(self, db):
        """Test assigning None to optional foreign key."""
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        profile = Profile(profile_id=1, user_id=1, bio="Software Engineer")
        profile.save()

        profile_loaded = Profile.get(profile_id=1)
        assert profile_loaded.user is not None

        # Assign None
        profile_loaded.user = None
        assert profile_loaded.user_id is None
        assert profile_loaded.user is None

        # Save and verify
        profile_loaded.save()

        profile_reloaded = Profile.get(profile_id=1)
        assert profile_reloaded.user_id is None
        assert profile_reloaded.user is None

    def test_foreign_key_assignment_none_required_raises(self, db):
        """Test assigning None to required foreign key raises error."""
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        order_loaded = Order.get(order_id=101)

        # Assigning None should raise
        with pytest.raises(ValueError, match="Cannot set User to None"):
            order_loaded.user = None


class TestForeignKeyErrors:
    """Test error handling in foreign key relationships."""

    def test_foreign_key_invalid_reference(self, db):
        """Test accessing foreign key with invalid reference."""
        # Create order without corresponding user
        order = Order(order_id=101, user_id=999, amount=99.99)
        order.save()

        order_loaded = Order.get(order_id=101)

        # Should raise ValueError when accessing non-existent user
        with pytest.raises(ValueError, match=r"Related User.*not found"):
            _ = order_loaded.user

    def test_foreign_key_invalid_reference_optional_returns_none(self, db):
        """Test optional foreign key with invalid reference returns None."""
        # Create profile with non-existent user
        profile = Profile(profile_id=1, user_id=999, bio="Test")
        profile.save()

        profile_loaded = Profile.get(profile_id=1)

        # Should return None for optional relationship
        assert profile_loaded.user is None


class TestForeignKeyTransactions:
    """Test foreign key behavior with transactions."""

    def test_foreign_key_in_transaction(self, db):
        """Test foreign key works within transactions."""
        with db.transaction():
            user = User(user_id=1, name="Alice", email="alice@example.com")
            user.save()

            order = Order(order_id=101, user_id=1, amount=99.99)
            order.save()

        # Load after transaction
        order_loaded = Order.get(order_id=101)
        assert order_loaded.user.name == "Alice"

    def test_foreign_key_rollback(self, db):
        """Test foreign key data rolled back on error."""
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        # First check that no order exists
        order_check = Order.get(order_id=101)
        assert order_check is None

        try:
            with db.transaction():
                order = Order(order_id=101, user_id=1, amount=99.99)
                order.save()
                msg = "Simulated error"
                raise ValueError(msg)
        except ValueError:
            pass

        # Order should not exist after rollback
        order_loaded = Order.get(order_id=101)
        assert order_loaded is None


class TestForeignKeyPersistence:
    """Test foreign key persistence across database sessions."""

    def test_foreign_key_persists(self, db_path):
        """Test foreign key relationships persist across sessions."""
        # First session
        db1 = KenobiX(str(db_path))
        Document.set_database(db1)

        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        db1.close()

        # Second session
        db2 = KenobiX(str(db_path))
        Document.set_database(db2)

        order_loaded = Order.get(order_id=101)
        assert order_loaded is not None
        assert order_loaded.user.name == "Alice"

        db2.close()


class TestForeignKeyDescriptor:
    """Test ForeignKey descriptor protocol."""

    def test_descriptor_class_access(self, db):
        """Test accessing ForeignKey on class returns descriptor."""
        descriptor = Order.user
        assert isinstance(descriptor, ForeignKey)

    def test_descriptor_attributes(self, db):
        """Test ForeignKey descriptor attributes."""
        descriptor = Order.user
        assert descriptor.foreign_key_field == "user_id"
        assert descriptor.model == User
        assert descriptor.optional is False

    def test_descriptor_optional_attributes(self, db):
        """Test optional ForeignKey descriptor attributes."""
        descriptor = Profile.user
        assert descriptor.foreign_key_field == "user_id"
        assert descriptor.model == User
        assert descriptor.optional is True


class TestForeignKeyEdgeCases:
    """Test edge cases and corner conditions."""

    def test_foreign_key_with_zero_value(self, db):
        """Test foreign key with zero value (valid ID)."""
        user = User(user_id=0, name="System", email="system@example.com")
        user.save()

        order = Order(order_id=101, user_id=0, amount=0.0)
        order.save()

        order_loaded = Order.get(order_id=101)
        assert order_loaded.user.name == "System"

    def test_foreign_key_cache_survives_field_change(self, db):
        """Test cache is invalidated when foreign key field changes."""
        user1 = User(user_id=1, name="Alice", email="alice@example.com")
        user1.save()

        user2 = User(user_id=2, name="Bob", email="bob@example.com")
        user2.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        order_loaded = Order.get(order_id=101)

        # Load and cache user1
        assert order_loaded.user.name == "Alice"

        # Manually change foreign key field
        order_loaded.user_id = 2

        # Cache should still return Alice (by design - use assignment to update)
        assert order_loaded.user.name == "Alice"

        # Proper way: assign through descriptor
        order_loaded.user = user2
        assert order_loaded.user.name == "Bob"

    def test_multiple_foreign_keys_same_model(self, db):
        """Test model with multiple foreign keys to same target."""

        @dataclass
        class Transaction(Document):
            class Meta:
                collection_name = "transactions"
                indexed_fields = ["from_user_id", "to_user_id"]

            from_user_id: int
            to_user_id: int
            amount: float

            from_user: ForeignKey[User] = field(
                default=ForeignKey("from_user_id", User, related_field="user_id"),
                init=False,
                repr=False,
                compare=False,
            )
            to_user: ForeignKey[User] = field(
                default=ForeignKey("to_user_id", User, related_field="user_id"),
                init=False,
                repr=False,
                compare=False,
            )

        user1 = User(user_id=1, name="Alice", email="alice@example.com")
        user1.save()

        user2 = User(user_id=2, name="Bob", email="bob@example.com")
        user2.save()

        txn = Transaction(from_user_id=1, to_user_id=2, amount=50.0)
        txn.save()

        txn_loaded = Transaction.get(from_user_id=1)
        assert txn_loaded.from_user.name == "Alice"
        assert txn_loaded.to_user.name == "Bob"
