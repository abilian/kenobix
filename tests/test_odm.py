"""
Tests for KenobiX ODM (Object Document Mapper)

Tests cover:
- Basic CRUD operations
- Dataclass integration
- cattrs serialization
- Filtering and querying
- Bulk operations
"""

from dataclasses import dataclass

import cattrs
import pytest

from kenobix import Document, KenobiX


# Test models
@dataclass
class User(Document):
    """Test user model."""

    name: str
    email: str
    age: int
    active: bool = True


@dataclass
class Post(Document):
    """Test post model with nested structure."""

    title: str
    content: str
    author_id: int
    tags: list[str]
    published: bool = False


@dataclass
class Address(Document):
    """Test address model."""

    street: str
    city: str
    zip: str
    country: str = "USA"


# Fixtures
@pytest.fixture
def db_path(tmp_path):
    """Temporary database path."""
    return tmp_path / "test_odm.db"


@pytest.fixture
def db(db_path):
    """Create database with indexed fields."""
    database = KenobiX(
        str(db_path), indexed_fields=["name", "email", "age", "city", "author_id"]
    )
    Document.set_database(database)
    yield database
    database.close()


# Basic CRUD Tests
def test_create_and_save(db):
    """Test creating and saving a document."""
    user = User(name="Alice", email="alice@example.com", age=30)

    # Before save, no ID
    assert user._id is None

    # Save
    user.save()

    # After save, has ID
    assert user._id is not None
    assert user._id > 0


def test_get_by_id(db):
    """Test retrieving document by ID."""
    user = User(name="Bob", email="bob@example.com", age=25)
    user.save()

    # Retrieve by ID
    retrieved = User.get_by_id(user._id)

    assert retrieved is not None
    assert retrieved._id == user._id
    assert retrieved.name == "Bob"
    assert retrieved.email == "bob@example.com"
    assert retrieved.age == 25


def test_get_with_filter(db):
    """Test getting single document with filter."""
    user = User(name="Charlie", email="charlie@example.com", age=35)
    user.save()

    # Get by email (indexed field)
    retrieved = User.get(email="charlie@example.com")

    assert retrieved is not None
    assert retrieved.name == "Charlie"
    assert retrieved.age == 35


def test_get_nonexistent(db):
    """Test getting nonexistent document returns None."""
    result = User.get(email="nonexistent@example.com")
    assert result is None


def test_filter_multiple(db):
    """Test filtering multiple documents."""
    users = [
        User(name="Alice", email="alice@example.com", age=30, active=True),
        User(name="Bob", email="bob@example.com", age=30, active=True),
        User(name="Charlie", email="charlie@example.com", age=25, active=False),
    ]

    for user in users:
        user.save()

    # Filter by age
    age_30 = User.filter(age=30)
    assert len(age_30) == 2
    assert all(u.age == 30 for u in age_30)

    # Filter by active
    active_users = User.filter(active=True)
    assert len(active_users) == 2


def test_filter_with_limit_offset(db):
    """Test filtering with pagination."""
    users = [
        User(name=f"User{i}", email=f"user{i}@example.com", age=20 + i)
        for i in range(10)
    ]

    for user in users:
        user.save()

    # Get first 5
    first_page = User.all(limit=5, offset=0)
    assert len(first_page) == 5

    # Get next 5
    second_page = User.all(limit=5, offset=5)
    assert len(second_page) == 5

    # Verify no overlap
    first_ids = {u._id for u in first_page}
    second_ids = {u._id for u in second_page}
    assert len(first_ids & second_ids) == 0


def test_update(db):
    """Test updating a document."""
    user = User(name="David", email="david@example.com", age=40)
    user.save()
    original_id = user._id

    # Modify and save
    user.age = 41
    user.name = "David Updated"
    user.save()

    # ID should not change
    assert user._id == original_id

    # Retrieve and verify
    retrieved = User.get_by_id(original_id)
    assert retrieved.age == 41
    assert retrieved.name == "David Updated"


def test_delete(db):
    """Test deleting a document."""
    user = User(name="Eve", email="eve@example.com", age=28)
    user.save()
    user_id = user._id

    # Delete
    result = user.delete()
    assert result is True

    # Should not exist anymore
    retrieved = User.get_by_id(user_id)
    assert retrieved is None


