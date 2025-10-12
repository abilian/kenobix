# KenobiX

**High-Performance Document Database** • **15-665x Faster** • **SQLite3-Powered** • **Zero Dependencies**

KenobiX is a document database with proper SQLite3 JSON optimization, delivering 15-53x faster searches and 80-665x faster updates compared to basic implementations.

Based on [KenobiDB](https://github.com/patx/kenobi) by Harrison Erd, enhanced with generated column indexes and optimized concurrency. ("KenobiX" = "Kenobi + indeX").

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

## Performance Benchmarks

Real-world measurements on a 10,000 document dataset:

| Operation | Without Indexes | With Indexes | Speedup |
|-----------|----------------|--------------|---------|
| Exact search | 6.52ms | 0.009ms | **724x faster** |
| Update 100 docs | 1.29s | 15.55ms | **83x faster** |
| Range-like queries | 2.96ms | 0.52ms | **5.7x faster** |

**Document complexity matters:** More complex documents see even greater benefits (up to 665x for very complex documents).

See `benchmarks/` for detailed performance analysis.

## Features

- **Automatic Index Usage** - Queries automatically use indexes when available, fall back to json_extract
- **VIRTUAL Generated Columns** - Minimal storage overhead (~7-20% depending on document complexity)
- **Thread-Safe** - No RLock on reads, SQLite handles concurrency with WAL mode
- **MongoDB-like API** - Familiar insert/search/update operations
- **Optional ODM Layer** - Type-safe dataclass-based models (install with `pip install kenobix[odm]`)
- **Cursor Pagination** - Efficient pagination for large datasets
- **Query Analysis** - Built-in `explain()` for optimization
- **Zero Runtime Dependencies** - Only Python stdlib (cattrs optional for ODM)

## Documentation

- **[Getting Started](docs/index.md)** - Quick start guide
- **[ODM Guide](docs/odm-guide.md)** - Complete ODM documentation with examples
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

1. **Index your query fields** - Biggest performance win
2. **Use `search_optimized()` for multi-field queries** - More efficient than chaining
3. **Use cursor pagination for large datasets** - Avoids O(n) OFFSET cost
4. **Batch inserts with `insert_many()`** - Much faster than individual inserts
5. **Check query plans with `explain()`** - Verify indexes are being used

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

- Python 3.9+
- SQLite 3.31.0+ (for generated columns)

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage (90%+ coverage maintained)
pytest --cov=kenobix tests/

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
- 81 tests covering CRUD, indexing, concurrency, and ODM features

**Concurrency Tests:** Comprehensive multiprocessing tests verify:
- Multiple readers run in parallel without blocking
- Writers properly serialize via write lock
- Readers not blocked by writers (WAL mode benefit)
- Data integrity under concurrent access
- Race condition detection

See [tests/CONCURRENCY_TESTS.md](tests/CONCURRENCY_TESTS.md) for details.

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

- Generated column indexes for 15-665x performance improvements
- Optimized concurrency model (no RLock for reads)
- Cursor-based pagination
- Query plan analysis tools
- Comprehensive benchmark suite

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

- **GitHub**: https://github.com/yourusername/kenobix
- **Original KenobiDB**: https://github.com/patx/kenobi
- **PyPI**: https://pypi.org/project/kenobix/
- **Benchmarks**: See `benchmarks/` directory

## Changelog

### 0.5.0 (2025-10-11)
- Initial KenobiX release based on KenobiDB 4.0
- Added generated column indexes (15-665x performance improvement)
- Removed RLock from read operations for true concurrency
- Added cursor-based pagination
- Added query plan analysis (`explain()`)
- Added `search_optimized()` for multi-field queries
- Added optional ODM layer with dataclass support and cattrs integration
  - Full CRUD operations: save(), get(), filter(), delete()
  - Bulk operations: insert_many(), delete_many()
  - Automatic index usage for queries
  - Type-safe models with zero boilerplate
- Modified insert/insert_many to return IDs for ODM integration
- Comprehensive benchmark suite (scale and complexity tests)
- Full API compatibility with KenobiDB
- 90%+ test coverage (81 tests covering all features)
- Complete documentation suite (Getting Started, ODM Guide, Performance Guide, API Reference)
