#!/usr/bin/env python3
"""
KenobiX Relationships Example

Demonstrates ForeignKey relationships with a real-world blog and e-commerce scenario.
Shows lazy loading, caching, optional relationships, transactions, and best practices.
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from kenobix import ForeignKey, KenobiX
from kenobix.odm import Document


def example_1_basic_foreign_key():
    """Example 1: Basic ForeignKey relationship with lazy loading."""
    print("\n" + "=" * 60)
    print("Example 1: Basic ForeignKey Relationship")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str
        email: str

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]

        order_id: int
        user_id: int  # Foreign key field
        amount: float

        # Relationship declaration
        user: ForeignKey[User] = field(
            default=ForeignKey("user_id", User), init=False, repr=False, compare=False
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Create user
        user = User(user_id=1, name="Alice", email="alice@example.com")
        user.save()
        print(f"Created user: {user.name}")

        # Create order referencing user
        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()
        print(f"Created order: {order.order_id}")

        # Load order from database
        order_loaded = Order.get(order_id=101)
        print(f"\nLoaded order {order_loaded.order_id}")

        # Access related user (lazy loads)
        print(f"Order user: {order_loaded.user.name}")
        print(f"Order email: {order_loaded.user.email}")

        # Second access uses cache (no query)
        print(f"User again (cached): {order_loaded.user.name}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_2_optional_relationships():
    """Example 2: Optional ForeignKey relationships (nullable)."""
    print("\n" + "=" * 60)
    print("Example 2: Optional Relationships")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str

    @dataclass
    class Profile(Document):
        class Meta:
            collection_name = "profiles"
            indexed_fields = ["profile_id", "user_id"]

        profile_id: int
        user_id: int | None  # Nullable foreign key
        bio: str

        # Optional relationship
        user: ForeignKey[User] = field(
            default=ForeignKey("user_id", User, optional=True),
            init=False,
            repr=False,
            compare=False,
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Create user
        user = User(user_id=1, name="Alice")
        user.save()

        # Profile with user
        profile1 = Profile(profile_id=1, user_id=1, bio="Software Engineer")
        profile1.save()
        print(f"Created profile 1 with user: {profile1.bio}")

        # Profile without user (anonymous)
        profile2 = Profile(profile_id=2, user_id=None, bio="Anonymous User")
        profile2.save()
        print(f"Created profile 2 without user: {profile2.bio}")

        # Load and access
        p1_loaded = Profile.get(profile_id=1)
        print(f"\nProfile 1 user: {p1_loaded.user.name}")

        p2_loaded = Profile.get(profile_id=2)
        print(f"Profile 2 user: {p2_loaded.user}")  # None

        db.close()

    finally:
        Path(db_path).unlink()


def example_3_multiple_foreign_keys():
    """Example 3: Multiple ForeignKeys to the same model."""
    print("\n" + "=" * 60)
    print("Example 3: Multiple Foreign Keys")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str

    @dataclass
    class Transaction(Document):
        class Meta:
            collection_name = "transactions"
            indexed_fields = ["transaction_id", "from_user_id", "to_user_id"]

        transaction_id: int
        from_user_id: int
        to_user_id: int
        amount: float

        # Two relationships to same model
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

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Create users
        alice = User(user_id=1, name="Alice")
        alice.save()

        bob = User(user_id=2, name="Bob")
        bob.save()

        print(f"Created users: {alice.name}, {bob.name}")

        # Create transaction
        txn = Transaction(
            transaction_id=5001, from_user_id=1, to_user_id=2, amount=50.0
        )
        txn.save()
        print(f"Created transaction: {txn.transaction_id}")

        # Load and access both relationships
        txn_loaded = Transaction.get(transaction_id=5001)
        print(f"\nTransaction ${txn_loaded.amount}")
        print(f"  From: {txn_loaded.from_user.name}")
        print(f"  To: {txn_loaded.to_user.name}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_4_assignment_and_updates():
    """Example 4: Assigning related objects and updating relationships."""
    print("\n" + "=" * 60)
    print("Example 4: Assignment and Updates")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]

        order_id: int
        user_id: int
        amount: float

        user: ForeignKey[User] = field(
            default=ForeignKey("user_id", User), init=False, repr=False, compare=False
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Create users
        alice = User(user_id=1, name="Alice")
        alice.save()

        bob = User(user_id=2, name="Bob")
        bob.save()

        # Create order for Alice
        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()
        print(f"Created order {order.order_id} for {alice.name}")

        # Load order
        order_loaded = Order.get(order_id=101)
        print(f"Current user: {order_loaded.user.name}")

        # Reassign to Bob
        order_loaded.user = bob
        print(f"\nReassigned order to {bob.name}")
        print(f"Foreign key updated: user_id={order_loaded.user_id}")

        # Save changes
        order_loaded.save()
        print("Saved changes to database")

        # Reload and verify
        order_reloaded = Order.get(order_id=101)
        print(f"Reloaded order - user is now: {order_reloaded.user.name}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_5_error_handling():
    """Example 5: Error handling with relationships."""
    print("\n" + "=" * 60)
    print("Example 5: Error Handling")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]

        order_id: int
        user_id: int
        amount: float

        user: ForeignKey[User] = field(
            default=ForeignKey("user_id", User), init=False, repr=False, compare=False
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Create order with invalid user_id
        order = Order(order_id=101, user_id=999, amount=99.99)
        order.save()
        print(f"Created order {order.order_id} with invalid user_id=999")

        # Try to access user
        order_loaded = Order.get(order_id=101)
        try:
            user = order_loaded.user
            print(f"User: {user.name}")
        except ValueError as e:
            print(f"\nError accessing user: {e}")

        # Fix by creating the user
        user = User(user_id=999, name="Unknown User")
        user.save()
        print("\nCreated missing user")

        # Now it works
        order_reloaded = Order.get(order_id=101)
        print(f"Order user: {order_reloaded.user.name}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_6_transactions():
    """Example 6: Relationships with transactions."""
    print("\n" + "=" * 60)
    print("Example 6: Relationships with Transactions")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]

        order_id: int
        user_id: int
        amount: float

        user: ForeignKey[User] = field(
            default=ForeignKey("user_id", User), init=False, repr=False, compare=False
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Atomic creation of related objects
        print("Creating user and order atomically...")
        with db.transaction():
            user = User(user_id=1, name="Alice")
            user.save()

            order = Order(order_id=101, user_id=1, amount=99.99)
            order.save()

        print("Transaction committed")

        # Verify
        order_loaded = Order.get(order_id=101)
        print(f"Order user: {order_loaded.user.name}")

        # Rollback scenario
        print("\nAttempting transaction that will fail...")
        try:
            with db.transaction():
                user2 = User(user_id=2, name="Bob")
                user2.save()

                order2 = Order(order_id=102, user_id=2, amount=149.99)
                order2.save()

                # Simulate error
                msg = "Simulated error"
                raise ValueError(msg)
        except ValueError:
            print("Transaction rolled back")

        # Verify rollback
        user2_check = User.get(user_id=2)
        order2_check = Order.get(order_id=102)
        print(f"User 2 exists: {user2_check is not None}")  # False
        print(f"Order 102 exists: {order2_check is not None}")  # False

        db.close()

    finally:
        Path(db_path).unlink()


def example_7_blog_application():
    """Example 7: Complete blog application with relationships."""
    print("\n" + "=" * 60)
    print("Example 7: Blog Application")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id", "username"]

        user_id: int
        username: str
        email: str

    @dataclass
    class Post(Document):
        class Meta:
            collection_name = "posts"
            indexed_fields = ["post_id", "author_id"]

        post_id: int
        author_id: int
        title: str
        content: str
        timestamp: float

        author: ForeignKey[User] = field(
            default=ForeignKey("author_id", User, related_field="user_id"),
            init=False,
            repr=False,
            compare=False,
        )

    @dataclass
    class Comment(Document):
        class Meta:
            collection_name = "comments"
            indexed_fields = ["comment_id", "post_id", "author_id"]

        comment_id: int
        post_id: int
        author_id: int
        content: str
        timestamp: float

        post: ForeignKey[Post] = field(
            default=ForeignKey("post_id", Post), init=False, repr=False, compare=False
        )
        author: ForeignKey[User] = field(
            default=ForeignKey("author_id", User, related_field="user_id"),
            init=False,
            repr=False,
            compare=False,
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        print("Setting up blog data...\n")

        # Create users
        alice = User(user_id=1, username="alice", email="alice@example.com")
        alice.save()

        bob = User(user_id=2, username="bob", email="bob@example.com")
        bob.save()

        print(f"Created users: {alice.username}, {bob.username}")

        # Create post
        post = Post(
            post_id=1,
            author_id=1,
            title="Introduction to KenobiX",
            content="KenobiX is a high-performance document database...",
            timestamp=time.time(),
        )
        post.save()
        print(f"Created post by {post.author.username}: {post.title}")

        # Create comments
        comment1 = Comment(
            comment_id=1,
            post_id=1,
            author_id=2,
            content="Great post!",
            timestamp=time.time(),
        )
        comment1.save()

        comment2 = Comment(
            comment_id=2,
            post_id=1,
            author_id=1,
            content="Thanks!",
            timestamp=time.time(),
        )
        comment2.save()

        print(f"Created {Comment.count()} comments")

        # Display blog content
        print("\n--- Blog Post ---")
        post_loaded = Post.get(post_id=1)
        print(f"Title: {post_loaded.title}")
        print(f"Author: {post_loaded.author.username}")
        print(f"Content: {post_loaded.content}")

        print("\n--- Comments ---")
        comments = Comment.filter(post_id=1, limit=100)
        for comment in comments:
            print(f"{comment.author.username}: {comment.content}")
            print(f"  (on post: {comment.post.title})")

        db.close()

    finally:
        Path(db_path).unlink()


def example_8_ecommerce_with_relationships():
    """Example 8: E-commerce application with complex relationships."""
    print("\n" + "=" * 60)
    print("Example 8: E-commerce with Relationships")
    print("=" * 60)

    @dataclass
    class Customer(Document):
        class Meta:
            collection_name = "customers"
            indexed_fields = ["customer_id", "email"]

        customer_id: int
        name: str
        email: str

    @dataclass
    class Product(Document):
        class Meta:
            collection_name = "products"
            indexed_fields = ["product_id", "category"]

        product_id: int
        name: str
        price: float
        category: str

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "customer_id"]

        order_id: int
        customer_id: int
        total: float
        timestamp: float
        status: str

        customer: ForeignKey[Customer] = field(
            default=ForeignKey("customer_id", Customer),
            init=False,
            repr=False,
            compare=False,
        )

    @dataclass
    class OrderItem(Document):
        class Meta:
            collection_name = "order_items"
            indexed_fields = ["order_id", "product_id"]

        order_id: int
        product_id: int
        quantity: int
        price: float

        order: ForeignKey[Order] = field(
            default=ForeignKey("order_id", Order), init=False, repr=False, compare=False
        )
        product: ForeignKey[Product] = field(
            default=ForeignKey("product_id", Product),
            init=False,
            repr=False,
            compare=False,
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        print("Setting up e-commerce data...\n")

        # Create customer
        customer = Customer(
            customer_id=1, name="Alice Johnson", email="alice@example.com"
        )
        customer.save()
        print(f"Customer: {customer.name}")

        # Create products
        laptop = Product(
            product_id=101, name="Laptop", price=999.99, category="electronics"
        )
        laptop.save()

        mouse = Product(
            product_id=102, name="Mouse", price=29.99, category="electronics"
        )
        mouse.save()

        print(f"Products: {laptop.name}, {mouse.name}")

        # Create order with items (atomic)
        print("\nCreating order...")
        with db.transaction():
            # Create order
            order = Order(
                order_id=1001,
                customer_id=1,
                total=1029.98,
                timestamp=time.time(),
                status="completed",
            )
            order.save()

            # Create order items
            item1 = OrderItem(order_id=1001, product_id=101, quantity=1, price=999.99)
            item1.save()

            item2 = OrderItem(order_id=1001, product_id=102, quantity=1, price=29.99)
            item2.save()

        print("Order created successfully")

        # Display order details with relationships
        print("\n--- Order Details ---")
        order_loaded = Order.get(order_id=1001)
        print(f"Order ID: {order_loaded.order_id}")
        print(f"Customer: {order_loaded.customer.name}")
        print(f"Email: {order_loaded.customer.email}")
        print(f"Status: {order_loaded.status}")
        print(f"Total: ${order_loaded.total}")

        print("\n--- Order Items ---")
        items = OrderItem.filter(order_id=1001, limit=100)
        for item in items:
            print(f"  {item.product.name}:")
            print(f"    Quantity: {item.quantity}")
            print(f"    Price: ${item.price}")
            print(f"    Category: {item.product.category}")

        # Calculate order total from items
        calculated_total = sum(item.price * item.quantity for item in items)
        print(f"\nCalculated total: ${calculated_total}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_9_caching_behavior():
    """Example 9: Understanding lazy loading and caching."""
    print("\n" + "=" * 60)
    print("Example 9: Lazy Loading and Caching")
    print("=" * 60)

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]

        order_id: int
        user_id: int
        amount: float

        user: ForeignKey[User] = field(
            default=ForeignKey("user_id", User), init=False, repr=False, compare=False
        )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        # Create data
        user = User(user_id=1, name="Alice")
        user.save()

        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()

        # Load order
        order_loaded = Order.get(order_id=101)
        print("Order loaded (user not loaded yet)")

        # First access - lazy loads user
        print(f"\nFirst access: {order_loaded.user.name}")
        print("  ^ User loaded from database")

        # Second access - uses cache
        print(f"Second access: {order_loaded.user.name}")
        print("  ^ User loaded from cache (no query)")

        # Third access - still cached
        print(f"Third access: {order_loaded.user.name}")
        print("  ^ User loaded from cache (no query)")

        # Verify same object
        user1 = order_loaded.user
        user2 = order_loaded.user
        print(f"\nSame object reference: {user1 is user2}")

        db.close()

    finally:
        Path(db_path).unlink()


def example_10_best_practices():
    """Example 10: Best practices for relationships."""
    print("\n" + "=" * 60)
    print("Example 10: Best Practices")
    print("=" * 60)

    # Good: Index foreign key fields
    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]  # ← Index foreign key!

        order_id: int
        user_id: int
        amount: float

    # Good: Use optional for nullable relationships
    @dataclass
    class Profile(Document):
        class Meta:
            collection_name = "profiles"
            indexed_fields = ["profile_id", "user_id"]

        profile_id: int
        user_id: int | None  # Nullable
        bio: str

    # Good: Use transactions for related changes
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)
        Document.set_database(db)

        print("Best Practice #1: Index foreign keys")
        print("  ✓ Order.user_id is indexed for fast lookups")

        print("\nBest Practice #2: Use optional for nullable FKs")
        print("  ✓ Profile.user_id is Optional[int] with optional=True")

        print("\nBest Practice #3: Use transactions")
        print("  ✓ Create related objects atomically")

        print("\nBest Practice #4: Use descriptive names")
        print("  ✓ from_user, to_user (not user1, user2)")

        print("\nBest Practice #5: Assign through descriptor")
        print("  ✓ order.user = new_user (not order.user_id = new_id)")

        db.close()

    finally:
        Path(db_path).unlink()


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# KenobiX Relationships Examples")
    print("#" * 60)

    example_1_basic_foreign_key()
    example_2_optional_relationships()
    example_3_multiple_foreign_keys()
    example_4_assignment_and_updates()
    example_5_error_handling()
    example_6_transactions()
    example_7_blog_application()
    example_8_ecommerce_with_relationships()
    example_9_caching_behavior()
    example_10_best_practices()

    print("\n" + "#" * 60)
    print("# All examples completed successfully!")
    print("#" * 60 + "\n")


if __name__ == "__main__":
    main()