def test_delete_unsaved_raises(db):
    """Test deleting unsaved document raises error."""
    user = User(name="Frank", email="frank@example.com", age=33)

    with pytest.raises(RuntimeError, match="Cannot delete unsaved document"):
        user.delete()


def test_delete_many(db):
    """Test bulk delete operation."""
    users = [
        User(name="Alice", email="alice@example.com", age=30, active=True),
        User(name="Bob", email="bob@example.com", age=30, active=False),
        User(name="Charlie", email="charlie@example.com", age=25, active=False),
    ]

    for user in users:
        user.save()

    # Delete inactive users
    deleted = User.delete_many(active=False)
    assert deleted == 2

    # Verify only active users remain
    remaining = User.all()
    assert len(remaining) == 1
    assert remaining[0].active is True


def test_insert_many(db):
    """Test bulk insert operation."""
    users = [
        User(name=f"User{i}", email=f"user{i}@example.com", age=20 + i)
        for i in range(5)
    ]

    # Insert all at once
    User.insert_many(users)

    # All should have IDs
    assert all(u._id is not None for u in users)

    # IDs should be sequential
    ids = [u._id for u in users]
    assert ids == sorted(ids)

    # Verify in database
    all_users = User.all()
    assert len(all_users) == 5


def test_count(db):
    """Test counting documents."""
    users = [
        User(name="Alice", email="alice@example.com", age=30, active=True),
        User(name="Bob", email="bob@example.com", age=30, active=True),
        User(name="Charlie", email="charlie@example.com", age=25, active=False),
    ]

    for user in users:
        user.save()

    # Count all
    total = User.count()
    assert total == 3

    # Count with filter
    active_count = User.count(active=True)
    assert active_count == 2

    age_30_count = User.count(age=30)
    assert age_30_count == 2


# Nested Structure Tests
def test_nested_dataclass(db):
    """Test handling documents with lists."""
    post = Post(
        title="My First Post",
        content="This is the content",
        author_id=1,
        tags=["python", "database", "kenobix"],
        published=True,
    )

    post.save()
    assert post._id is not None

    # Retrieve and verify
    retrieved = Post.get_by_id(post._id)
    assert retrieved.title == "My First Post"
    assert retrieved.tags == ["python", "database", "kenobix"]
    assert retrieved.published is True


def test_default_values(db):
    """Test dataclass default values are preserved."""
    # User has active=True by default
    user = User(name="Grace", email="grace@example.com", age=27)
    assert user.active is True

    user.save()

    retrieved = User.get_by_id(user._id)
    assert retrieved.active is True

    # Address has country="USA" by default
    addr = Address(street="123 Main St", city="Boston", zip="02101")
    assert addr.country == "USA"

    addr.save()
    retrieved_addr = Address.get_by_id(addr._id)
    assert retrieved_addr.country == "USA"


def test_repr(db):
    """Test string representation."""
    user = User(name="Henry", email="henry@example.com", age=45)
    user.save()

    repr_str = repr(user)
    assert "User" in repr_str
    # Note: _id may not be in repr since dataclass generates its own __repr__
    # unless we use @dataclass(repr=False)
    assert "name='Henry'" in repr_str
    assert "email='henry@example.com'" in repr_str

    # But _id should be accessible
    assert user._id is not None


# Error Handling Tests
def test_no_database_set():
    """Test error when database not initialized."""

    # Create a new Document class that doesn't have db set
    @dataclass
    class TempUser(Document):
        name: str

    # Reset database to None
    original_db = Document._db
    Document._db = None

    try:
        with pytest.raises(RuntimeError, match="Database not initialized"):
            TempUser.get(name="test")
    finally:
        # Restore database
        Document._db = original_db


def test_multiple_models(db):
    """Test using multiple model classes."""
    user = User(name="Alice", email="alice@example.com", age=30)
    user.save()

    addr = Address(street="123 Main", city="NYC", zip="10001")
    addr.save()

    # Both should work independently
    retrieved_user = User.get(name="Alice")
    assert retrieved_user is not None
    assert retrieved_user.email == "alice@example.com"

    retrieved_addr = Address.get(city="NYC")
    assert retrieved_addr is not None
    assert retrieved_addr.street == "123 Main"


