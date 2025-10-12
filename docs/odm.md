# KenobiX ODM Guide

The KenobiX Object Document Mapper (ODM) provides a type-safe, Pythonic interface for working with documents using dataclasses.

## Installation

```bash
pip install kenobix[odm]
```

Or install `cattrs` separately:

```bash
pip install cattrs
```

## Quick Start

```python
from dataclasses import dataclass
from kenobix import KenobiX, Document

# Define your model
@dataclass
class User(Document):
    name: str
    email: str
    age: int
    active: bool = True

# Setup database
db = KenobiX('app.db', indexed_fields=['email', 'name'])
Document.set_database(db)

# Create and save
user = User(name="Alice", email="alice@example.com", age=30)
user.save()  # _id is now set

# Read
alice = User.get(email="alice@example.com")
users = User.filter(age=30)

# Update
alice.age = 31
alice.save()

# Delete
alice.delete()
```

## Defining Models

### Basic Model

```python
from dataclasses import dataclass
from kenobix import Document

@dataclass
class User(Document):
    name: str
    email: str
    age: int
```

### With Default Values

```python
@dataclass
class User(Document):
    name: str
    email: str
    age: int
    active: bool = True
    role: str = "user"
```

### With Nested Structures

```python
from typing import List

@dataclass
class Post(Document):
    title: str
    content: str
    author_id: int
    tags: List[str]
    published: bool = False
```

## CRUD Operations

### Create

```python
# Single document
user = User(name="Alice", email="alice@example.com", age=30)
user.save()
print(user._id)  # ID is set after save

# Bulk insert
users = [
    User(name="Bob", email="bob@example.com", age=25),
    User(name="Carol", email="carol@example.com", age=28),
]
User.insert_many(users)  # All have _id set
```

### Read

```python
# Get single document by filter
alice = User.get(email="alice@example.com")

# Get by ID
user = User.get_by_id(123)

# Filter multiple documents
young_users = User.filter(age=25)
active_users = User.filter(active=True)

# Pagination
page1 = User.all(limit=10, offset=0)
page2 = User.all(limit=10, offset=10)

# Get all
all_users = User.all()
```

### Update

```python
# Update and save
user = User.get(email="alice@example.com")
user.age = 31
user.email = "alice.new@example.com"
user.save()  # Updates existing document
```

### Delete

```python
# Delete single document
user = User.get(email="alice@example.com")
user.delete()

# Bulk delete
deleted_count = User.delete_many(active=False)
print(f"Deleted {deleted_count} users")
```

### Count

```python
# Count all
total = User.count()

# Count with filter
active_count = User.count(active=True)
age_30_count = User.count(age=30)
```

## Advanced Features

### Indexed Field Queries

The ODM automatically uses KenobiX indexes:

```python
# Setup with indexed fields
db = KenobiX('app.db', indexed_fields=['email', 'name', 'age'])
Document.set_database(db)

# These queries use indexes (fast!)
User.get(email="alice@example.com")      # Uses idx_email
User.filter(name="Bob")                   # Uses idx_name
User.filter(age=30)                       # Uses idx_age

# Non-indexed field still works (slower)
User.filter(role="admin")                 # Uses json_extract
```

### Multiple Models

```python
@dataclass
class User(Document):
    name: str
    email: str

@dataclass
class Post(Document):
    title: str
    author_id: int

# Both use the same database
db = KenobiX('app.db', indexed_fields=['email', 'author_id'])
Document.set_database(db)

# Works independently
user = User(name="Alice", email="alice@example.com")
user.save()

post = Post(title="My Post", author_id=user._id)
post.save()
```

### Complex Nested Structures

```python
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Address(Document):
    street: str
    city: str
    zip: str
    country: str = "USA"

@dataclass
class User(Document):
    name: str
    email: str
    age: int
    tags: List[str]
    metadata: dict
    address_id: Optional[int] = None

# Create with nested structures
user = User(
    name="Alice",
    email="alice@example.com",
    age=30,
    tags=["python", "developer"],
    metadata={"signup_date": "2025-01-15", "referrer": "google"}
)
user.save()

# Nested structures are preserved
retrieved = User.get_by_id(user._id)
print(retrieved.tags)        # ["python", "developer"]
print(retrieved.metadata)    # {"signup_date": "2025-01-15", ...}
```

## ODM Internals

### _id Management

- `_id` is NOT a dataclass field (avoids field ordering conflicts)
- Stored in `__dict__` via `__post_init__()`
- `None` before save, integer after save
- Used for updates and deletes

```python
user = User(name="Alice", email="alice@example.com", age=30)
print(user._id)  # None

user.save()
print(user._id)  # e.g., 123
```

### Serialization

Behind the scenes:

```python
# Save: dataclass → dict → JSON → SQLite
user._to_dict()  # Extract non-private fields
db.insert(data)  # Insert JSON

# Load: SQLite → JSON → dict → dataclass
data = db.get_by_id(123)
User._from_dict(data, doc_id=123)  # Use cattrs.structure()
```

### Database Connection

```python
# Class-level database shared across all models
Document.set_database(db)  # Sets Document._db

# All models use the same database
User.get(...)   # Uses Document._db
Post.get(...)   # Uses Document._db
```

## Best Practices

### 1. Define Indexed Fields

```python
# Index your most queried fields
db = KenobiX('app.db', indexed_fields=[
    'email',      # User lookups
    'author_id',  # Post queries
    'status',     # Filtering
])
```

### 2. Use Type Hints

