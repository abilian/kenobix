#!/usr/bin/env python3
"""
KenobiX Collections Example

Demonstrates multi-collection support with a real-world e-commerce scenario.
Shows how to organize data into separate collections, work with transactions,
and use collections with the ODM layer.
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from kenobix import KenobiX
from kenobix.odm import Document


def example_1_basic_collections():
    """Example 1: Basic collection creation and usage."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Collections")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Open database
        db = KenobiX(db_path)

        # Create collections with indexed fields
        users = db.collection("users", indexed_fields=["user_id", "email"])
        products = db.collection("products", indexed_fields=["product_id", "category"])

        # Insert into users collection
        users.insert({
            "user_id": 1,
            "name": "Alice",
            "email": "alice@example.com",
            "role": "customer",
        })

        # Insert into products collection
        products.insert({
            "product_id": 101,
            "name": "Laptop",
            "category": "electronics",
            "price": 999.99,
        })

        # Query each collection
        user = users.search("user_id", 1)[0]
        print(f"User: {user['name']} ({user['email']})")

        product = products.search("product_id", 101)[0]
        print(f"Product: {product['name']} - ${product['price']}")

        # List all collections
        print(f"\nCollections in database: {db.collections()}")

        # Get collection stats
        user_stats = users.stats()
        print(f"Users collection: {user_stats['count']} documents")

        db.close()

    finally:
        Path(db_path).unlink()


def example_2_dict_style_access():
    """Example 2: Dictionary-style collection access."""
    print("\n" + "=" * 60)
    print("Example 2: Dictionary-Style Access")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)

        # Dictionary-style access is more concise
        db["users"].insert({"user_id": 1, "name": "Alice"})
        db["orders"].insert({"order_id": 101, "user_id": 1, "amount": 99.99})

        # Query using dict-style
        users = db["users"].all(limit=100)
        orders = db["orders"].all(limit=100)

        print(f"Users: {len(users)}")
        print(f"Orders: {len(orders)}")

        # Collections are cached - same instance
        users1 = db["users"]
        users2 = db["users"]
        print(f"Collections cached: {users1 is users2}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_3_transactions_across_collections():
    """Example 3: Transactions spanning multiple collections."""
    print("\n" + "=" * 60)
    print("Example 3: Transactions Across Collections")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)

        # Atomic operation across collections
        with db.transaction():
            db["users"].insert({"user_id": 1, "name": "Alice", "balance": 1000.0})

            db["orders"].insert({
                "order_id": 101,
                "user_id": 1,
                "amount": 99.99,
                "status": "completed",
            })

            db["transactions"].insert({
                "transaction_id": 501,
                "user_id": 1,
                "amount": -99.99,
                "type": "purchase",
            })

        print("Transaction committed: User, Order, and Transaction created")

        # Verify all data is present
        print(f"Users: {len(db['users'].all(limit=10))}")
        print(f"Orders: {len(db['orders'].all(limit=10))}")
        print(f"Transactions: {len(db['transactions'].all(limit=10))}")

        # Demonstrate rollback
        try:
            with db.transaction():
                db["users"].insert({"user_id": 2, "name": "Bob"})
                db["orders"].insert({"order_id": 102, "user_id": 2})
                msg = "Simulated error"
                raise ValueError(msg)
        except ValueError:
            print("\nTransaction rolled back due to error")

        # User 2 and Order 102 were not committed
        assert len(db["users"].all(limit=10)) == 1
        assert len(db["orders"].all(limit=10)) == 1
        print("Verified: Rollback successful")

        db.close()

    finally:
        Path(db_path).unlink()