def test_indexed_vs_nonindexed_fields(db):
    """Test that both indexed and non-indexed fields work."""
    # 'email' is indexed, 'active' is not
    users = [
        User(name="Alice", email="alice@example.com", age=30, active=True),
        User(name="Bob", email="bob@example.com", age=25, active=False),
    ]

    for user in users:
        user.save()

    # Query on indexed field
    alice = User.get(email="alice@example.com")
    assert alice is not None
    assert alice.name == "Alice"

    # Query on non-indexed field
    active_users = User.filter(active=True)
    assert len(active_users) == 1
    assert active_users[0].name == "Alice"


def test_update_indexed_field(db):
    """Test updating an indexed field."""
    user = User(name="Carol", email="carol@example.com", age=35)
    user.save()
    original_id = user._id

    # Update indexed field (email)
    user.email = "carol.new@example.com"
    user.save()

    # Should still have same ID
    assert user._id == original_id

    # Old email should not find it
    old = User.get(email="carol@example.com")
    assert old is None

    # New email should find it
    new = User.get(email="carol.new@example.com")
    assert new is not None
    assert new._id == original_id


def test_from_dict_error_handling(db):
    """Test error handling when deserializing invalid data."""
    # Invalid data that can't be structured into User
    invalid_data = {
        "name": "Alice",
        "email": "alice@example.com",
        "age": "not_an_integer",  # Should be int
    }

    with pytest.raises(ValueError, match="Failed to deserialize document"):
        User._from_dict(invalid_data, doc_id=1)


def test_document_without_dataclass_fields(db):
    """Test Document behavior with minimal dataclass."""

    @dataclass
    class MinimalDoc(Document):
        """Minimal document with just one field."""

        value: str

    minimal = MinimalDoc(value="test")
    minimal.save()

    assert minimal._id is not None

    retrieved = MinimalDoc.get_by_id(minimal._id)
    assert retrieved is not None
    assert retrieved.value == "test"


def test_insert_many_empty_list(db):
    """Test insert_many with empty list."""
    result = User.insert_many([])
    assert result == []


def test_delete_many_no_filters(db):
    """Test delete_many without filters raises error."""
    user = User(name="Alice", email="alice@example.com", age=30)
    user.save()

    with pytest.raises(ValueError, match="delete_many requires at least one filter"):
        User.delete_many()


def test_save_without_database_set():
    """Test save when database not set raises error."""

    @dataclass
    class TempDoc(Document):
        name: str

    # Save original db
    original_db = Document._db
    Document._db = None

    try:
        doc = TempDoc(name="test")
        with pytest.raises(RuntimeError, match="Database not initialized"):
            doc.save()
    finally:
        # Restore database
        Document._db = original_db


def test_filter_with_no_results(db):
    """Test filter that returns no results."""
    user = User(name="Alice", email="alice@example.com", age=30)
    user.save()

    # Filter that won't match
    results = User.filter(age=999)
    assert len(results) == 0


def test_count_with_no_matches(db):
    """Test count with no matching documents."""
    user = User(name="Alice", email="alice@example.com", age=30)
    user.save()

    # Count that won't match
    count = User.count(age=999)
    assert count == 0


def test_get_by_id_nonexistent(db):
    """Test get_by_id with nonexistent ID."""
    result = User.get_by_id(99999)
    assert result is None


def test_document_repr_with_complex_data(db):
    """Test __repr__ with complex nested data."""
    post = Post(
        title="Test Post",
        content="Some content",
        author_id=1,
        tags=["tag1", "tag2", "tag3"],
        published=True,
    )
    post.save()

    repr_str = repr(post)
    assert "Post" in repr_str
    assert "title='Test Post'" in repr_str
    assert "_id" in str(post._id) or "Post(" in repr_str


def test_all_with_empty_database(db):
    """Test all() on empty database."""
    results = User.all()
    assert len(results) == 0


def test_delete_many_with_indexed_field(db):
    """Test delete_many using indexed field."""
    users = [
        User(name="Alice", email="alice@example.com", age=30),
        User(name="Bob", email="bob@example.com", age=30),
        User(name="Charlie", email="charlie@example.com", age=25),
    ]

    for user in users:
        user.save()

    # Delete by indexed field (age)
    deleted = User.delete_many(age=30)
    assert deleted == 2

    # Verify only age=25 remains
    remaining = User.all()
    assert len(remaining) == 1
    assert remaining[0].age == 25
