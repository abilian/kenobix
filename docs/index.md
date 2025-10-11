# KenobiX Documentation

**High-Performance Document Database** • **15-665x Faster** • **SQLite3-Powered**

Welcome to the KenobiX documentation. KenobiX is a high-performance document database built on SQLite3, enhanced with generated column indexes for massive performance improvements.

## Quick Links

- **[Getting Started](#getting-started)** - Installation and first steps
- **[ODM Guide](odm-guide.md)** - Object Document Mapper with dataclasses
- **[Performance Guide](performance.md)** - Optimization and benchmarks
- **[API Reference](api-reference.md)** - Complete API documentation

## Getting Started

### Installation

```bash
pip install kenobix

# Or with ODM support
pip install kenobix[odm]
```

### Basic Usage

```python
from kenobix import KenobiX

# Create database with indexed fields
db = KenobiX('app.db', indexed_fields=['user_id', 'email', 'status'])

# Insert documents
db.insert({'user_id': 1, 'email': 'alice@example.com', 'status': 'active'})

# Lightning-fast indexed searches
users = db.search('email', 'alice@example.com')  # Uses index!

# Update operations
db.update('user_id', 1, {'status': 'inactive'})
```

## Key Features

### 🚀 Massive Performance Gains

- **15-53x faster searches** on indexed fields
- **80-665x faster updates** compared to basic implementations
- Sub-millisecond query times on 10k+ documents

### 🎯 Automatic Index Usage

- Queries automatically use indexes when available
- Falls back to `json_extract` for non-indexed fields
- Built-in `explain()` for query optimization

### 📦 Zero Runtime Dependencies

- Only Python stdlib required
- Optional: `cattrs` for ODM support
- No external database needed

### 🔒 Thread-Safe

- Lock-free reads for true concurrency
- WAL mode for optimal performance
- ThreadPoolExecutor for async operations

### 💎 Optional ODM Layer

- Type-safe models with dataclasses
- Automatic serialization with cattrs
- MongoDB-like API (save, get, filter, delete)

## Architecture

KenobiX uses SQLite's **generated VIRTUAL columns** to create indexes on JSON fields:

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    email TEXT GENERATED ALWAYS AS (json_extract(data, '$.email')) VIRTUAL
)
CREATE INDEX idx_email ON documents(email)
```

This allows indexed queries on JSON fields with minimal storage overhead (~7-20%).

## Performance Comparison

Real-world measurements on 10,000 documents:

| Operation | Without Indexes | With Indexes | Speedup |
|-----------|----------------|--------------|---------|
| Exact search | 6.52ms | 0.009ms | **724x** |
| Update 100 docs | 1.29s | 15.55ms | **83x** |
| Range queries | 2.96ms | 0.52ms | **5.7x** |

## When to Use KenobiX

### Perfect For ✅

- Applications with 1,000 - 1,000,000+ documents
- Frequent searches and updates
- Known query patterns (can index those fields)
- Complex document structures
- Need sub-millisecond query times
- Prototypes that need to scale

### Consider Alternatives ⚠️

- Pure insert-only workloads (indexing overhead not worth it)
- < 100 documents (overhead not justified)
- > 10M documents (use PostgreSQL/MongoDB)

## Documentation Structure

- **[ODM Guide](odm-guide.md)** - Complete guide to the Object Document Mapper
- **[Performance Guide](performance.md)** - Benchmarks and optimization tips
- **[API Reference](api-reference.md)** - Full API documentation

## Requirements

- Python 3.9+
- SQLite 3.31.0+ (for generated columns)

## Testing

KenobiX maintains **90%+ test coverage** with 81 comprehensive tests:

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=kenobix tests/
```

## Credits

Based on **[KenobiDB](https://github.com/patx/kenobi) by Harrison Erd**.

KenobiX adds generated column indexes, optimized concurrency, cursor pagination, and ODM support.

## License

BSD-3-Clause License

Copyright (c) 2025 KenobiX Contributors
Original KenobiDB Copyright (c) Harrison Erd