def example_4_ecommerce_application():
    """Example 4: Complete e-commerce application with collections."""
    print("\n" + "=" * 60)
    print("Example 4: E-commerce Application")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)

        # Setup collections with appropriate indexes
        customers = db.collection("customers", indexed_fields=["customer_id", "email"])
        products = db.collection("products", indexed_fields=["product_id", "category"])
        orders = db.collection("orders", indexed_fields=["order_id", "customer_id"])
        order_items = db.collection(
            "order_items", indexed_fields=["order_id", "product_id"]
        )

        # Insert sample data
        print("\nSetting up e-commerce data...")

        # Customers
        customers.insert_many([
            {"customer_id": 1, "name": "Alice", "email": "alice@example.com"},
            {"customer_id": 2, "name": "Bob", "email": "bob@example.com"},
        ])

        # Products
        products.insert_many([
            {
                "product_id": 101,
                "name": "Laptop",
                "category": "electronics",
                "price": 999.99,
            },
            {
                "product_id": 102,
                "name": "Mouse",
                "category": "electronics",
                "price": 29.99,
            },
            {
                "product_id": 103,
                "name": "Desk",
                "category": "furniture",
                "price": 299.99,
            },
        ])

        # Create an order with items (atomic)
        with db.transaction():
            # Insert order
            orders.insert({
                "order_id": 1001,
                "customer_id": 1,
                "timestamp": time.time(),
                "status": "completed",
                "total": 1029.98,
            })

            # Insert order items
            order_items.insert_many([
                {
                    "order_id": 1001,
                    "product_id": 101,
                    "quantity": 1,
                    "price": 999.99,
                },
                {
                    "order_id": 1001,
                    "product_id": 102,
                    "quantity": 1,
                    "price": 29.99,
                },
            ])

        print("Order 1001 created with 2 items")

        # Query order details
        order = orders.search("order_id", 1001)[0]
        items = order_items.search("order_id", 1001)

        print("\nOrder Details:")
        print(f"  Order ID: {order['order_id']}")
        print(f"  Customer ID: {order['customer_id']}")
        print(f"  Status: {order['status']}")
        print(f"  Total: ${order['total']}")
        print(f"  Items: {len(items)}")

        for item in items:
            product = products.search("product_id", item["product_id"])[0]
            print(f"    - {product['name']}: {item['quantity']} x ${item['price']}")

        # Query by category
        electronics = products.search("category", "electronics")
        print(f"\nElectronics products: {len(electronics)}")
        for product in electronics:
            print(f"  - {product['name']}: ${product['price']}")

        # Customer order history
        customer_orders = orders.search("customer_id", 1)
        print(f"\nAlice's orders: {len(customer_orders)}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_5_odm_with_collections():
    """Example 5: Using ODM with collections."""
    print("\n" + "=" * 60)
    print("Example 5: ODM with Collections")
    print("=" * 60)

    # Define models with Meta class
    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id", "email"]

        user_id: int
        name: str
        email: str
        active: bool = True

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]

        order_id: int
        user_id: int
        amount: float
        status: str = "pending"

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Create and save users
        alice = User(user_id=1, name="Alice", email="alice@example.com")
        alice.save()

        bob = User(user_id=2, name="Bob", email="bob@example.com")
        bob.save()

        print(f"Created users: {alice.name}, {bob.name}")

        # Create orders
        order1 = Order(order_id=101, user_id=1, amount=99.99, status="completed")
        order1.save()

        order2 = Order(order_id=102, user_id=1, amount=149.99, status="pending")
        order2.save()

        print(f"Created orders: {order1.order_id}, {order2.order_id}")

        # Query by model
        all_users = User.all()
        print(f"\nTotal users: {len(all_users)}")

        alice_orders = Order.filter(user_id=1)
        print(f"Alice's orders: {len(alice_orders)}")

        # Calculate total
        total = sum(order.amount for order in alice_orders)
        print(f"Alice's total: ${total}")

        # Update
        order2.status = "completed"
        order2.save()
        print(f"\nOrder {order2.order_id} status updated to {order2.status}")

        # Transaction with ODM
        with db.transaction():
            user3 = User(user_id=3, name="Carol", email="carol@example.com")
            user3.save()

            order3 = Order(order_id=103, user_id=3, amount=199.99)
            order3.save()

        print("Atomic operation: User and Order created together")

        # Verify collections are separate
        print(f"\nCollections in database: {db.collections()}")
        print(f"Users count: {User.count()}")
        print(f"Orders count: {Order.count()}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_6_auto_derived_collection_names():
    """Example 6: Auto-derived collection names with pluralization."""
    print("\n" + "=" * 60)
    print("Example 6: Auto-Derived Collection Names")
    print("=" * 60)

    @dataclass
    class User(Document):
        # No Meta - auto-derives "users"
        user_id: int
        name: str

    @dataclass
    class Category(Document):
        # No Meta - auto-derives "categories" (handles irregular plural)
        category_id: int
        name: str

    @dataclass
    class Address(Document):
        # No Meta - auto-derives "addresses"
        address_id: int
        street: str

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Save instances
        user = User(user_id=1, name="Alice")
        user.save()

        category = Category(category_id=1, name="Electronics")
        category.save()

        address = Address(address_id=1, street="123 Main St")
        address.save()

        # Check collection names
        collections = db.collections()
        print("Auto-derived collection names:")
        print(f"  User -> {collections[0] if collections else 'N/A'}")
        print(f"  Category -> {collections[1] if len(collections) > 1 else 'N/A'}")
        print(f"  Address -> {collections[2] if len(collections) > 2 else 'N/A'}")

        # Verify data
        print(f"\nUsers: {User.count()}")
        print(f"Categories: {Category.count()}")
        print(f"Addresses: {Address.count()}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_7_collection_isolation():
    """Example 7: Demonstrate complete collection isolation."""
    print("\n" + "=" * 60)
    print("Example 7: Collection Isolation")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)

        # Same field names in different collections - no conflict
        db["users"].insert({"id": 1, "name": "Alice", "type": "person"})
        db["products"].insert({"id": 1, "name": "Widget", "type": "item"})
        db["categories"].insert({"id": 1, "name": "Electronics", "type": "category"})

        print("Inserted documents with ID=1 into three collections")

        # Query each collection independently
        user = db["users"].search("id", 1)[0]
        product = db["products"].search("id", 1)[0]
        category = db["categories"].search("id", 1)[0]

        print(f"\nUsers collection:      {user}")
        print(f"Products collection:   {product}")
        print(f"Categories collection: {category}")

        # Different indexes per collection
        users = db.collection("users", indexed_fields=["id", "name"])
        products = db.collection("products", indexed_fields=["id", "type"])

        print(f"\nUsers indexed fields:    {users.get_indexed_fields()}")
        print(f"Products indexed fields: {products.get_indexed_fields()}")

        # Verify isolation - update doesn't affect other collections
        db["users"].update("id", 1, {"name": "Alice Updated"})

        user_updated = db["users"].search("id", 1)[0]
        product_unchanged = db["products"].search("id", 1)[0]

        print("\nAfter updating users collection:")
        print(f"  User name: {user_updated['name']}")
        print(f"  Product name: {product_unchanged['name']} (unchanged)")

        db.close()

    finally:
        Path(db_path).unlink()


def example_8_audit_logging():
    """Example 8: Using collections for audit logging."""
    print("\n" + "=" * 60)
    print("Example 8: Audit Logging with Collections")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)

        # Setup collections
        users = db.collection("users", indexed_fields=["user_id"])
        audit = db.collection(
            "audit_logs", indexed_fields=["timestamp", "user_id", "action"]
        )

        def log_action(user_id: int, action: str, details: dict):
            """Helper to log actions to audit collection."""
            audit.insert({
                "timestamp": time.time(),
                "user_id": user_id,
                "action": action,
                "details": details,
            })

        # Create user with audit log
        with db.transaction():
            users.insert({"user_id": 1, "name": "Alice", "role": "admin"})
            log_action(1, "user_created", {"name": "Alice", "role": "admin"})

        print("User created with audit log")

        # Update user with audit log
        with db.transaction():
            users.update("user_id", 1, {"role": "superadmin"})
            log_action(1, "role_changed", {"old": "admin", "new": "superadmin"})

        print("User role updated with audit log")

        # Query audit logs
        user_logs = audit.search("user_id", 1)
        print(f"\nAudit logs for user 1: {len(user_logs)} entries")
        for log in user_logs:
            print(f"  - {log['action']}: {log['details']}")

        # Recent activity
        all_logs = audit.all(limit=100)
        print(f"\nTotal audit entries: {len(all_logs)}")

        db.close()

    finally:
        Path(db_path).unlink()


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# KenobiX Collections Examples")
    print("#" * 60)

    example_1_basic_collections()
    example_2_dict_style_access()
    example_3_transactions_across_collections()
    example_4_ecommerce_application()
    example_5_odm_with_collections()
    example_6_auto_derived_collection_names()
    example_7_collection_isolation()
    example_8_audit_logging()

    print("\n" + "#" * 60)
    print("# All examples completed successfully!")
    print("#" * 60 + "\n")


if __name__ == "__main__":
    main()