```python
from typing import List, Optional

@dataclass
class User(Document):
    name: str
    email: str
    age: int
    tags: List[str]
    bio: Optional[str] = None
```

### 3. Default Values for Optional Fields

```python
@dataclass
class User(Document):
    name: str
    email: str
    active: bool = True          # Good: sensible default
    created_at: str = ""          # Avoid: use None or timestamp
    role: str = "user"            # Good: default role
```

### 4. Bulk Operations for Performance

```python
# Slow: Individual saves
for user_data in user_list:
    user = User(**user_data)
    user.save()

# Fast: Bulk insert
users = [User(**data) for data in user_list]
User.insert_many(users)
```

### 5. Check Before Delete

```python
# Always check _id before delete
if user._id:
    user.delete()
else:
    print("User not saved yet")
```

## Error Handling

```python
# Database not set
try:
    user = User(name="Alice", email="alice@example.com", age=30)
    user.save()
except RuntimeError as e:
    print("Did you forget Document.set_database(db)?")

# Delete unsaved document
user = User(name="Bob", email="bob@example.com", age=25)
try:
    user.delete()  # Raises RuntimeError
except RuntimeError as e:
    print("Cannot delete unsaved document")

# Invalid data type
try:
    user = User._from_dict({"age": "not_an_int"}, doc_id=1)
except ValueError as e:
    print("Failed to deserialize document")
```

## Performance

### ODM Overhead

Based on **robust benchmarks** comparing ODM vs raw KenobiX operations (5 iterations, trimmed mean):

**Write Operations (Low Overhead):**
- Bulk insert: ~15% slower
- Delete many: ~13% slower
- Single insert: ~7% slower

**Read Operations (Significant Overhead):**
- Search (indexed): ~900% slower (cattrs deserialization is expensive)
- Retrieve all: ~125% slower (deserializing multiple objects)
- Count: ~17% slower (minimal since no deserialization)

**Why Such High Read Overhead?**
- Raw: SQLite → JSON parse → dict (fast)
- ODM: SQLite → JSON parse → cattrs.structure() → type validation → dataclass creation (slow)
- The overhead is in object construction, not SQL queries (both use identical indexes)

**Key Insights:**
- Write operations have minimal overhead (7-15%)
- Read operations are 2-10x slower due to cattrs deserialization
- Search has highest overhead because it deserializes complex objects
- Count has lowest overhead because it returns a single integer
- Index usage is identical (both use same SQLite indexes)
- Trade-off: Type safety + developer productivity vs read performance

**Benchmark Improvements:**
Previous benchmarks had bugs (e.g., count showed +2100% overhead). Current benchmarks use:
- 5 iterations with trimmed mean (discard min/max)
- Warmup runs for fair cache comparison
- Fresh databases per iteration for bulk operations

**When to Use ODM:**
- Type safety and IDE autocomplete are important
- Code maintainability is a priority
- Write-heavy or balanced workloads
- Can tolerate 2-10x slower reads
- Developer productivity matters more than raw speed
- Want dataclass benefits (equality, repr, etc.)

**When to Use Raw Operations:**
- Maximum read performance is critical
- Read-heavy workloads (hot loops, high-throughput)
- High-throughput applications (100k+ reads/sec)
- Performance-sensitive code paths
- Every millisecond matters

**Hybrid Approach:**
You can mix both in the same application:
```python
# Use ODM for most code (type safety, maintainability)
user = User.get(email="alice@example.com")
user.age = 31
user.save()

# Use raw for performance-critical hot paths
results = db.search('status', 'active')  # 10x faster
for doc in results:
    process_fast(doc)  # Work with dicts
```

**Real-world recommendation:** Start with ODM. Profile your application. Only optimize hot paths to raw operations if profiling identifies ODM as a bottleneck.

### Optimization Tips

1. **Use indexed fields for queries**
   ```python
   # Fast: indexed field
   User.get(email="alice@example.com")

   # Slower: non-indexed field
   User.filter(bio="developer")
   ```

2. **Bulk operations**
   ```python
   # Fast
   User.insert_many(users)

   # Slower
   for user in users:
       user.save()
   ```

3. **Pagination for large datasets**
   ```python
   # Better
   page = User.all(limit=100, offset=0)

   # Avoid loading everything
   all_users = User.all()  # May be slow for large datasets
   ```

## Testing with ODM

```python
import pytest
from kenobix import KenobiX, Document

@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    db = KenobiX(str(db_path), indexed_fields=['email'])
    Document.set_database(db)
    yield db
    db.close()

def test_user_crud(db):
    # Create
    user = User(name="Alice", email="alice@example.com", age=30)
    user.save()
    assert user._id is not None

    # Read
    retrieved = User.get_by_id(user._id)
    assert retrieved.name == "Alice"

    # Update
    retrieved.age = 31
    retrieved.save()

    # Verify
    updated = User.get_by_id(user._id)
    assert updated.age == 31
```

## Migration from Raw KenobiX

```python
# Before: Raw operations
db = KenobiX('app.db')
db.insert({'name': 'Alice', 'email': 'alice@example.com'})
results = db.search('email', 'alice@example.com')

# After: ODM
@dataclass
class User(Document):
    name: str
    email: str

db = KenobiX('app.db', indexed_fields=['email'])
Document.set_database(db)

user = User(name='Alice', email='alice@example.com')
user.save()
retrieved = User.get(email='alice@example.com')
```

## Full Example

See `examples/odm_example.py` for a complete working example with multiple models, relationships, and all CRUD operations.

## API Reference

See [API Reference](api-reference.md) for complete ODM API documentation.
