#!/usr/bin/env python3
"""
KenobiX ODM (Object Document Mapper) Example

This example demonstrates how to use the ODM layer with dataclasses
for type-safe, Pythonic document database operations.

Requirements:
    pip install kenobix[odm]
"""

from dataclasses import dataclass

from kenobix import Document, KenobiX


# Define your models as dataclasses
@dataclass
class User(Document):
    """User model with type hints."""

    name: str
    email: str
    age: int
    active: bool = True  # Default value


@dataclass
class Post(Document):
    """Blog post model with nested structures."""

    title: str
    content: str
    author_id: int
    tags: list[str]
    published: bool = False


def main():
    # 1. Setup database with indexed fields
    print("Setting up database...")
    db = KenobiX("example_odm.db", indexed_fields=["email", "name", "age", "author_id"])

    # Initialize ODM
    Document.set_database(db)
    print("✓ Database initialized\n")

    # 2. Create and save documents
    print("Creating users...")
    alice = User(name="Alice", email="alice@example.com", age=30)
    alice.save()
    print(f"✓ Created: {alice.name} (ID: {alice._id})")

    bob = User(name="Bob", email="bob@example.com", age=25, active=True)
    bob.save()
    print(f"✓ Created: {bob.name} (ID: {bob._id})")

    carol = User(name="Carol", email="carol@example.com", age=35, active=False)
    carol.save()
    print(f"✓ Created: {carol.name} (ID: {carol._id})\n")

    # 3. Bulk insert
    print("Bulk inserting users...")
    users = [
        User(name=f"User{i}", email=f"user{i}@example.com", age=20 + i)
        for i in range(3)
    ]
    User.insert_many(users)
    print(f"✓ Inserted {len(users)} users\n")

    # 4. Query documents
    print("Querying users...")

    # Get by email (indexed - fast!)
    found = User.get(email="alice@example.com")
    if found:
        print(f"✓ Found by email: {found.name}, age {found.age}")

    # Get by ID
    found_by_id = User.get_by_id(bob._id)
    print(f"✓ Found by ID: {found_by_id.name}")

    # Filter by age
    young_users = User.filter(age=25)
    print(f"✓ Users aged 25: {len(young_users)}")

    # Filter with multiple conditions
    active_users = User.filter(active=True)
    print(f"✓ Active users: {len(active_users)}\n")

    # 5. Update documents
    print("Updating documents...")
    alice.age = 31
    alice.email = "alice.new@example.com"
    alice.save()
    print(f"✓ Updated Alice: age={alice.age}, email={alice.email}")

    # Verify update
    updated = User.get_by_id(alice._id)
    print(f"✓ Verified: {updated.name}, age {updated.age}\n")

    # 6. Pagination
    print("Paginating results...")
    # Note: Since User and Post share the same table, we filter by fields
    # to ensure we only get User documents
    page1 = User.filter(active=True, limit=3, offset=0)
    page2 = User.filter(active=True, limit=3, offset=3)
    print(f"✓ Page 1: {len(page1)} users")
    print(f"✓ Page 2: {len(page2)} users\n")

    # 7. Count
    total = User.count()
    active_count = User.count(active=True)
    print(f"✓ Total users: {total}")
    print(f"✓ Active users: {active_count}\n")

    # 8. Working with nested structures
    print("Creating posts with nested data...")
    post = Post(
        title="Getting Started with KenobiX",
        content="KenobiX is a high-performance document database...",
        author_id=alice._id,
        tags=["python", "database", "kenobix", "sqlite"],
        published=True,
    )
    post.save()
    print(f"✓ Created post: {post.title} (ID: {post._id})")
    print(f"  Tags: {', '.join(post.tags)}\n")

    # Query posts by author
    alice_posts = Post.filter(author_id=alice._id)
    print(f"✓ Posts by {alice.name}: {len(alice_posts)}\n")

    # 9. Delete operations
    print("Deleting documents...")

    # Delete single document
    carol.delete()
    print("✓ Deleted user: Carol")

    # Delete many
    deleted = User.delete_many(active=False)
    print(f"✓ Deleted {deleted} inactive users\n")

    # 10. Final stats
    print("Final statistics:")
    remaining = User.count()
    posts_count = Post.count()
    print(f"✓ Remaining users: {remaining}")
    print(f"✓ Total posts: {posts_count}")

    # 11. Performance: indexed vs non-indexed
    print("\nPerformance comparison:")
    import time

    # Indexed search (fast)
    start = time.time()
    _ = User.filter(email="alice.new@example.com")
    indexed_time = time.time() - start
    print(f"✓ Indexed search (email): {indexed_time * 1000:.3f}ms")

    # Non-indexed search (slower)
    start = time.time()
    _ = User.filter(active=True)
    unindexed_time = time.time() - start
    print(f"✓ Non-indexed search (active): {unindexed_time * 1000:.3f}ms")

    if indexed_time > 0:
        speedup = unindexed_time / indexed_time
        print(f"✓ Speedup: {speedup:.1f}x faster with indexes")

    # Cleanup
    db.close()
    print("\n✓ Database closed")


if __name__ == "__main__":
    main()
