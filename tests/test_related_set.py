#!/usr/bin/env python3
"""
Tests for KenobiX ODM RelatedSet (one-to-many relationships).

Tests the RelatedSet descriptor for reverse foreign key relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from kenobix import ForeignKey, KenobiX, RelatedSet
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
class Order(Document):
    """Order model with foreign key to User."""

    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]

    order_id: int
    user_id: int | None  # Nullable to support remove/clear operations
    amount: float


# Forward reference workaround - define User after Order
@dataclass
class User(Document):
    """User model for testing."""

    class Meta:
        collection_name = "users"
        indexed_fields = ["user_id"]

    user_id: int
    name: str


# Now we can add relationships after both classes are defined
def _setup_relationships():
    """Setup bidirectional relationships between User and Order."""
    # This is called at module load time to add relationship descriptors


# Add RelatedSet to User class
User.orders = RelatedSet(Order, "user_id")

# Add ForeignKey to Order class
Order.user = ForeignKey("user_id", User)


class TestRelatedSetBasics:
    """Test basic RelatedSet functionality."""

    def test_related_set_all(self, db):
        """Test getting all related objects."""
        # Create user
        user = User(user_id=1, name="Alice")
        user.save()

        # Create orders
        order1 = Order(order_id=101, user_id=1, amount=99.99)
        order1.save()

        order2 = Order(order_id=102, user_id=1, amount=149.99)
        order2.save()

        order3 = Order(order_id=103, user_id=1, amount=49.99)
        order3.save()

        # Load user and get orders
        user_loaded = User.get(user_id=1)
        assert user_loaded is not None

        orders = user_loaded.orders.all()
        assert len(orders) == 3
        assert all(order.user_id == 1 for order in orders)

    def test_related_set_empty(self, db):
        """Test related set with no related objects."""
        user = User(user_id=1, name="Alice")
        user.save()

        user_loaded = User.get(user_id=1)
        orders = user_loaded.orders.all()
        assert len(orders) == 0

    def test_related_set_filter(self, db):
        """Test filtering related objects."""
        user = User(user_id=1, name="Alice")
        user.save()

        # Create orders with different amounts
        Order(order_id=101, user_id=1, amount=50.0).save()
        Order(order_id=102, user_id=1, amount=150.0).save()
        Order(order_id=103, user_id=1, amount=250.0).save()

        user_loaded = User.get(user_id=1)

        # Filter by amount
        expensive_orders = user_loaded.orders.filter(amount=250.0)
        assert len(expensive_orders) == 1
        assert expensive_orders[0].amount == 250.0

    def test_related_set_count(self, db):
        """Test counting related objects."""
        user = User(user_id=1, name="Alice")
        user.save()

        # Create orders
        Order(order_id=101, user_id=1, amount=99.99).save()
        Order(order_id=102, user_id=1, amount=149.99).save()
        Order(order_id=103, user_id=1, amount=49.99).save()

        user_loaded = User.get(user_id=1)
        count = user_loaded.orders.count()
        assert count == 3

    def test_related_set_iteration(self, db):
        """Test iterating over related set."""
        user = User(user_id=1, name="Alice")
        user.save()

        Order(order_id=101, user_id=1, amount=99.99).save()
        Order(order_id=102, user_id=1, amount=149.99).save()

        user_loaded = User.get(user_id=1)

        # Iterate using for loop
        order_ids = [order.order_id for order in user_loaded.orders]

        assert len(order_ids) == 2
        assert 101 in order_ids
        assert 102 in order_ids

    def test_related_set_len(self, db):
        """Test len() on related set."""
        user = User(user_id=1, name="Alice")
        user.save()

        Order(order_id=101, user_id=1, amount=99.99).save()
        Order(order_id=102, user_id=1, amount=149.99).save()

        user_loaded = User.get(user_id=1)
        assert len(user_loaded.orders) == 2


class TestRelatedSetIsolation:
    """Test that related sets are properly isolated between users."""

    def test_related_set_isolation(self, db):
        """Test that each user has their own orders."""
        # Create users
        user1 = User(user_id=1, name="Alice")
        user1.save()

        user2 = User(user_id=2, name="Bob")
        user2.save()

        # Create orders for different users
        Order(order_id=101, user_id=1, amount=99.99).save()
        Order(order_id=102, user_id=1, amount=149.99).save()
        Order(order_id=103, user_id=2, amount=49.99).save()

        # Load users
        user1_loaded = User.get(user_id=1)
        user2_loaded = User.get(user_id=2)

        # Check isolation
        assert len(user1_loaded.orders) == 2
        assert len(user2_loaded.orders) == 1

        # Verify correct orders
        user1_orders = user1_loaded.orders.all()
        assert all(order.user_id == 1 for order in user1_orders)

        user2_orders = user2_loaded.orders.all()
        assert all(order.user_id == 2 for order in user2_orders)


class TestRelatedSetManagement:
    """Test add/remove/clear methods."""

    def test_related_set_add(self, db):
        """Test adding objects to related set."""
        user = User(user_id=1, name="Alice")
        user.save()

        # Create order without saving
        new_order = Order(
            order_id=101, user_id=0, amount=99.99
        )  # Wrong user_id initially

        user_loaded = User.get(user_id=1)

        # Add order to user's orders
        user_loaded.orders.add(new_order)

        # Verify order was updated and saved
        order_loaded = Order.get(order_id=101)
        assert order_loaded is not None
        assert order_loaded.user_id == 1

        # Verify it appears in user's orders
        assert len(user_loaded.orders) == 1

    def test_related_set_remove(self, db):
        """Test removing objects from related set."""
        user = User(user_id=1, name="Alice")
        user.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        user_loaded = User.get(user_id=1)
        assert len(user_loaded.orders) == 1

        # Remove order
        order_to_remove = user_loaded.orders.all()[0]
        user_loaded.orders.remove(order_to_remove)

        # Verify order still exists but user_id is None
        order_loaded = Order.get(order_id=101)
        assert order_loaded is not None
        assert order_loaded.user_id is None

        # Verify it no longer appears in user's orders
        # Need to get fresh user instance to see updated state
        user_reloaded = User.get(user_id=1)
        assert len(user_reloaded.orders) == 0

    def test_related_set_clear(self, db):
        """Test clearing all objects from related set."""
        user = User(user_id=1, name="Alice")
        user.save()

        # Create multiple orders
        Order(order_id=101, user_id=1, amount=99.99).save()
        Order(order_id=102, user_id=1, amount=149.99).save()
        Order(order_id=103, user_id=1, amount=49.99).save()

        user_loaded = User.get(user_id=1)
        assert len(user_loaded.orders) == 3

        # Clear all orders
        user_loaded.orders.clear()

        # Verify all orders still exist but user_id is None
        for order_id in [101, 102, 103]:
            order = Order.get(order_id=order_id)
            assert order is not None
            assert order.user_id is None

        # Verify user has no orders
        user_reloaded = User.get(user_id=1)
        assert len(user_reloaded.orders) == 0


class TestRelatedSetWithTransactions:
    """Test related set behavior with transactions."""

    def test_related_set_in_transaction(self, db):
        """Test related set works within transactions."""
        with db.transaction():
            user = User(user_id=1, name="Alice")
            user.save()

            order1 = Order(order_id=101, user_id=1, amount=99.99)
            order1.save()

            order2 = Order(order_id=102, user_id=1, amount=149.99)
            order2.save()

        # Load after transaction
        user_loaded = User.get(user_id=1)
        assert len(user_loaded.orders) == 2

    def test_related_set_rollback(self, db):
        """Test related set data rolled back on error."""
        user = User(user_id=1, name="Alice")
        user.save()

        # First check that no order exists
        user_check = User.get(user_id=1)
        assert len(user_check.orders) == 0

        try:
            with db.transaction():
                order = Order(order_id=101, user_id=1, amount=99.99)
                order.save()
                msg = "Simulated error"
                raise ValueError(msg)
        except ValueError:
            pass

        # Order should not exist after rollback
        user_loaded = User.get(user_id=1)
        assert len(user_loaded.orders) == 0


class TestRelatedSetPersistence:
    """Test related set persistence across database sessions."""

    def test_related_set_persists(self, db_path):
        """Test related set relationships persist across sessions."""
        # First session
        db1 = KenobiX(str(db_path))
        Document.set_database(db1)

        user = User(user_id=1, name="Alice")
        user.save()

        Order(order_id=101, user_id=1, amount=99.99).save()
        Order(order_id=102, user_id=1, amount=149.99).save()

        db1.close()

        # Second session
        db2 = KenobiX(str(db_path))
        Document.set_database(db2)

        user_loaded = User.get(user_id=1)
        assert user_loaded is not None
        assert len(user_loaded.orders) == 2

        db2.close()


class TestRelatedSetDescriptor:
    """Test RelatedSet descriptor protocol."""

    def test_descriptor_class_access(self, db):
        """Test accessing RelatedSet on class returns descriptor."""
        descriptor = User.orders
        assert isinstance(descriptor, RelatedSet)

    def test_descriptor_attributes(self, db):
        """Test RelatedSet descriptor attributes."""
        descriptor = User.orders
        assert descriptor.related_model == Order
        assert descriptor.foreign_key_field == "user_id"
        assert descriptor.local_field == "user_id"

    def test_descriptor_prevents_direct_assignment(self, db):
        """Test that direct assignment to RelatedSet raises error."""
        user = User(user_id=1, name="Alice")
        user.save()

        user_loaded = User.get(user_id=1)

        # Attempting to assign directly should raise AttributeError
        with pytest.raises(
            AttributeError, match="Cannot directly assign to RelatedSet"
        ):
            user_loaded.orders = []  # type: ignore[misc]


class TestRelatedSetEdgeCases:
    """Test edge cases and corner conditions."""

    def test_related_set_with_none_local_field(self, db):
        """Test related set when local field is None."""
        # This would require a model with nullable primary key
        # which is unusual but should be handled gracefully

    def test_related_set_manager_caching(self, db):
        """Test that manager is cached per instance."""
        user = User(user_id=1, name="Alice")
        user.save()

        user_loaded = User.get(user_id=1)

        # Get manager twice
        manager1 = user_loaded.orders
        manager2 = user_loaded.orders

        # Should be same object (cached)
        assert manager1 is manager2

    def test_related_set_with_limit(self, db):
        """Test related set with limit parameter."""
        user = User(user_id=1, name="Alice")
        user.save()

        # Create many orders
        for i in range(150):
            Order(order_id=100 + i, user_id=1, amount=float(i)).save()

        user_loaded = User.get(user_id=1)

        # Default limit is 100
        orders_default = user_loaded.orders.all()
        assert len(orders_default) == 100

        # Custom limit
        orders_limited = user_loaded.orders.all(limit=50)
        assert len(orders_limited) == 50

    def test_bidirectional_relationship(self, db):
        """Test that ForeignKey and RelatedSet work together."""
        user = User(user_id=1, name="Alice")
        user.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        # Access from order to user (ForeignKey)
        order_loaded = Order.get(order_id=101)
        assert order_loaded.user.name == "Alice"

        # Access from user to orders (RelatedSet)
        user_loaded = User.get(user_id=1)
        user_orders = user_loaded.orders.all()
        assert len(user_orders) == 1
        assert user_orders[0].order_id == 101
