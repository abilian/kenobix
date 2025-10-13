# KenobiX

**High-Performance Minimal Document Database** • **SQLite3-Powered** • **One Dependency (cattrs)**

KenobiX is a document database with proper SQLite3 JSON optimization, delivering faster searches and faster updates compared to basic implementations.

Based on [KenobiDB](https://github.com/patx/kenobi) by Harrison Erd, enhanced with generated column indexes and optimized concurrency. ("KenobiX" = "Kenobi + indeX").

<!-- toc -->

- [Why KenobiX?](#why-kenobix)
- [Features](#features)
- [Performance Benchmarks](#performance-benchmarks)
- [ACID Compliance](#acid-compliance)
- [Documentation](#documentation)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Object Document Mapper (ODM)](#object-document-mapper-odm)
  * [Installation](#installation-1)
  * [Usage](#usage)
  * [ODM Features](#odm-features)
  * [ODM Transaction Support](#odm-transaction-support)
- [Multi-Collection Support](#multi-collection-support)
  * [Quick Example](#quick-example)
  * [Benefits](#benefits)
  * [ODM with Collections](#odm-with-collections)
- [ODM Relationships](#odm-relationships)
  * [Quick Example](#quick-example-1)
  * [Many-to-Many Relationships](#many-to-many-relationships)
  * [Relationship Features](#relationship-features)
- [When to Use KenobiX](#when-to-use-kenobix)
  * [Perfect For:](#perfect-for)
  * [Consider Alternatives For:](#consider-alternatives-for)
- [When to Use Transactions](#when-to-use-transactions)
  * [Use Transactions For:](#use-transactions-for)
  * [Auto-commit is Fine For:](#auto-commit-is-fine-for)
- [Index Selection Strategy](#index-selection-strategy)
- [API Documentation](#api-documentation)
  * [Initialization](#initialization)
  * [CRUD Operations](#crud-operations)
  * [Transaction Operations](#transaction-operations)
  * [Advanced Operations](#advanced-operations)
- [Performance Tips](#performance-tips)
- [Migration from KenobiDB](#migration-from-kenobidb)
- [Requirements](#requirements)
- [Testing](#testing)
- [Benchmarking](#benchmarking)
  * [ODM Performance](#odm-performance)
- [Credits](#credits)
- [License](#license)
- [Contributing](#contributing)
- [Links](#links)
- [Changelog](#changelog)

<!-- tocstop -->

## Why KenobiX?

```python
from kenobix import KenobiX

# Create database with indexed fields
db = KenobiX('app.db', indexed_fields=['user_id', 'email', 'status'])

# Lightning-fast queries (0.01ms vs 2.5ms unindexed)
users = db.search('email', 'alice@example.com')

# Massively faster updates (665x improvement on complex documents)
db.update('user_id', 123, {'status': 'active'})
```

## Features

- **ODM Relationships** - ForeignKey, RelatedSet, and ManyToMany support for managing relationships between models
- **Multi-Collection Support** - Organize data into separate collections (like MongoDB or SQL tables)
- **Full ACID Transactions** - Context manager API with savepoints for nested transactions
- **Automatic Index Usage** - Queries automatically use indexes when available, fall back to json_extract
- **VIRTUAL Generated Columns** - Minimal storage overhead (~7-20% depending on document complexity)
- **Thread-Safe** - No RLock on reads, SQLite handles concurrency with WAL mode
- **MongoDB-like API** - Familiar insert/search/update operations
- **Optional ODM Layer** - Type-safe dataclass-based models with per-model collections
- **Cursor Pagination** - Efficient pagination for large datasets
- **Query Analysis** - Built-in `explain()` for optimization
- **Zero Runtime Dependencies** - Only Python stdlib (cattrs optional for ODM)

## Performance Benchmarks

Real-world measurements on a 10,000 document dataset:

| Operation | Without Indexes | With Indexes | Speedup |
|-----------|----------------|--------------|---------|
| Exact search | 6.52ms | 0.009ms | **724x faster** |
| Update 100 docs | 1.29s | 15.55ms | **83x faster** |
| Range-like queries | 2.96ms | 0.52ms | **5.7x faster** |

**Document complexity matters:** More complex documents see even greater benefits (up to 665x for very complex documents).

See `benchmarks/` for detailed performance analysis.

## ACID Compliance

**KenobiX provides full ACID transaction support** backed by SQLite's proven transaction engine:

- ✅ **Atomicity** - All-or-nothing execution with automatic rollback on errors
- ✅ **Consistency** - Data integrity maintained across all operations
- ✅ **Isolation** - Read Committed isolation prevents dirty reads
- ✅ **Durability** - Committed data persists through crashes (WAL mode)

**25/25 comprehensive ACID tests passing (100%)** - See [ACID Compliance](docs/dev/acid-compliance.md) for proof.

```python
# Banking transfer with automatic rollback on error
with db.transaction():
    db.update('account_id', 'A1', {'balance': 900})  # -100
    db.update('account_id', 'A2', {'balance': 1100}) # +100
    # Both succeed or both fail - guaranteed atomicity
```

## Documentation

- **[Getting Started](docs/index.md)** - Quick start guide
- **[Relationships Guide](docs/relationships.md)** - ForeignKey, RelatedSet, and ManyToMany relationships
- **[Collections Guide](docs/collections.md)** - Multi-collection support and usage
- **[Transactions](docs/transactions.md)** - Full ACID transaction API guide
- **[ACID Compliance](docs/dev/acid-compliance.md)** - Comprehensive ACID test results
- **[ODM Guide](docs/odm.md)** - Complete ODM documentation with examples
- **[Performance Guide](docs/performance.md)** - Benchmarks and optimization tips
- **[API Reference](docs/api-reference.md)** - Full API documentation

## Installation

```bash
pip install kenobix
```

Or install from source:

```bash
git clone https://github.com/yourusername/kenobix
cd kenobix
pip install -e .
```

## Quick Start

```python
from kenobix import KenobiX

# Initialize with indexed fields for best performance
db = KenobiX('myapp.db', indexed_fields=['user_id', 'email', 'status'])

# Insert documents
db.insert({'user_id': 1, 'email': 'alice@example.com', 'status': 'active'})
db.insert_many([
    {'user_id': 2, 'email': 'bob@example.com', 'status': 'active'},
    {'user_id': 3, 'email': 'carol@example.com', 'status': 'inactive'}
])

# Fast indexed searches
users = db.search('status', 'active')  # Uses index!
user = db.search('email', 'alice@example.com')  # Uses index!

# Non-indexed fields still work (slower but functional)
tagged = db.search('tags', 'python')  # Falls back to json_extract

# Multi-field optimized search
results = db.search_optimized(status='active', user_id=1)

# Update operations are massively faster
db.update('user_id', 1, {'last_login': '2025-01-15'})

# Efficient cursor-based pagination
result = db.all_cursor(limit=100)
documents = result['documents']
if result['has_more']:
    next_page = db.all_cursor(after_id=result['next_cursor'], limit=100)

# Query optimization
plan = db.explain('search', 'email', 'test@example.com')
print(plan)  # Shows if index is being used

# Transactions for ACID guarantees
with db.transaction():
    # All operations succeed or all fail together
    db.insert({'user_id': 4, 'email': 'dave@example.com', 'balance': 1000})
    db.update('user_id', 1, {'balance': 900})  # Transfer -100
    db.update('user_id', 4, {'balance': 1100}) # Transfer +100
    # Automatic commit on success, rollback on error

# Manual transaction control
db.begin()
try:
    db.insert({'user_id': 5, 'email': 'eve@example.com'})
    db.commit()
except Exception:
    db.rollback()
    raise

# Nested transactions with savepoints
with db.transaction():
    db.insert({'status': 'processing'})
    try:
        with db.transaction():  # Nested - uses savepoint
            db.insert({'status': 'temporary'})
            raise ValueError("Rollback nested only")
    except ValueError:
        pass  # Inner transaction rolled back
    db.insert({'status': 'completed'})
    # Outer transaction commits both 'processing' and 'completed'
```

## Object Document Mapper (ODM)

KenobiX includes an optional ODM layer for type-safe, Pythonic document operations using dataclasses.

### Installation

```bash
pip install kenobix[odm]  # Includes cattrs for serialization
```

### Usage

```python
from dataclasses import dataclass
from typing import List
from kenobix import KenobiX, Document

# Define your models
@dataclass
class User(Document):
    name: str
    email: str
    age: int
    active: bool = True

@dataclass
class Post(Document):
    title: str
    content: str
    author_id: int
    tags: List[str]
    published: bool = False

# Setup
db = KenobiX('app.db', indexed_fields=['email', 'name', 'author_id'])
Document.set_database(db)

# Create
user = User(name="Alice", email="alice@example.com", age=30)
user.save()  # Returns user with _id set

# Read
alice = User.get(email="alice@example.com")
users = User.filter(age=30)
all_users = User.all(limit=100)

# Update
alice.age = 31
alice.save()

# Delete
alice.delete()

# Bulk operations
User.insert_many([user1, user2, user3])
User.delete_many(active=False)

# Count
total = User.count()
active_count = User.count(active=True)
```

### ODM Features

- **Type Safety** - Full type hints with autocomplete support
- **Automatic Serialization** - Uses cattrs for nested structures
- **Indexed Queries** - Automatically uses KenobiX indexes
- **Bulk Operations** - Efficient insert_many, delete_many
- **Familiar API** - Similar to MongoDB ODMs (ODMantic, MongoEngine)
- **Zero Boilerplate** - Just use @dataclass decorator

See `examples/odm_example.py` for complete examples.

### ODM Transaction Support

The ODM layer fully supports transactions:

```python
# Context manager
with User.transaction():
    alice = User(name="Alice", email="alice@example.com", age=30)
    bob = User(name="Bob", email="bob@example.com", age=25)
    alice.save()
    bob.save()
    # Both saved atomically

# Manual control
User.begin()
try:
    user = User.get(email="alice@example.com")
    user.age = 31
    user.save()
    User.commit()
except Exception:
    User.rollback()
    raise
```

See [docs/transactions.md](docs/transactions.md) for complete transaction documentation.

## Multi-Collection Support

KenobiX supports organizing data into multiple collections (similar to MongoDB collections or SQL tables). Each collection has its own table, indexes, and schema within a single database file.

### Quick Example

```python
from kenobix import KenobiX

db = KenobiX('myapp.db')

# Create collections with independent indexes
users = db.collection('users', indexed_fields=['user_id', 'email'])
orders = db.collection('orders', indexed_fields=['order_id', 'user_id'])
products = db.collection('products', indexed_fields=['product_id', 'category'])

# Dictionary-style access
db['users'].insert({'user_id': 1, 'name': 'Alice', 'email': 'alice@example.com'})
db['orders'].insert({'order_id': 101, 'user_id': 1, 'amount': 99.99})

# Each collection is completely isolated
users = db['users'].all(limit=100)
orders = db['orders'].all(limit=100)

# Transactions work across collections
with db.transaction():
    db['users'].insert({'user_id': 2, 'name': 'Bob'})
    db['orders'].insert({'order_id': 102, 'user_id': 2, 'amount': 149.99})
```

### Benefits

- **Better Organization**: Each entity type in its own collection
- **Improved Performance**: Smaller tables with focused indexes
- **Complete Isolation**: No mixing of different document types
- **Independent Indexes**: Each collection can have different indexed fields
- **Type Safety**: Cleaner queries without type field filtering

### ODM with Collections

The ODM layer automatically uses collections:

```python
from dataclasses import dataclass
from kenobix.odm import Document

@dataclass
class User(Document):
    class Meta:
        collection_name = "users"
        indexed_fields = ["user_id", "email"]

    user_id: int
    name: str
    email: str

@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]

    order_id: int
    user_id: int
    amount: float

# Each model uses its own collection
user = User(user_id=1, name='Alice', email='alice@example.com')
user.save()  # -> users collection

order = Order(order_id=101, user_id=1, amount=99.99)
order.save()  # -> orders collection
```

See [docs/collections.md](docs/collections.md) for complete documentation and `examples/collections_example.py` for real-world examples.

## ODM Relationships

KenobiX provides transparent relationship support for modeling connections between documents with ForeignKey, RelatedSet, and ManyToMany relationships.

### Quick Example

```python
from dataclasses import dataclass, field
from kenobix import KenobiX, ForeignKey, RelatedSet, ManyToMany
from kenobix.odm import Document

db = KenobiX('myapp.db')
Document.set_database(db)

# Define models with relationships
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

    # Many-to-one: many orders belong to one user
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),
        init=False,
        repr=False,
        compare=False
    )

# Add reverse relationship
User.orders = RelatedSet(Order, "user_id")

# Usage - transparent lazy loading
user = User(user_id=1, name="Alice")
user.save()

order = Order(order_id=101, user_id=1, amount=99.99)
order.save()

# Access related objects
order = Order.get(order_id=101)
print(order.user.name)  # "Alice" - lazy loads User

user = User.get(user_id=1)
for order in user.orders:
    print(f"Order {order.order_id}: ${order.amount}")
```

### Many-to-Many Relationships

```python
@dataclass
class Student(Document):
    class Meta:
        collection_name = "students"
        indexed_fields = ["student_id"]

    student_id: int
    name: str

@dataclass
class Course(Document):
    class Meta:
        collection_name = "courses"
        indexed_fields = ["course_id"]

    course_id: int
    title: str

# Define bidirectional many-to-many
Student.courses = ManyToMany(
    Course,
    through="enrollments",
    local_field="student_id",
    remote_field="course_id"
)

Course.students = ManyToMany(
    Student,
    through="enrollments",
    local_field="course_id",
    remote_field="student_id"
)

# Usage
student = Student(student_id=1, name="Alice")
student.save()

math = Course(course_id=101, title="Mathematics")
math.save()

# Create relationship
student.courses.add(math)

# Navigate both directions
print(f"{student.name} is enrolled in {len(student.courses)} courses")
print(f"{math.title} has {len(math.students)} students")
```

### Relationship Features

- **ForeignKey** - Many-to-one relationships with lazy loading and caching
- **RelatedSet** - One-to-many reverse relationships with query/filter methods
- **ManyToMany** - Many-to-many relationships through automatic junction tables
- **Bidirectional Navigation** - Navigate relationships from both sides
- **Transaction Support** - All relationship operations are transaction-aware
- **Type Safety** - Full generic type hints for IDE autocomplete

See [docs/relationships.md](docs/relationships.md) for complete documentation and `examples/relationships_example.py` for 26 detailed examples.

## When to Use KenobiX

### Perfect For:
- ✅ Applications with 1,000 - 1,000,000+ documents
- ✅ Frequent searches and updates
- ✅ Known query patterns (can index those fields)
- ✅ Complex document structures
- ✅ Need sub-millisecond query times
- ✅ Prototypes that need to scale

### Consider Alternatives For:
- ⚠️ Pure insert-only workloads (indexing overhead not worth it)
- ⚠️ < 100 documents (overhead not justified)
- ⚠️ Truly massive scale (> 10M documents - use PostgreSQL/MongoDB)

## When to Use Transactions

### Use Transactions For:
- ✅ **Financial operations** - Balance transfers, payments, refunds
- ✅ **Multi-step updates** - Ensuring related data stays consistent
- ✅ **Batch operations** - 50-100x performance boost for bulk inserts
- ✅ **Business logic invariants** - Total inventory, account balances, quotas
- ✅ **Error recovery** - Automatic rollback on exceptions

### Auto-commit is Fine For:
- ⚠️ Single document inserts/updates (no performance benefit)
- ⚠️ Independent operations (no consistency requirements)
- ⚠️ Read-only queries (no transaction needed)

**Performance Note:** Transactions can improve bulk insert performance by 50-100x by deferring commit until the end.

```python
# Without transaction: ~2000ms for 1000 inserts
for doc in documents:
    db.insert(doc)  # Commits after each insert

# With transaction: ~20ms for 1000 inserts (100x faster)
with db.transaction():
    for doc in documents:
        db.insert(doc)  # Single commit at end
```

## Index Selection Strategy

**Rule of thumb:** Index your 3-6 most frequently queried fields.

```python
# Good indexing strategy
db = KenobiX('app.db', indexed_fields=[
    'user_id',      # Primary lookups
    'email',        # Authentication
    'status',       # Filtering
    'created_at',   # Time-based queries
])

# Each index adds ~5-10% insert overhead
# But provides 15-665x speedup on queries/updates
```

## API Documentation

### Initialization

```python
KenobiX(file, indexed_fields=None)
```

- `file`: Path to SQLite database (created if doesn't exist)
- `indexed_fields`: List of document fields to create indexes for

### CRUD Operations

```python
db.insert(document)                    # Insert single document
db.insert_many(documents)              # Bulk insert
db.search(key, value, limit=100)       # Search by field
db.search_optimized(**filters)         # Multi-field search
db.update(key, value, new_dict)        # Update matching documents
db.remove(key, value)                  # Remove matching documents
db.purge()                             # Delete all documents
db.all(limit=100, offset=0)            # Paginated retrieval
```

### Transaction Operations

```python
# Context manager (recommended)
with db.transaction():                 # Auto commit/rollback
    db.insert(...)
    db.update(...)

# Manual control
db.begin()                             # Start transaction
db.commit()                            # Commit changes
db.rollback()                          # Discard changes

# Savepoints (nested transactions)
sp = db.savepoint()                    # Create savepoint
db.rollback_to(sp)                     # Rollback to savepoint
db.release_savepoint(sp)               # Release savepoint
```

### Advanced Operations

```python
db.search_pattern(key, regex)          # Regex search (no index)
db.find_any(key, value_list)           # Match any value
db.find_all(key, value_list)           # Match all values
db.all_cursor(after_id, limit)         # Cursor pagination
db.explain(operation, *args)           # Query plan analysis
db.stats()                             # Database statistics
db.get_indexed_fields()                # List indexed fields
```

## Performance Tips

1. **Index your query fields** - Biggest performance win (15-665x speedup)
2. **Use transactions for bulk operations** - 50-100x faster for batch inserts
3. **Use `search_optimized()` for multi-field queries** - More efficient than chaining
4. **Use cursor pagination for large datasets** - Avoids O(n) OFFSET cost
5. **Batch inserts with `insert_many()`** - Much faster than individual inserts
6. **Check query plans with `explain()`** - Verify indexes are being used

## Migration from KenobiDB

KenobiX is API-compatible with KenobiDB. Simply:

```python
# Old
from kenobi import KenobiDB
db = KenobiDB('app.db')

# New (with performance boost)
from kenobix import KenobiX
db = KenobiX('app.db', indexed_fields=['your', 'query', 'fields'])
```

Existing databases work without modification. Add `indexed_fields` to unlock performance gains.

## Requirements

- Python 3.11+
- SQLite 3.31.0+ (for generated columns)

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage (90%+ coverage maintained)
pytest --cov=kenobix tests/

# Run ACID compliance tests
python3 tests/test_acid_compliance.py  # 25 comprehensive tests
python3 tests/test_transactions.py     # 14 transaction tests

# Run concurrency tests (uses multiprocessing)
python3 tests/test_concurrency.py

# Quick concurrency check
python3 scripts/check_concurrency.py

# Run benchmarks
python benchmarks/benchmark_scale.py
python benchmarks/benchmark_complexity.py
```

**Test Coverage:** KenobiX maintains 90%+ test coverage across:
- Core database operations (kenobix.py: 88%+)
- ODM layer (odm.py: 93%+)
- 217 tests covering CRUD, indexing, concurrency, transactions, ODM, and relationships

**ACID Compliance:** 25/25 comprehensive tests passing (100%):
- 6 atomicity tests (all-or-nothing execution)
- 5 consistency tests (data integrity invariants)
- 5 isolation tests (concurrent transaction safety)
- 7 durability tests (crash recovery simulation)
- 2 combined tests (real-world scenarios)

**Concurrency Tests:** Comprehensive multiprocessing tests verify:
- Multiple readers run in parallel without blocking
- Writers properly serialize via write lock
- Readers not blocked by writers (WAL mode benefit)
- Data integrity under concurrent access
- Race condition detection

See [Concurrency Tests](docs/dev/concurrency-tests.md) for details.

## Benchmarking

Comprehensive benchmarks included:

```bash
# Scale performance (1k-100k documents)
python benchmarks/benchmark_scale.py --sizes "1000,10000,100000"

# Document complexity impact
python benchmarks/benchmark_complexity.py

# ODM vs Raw performance comparison
python benchmarks/benchmark_odm.py --size 10000
```

### ODM Performance

The ODM layer adds overhead for deserialization (cattrs). Results based on robust benchmarks (5 iterations, trimmed mean):

- **Write operations**: ~7-15% slower (very acceptable)
- **Read operations**: ~100-900% slower (cattrs deserialization cost)
- **Count operations**: ~17% slower (minimal deserialization)
- **Trade-off**: Type safety + developer productivity vs 2-10x slower reads

**Key insight:** Write overhead is minimal. Read overhead is significant due to cattrs deserialization, not SQL queries (both use identical indexes).

For read-heavy workloads requiring maximum performance, use raw operations. For applications needing type safety and developer productivity, the ODM overhead is acceptable. You can also use a hybrid approach: ODM for most code, raw for hot paths.

## Credits

**KenobiX** is based on **[KenobiDB](https://github.com/patx/kenobi)** by **Harrison Erd**.

The original KenobiDB provided an excellent foundation with its MongoDB-like API and clean SQLite3 integration. KenobiX builds on this work by adding:

- Full ACID transaction support with context manager API
- Generated column indexes for 15-665x performance improvements
- Optimized concurrency model (no RLock for reads)
- Optional ODM layer with dataclass support
- Cursor-based pagination
- Query plan analysis tools
- Comprehensive benchmark and test suites

Thank you to Harrison Erd for creating KenobiDB!

## License

BSD-3-Clause License (same as original KenobiDB)

Copyright (c) 2025 KenobiX Contributors

Original KenobiDB Copyright (c) Harrison Erd

See LICENSE file for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Links

- **GitHub**: https://github.com/abilian/kenobix
- **Original KenobiDB**: https://github.com/patx/kenobi
- **PyPI**: https://pypi.org/project/kenobix/
- **Benchmarks**: See `benchmarks/` directory

## Changelog

See [CHANGES.md](CHANGES.md) for the complete changelog.
