# Changelog

All notable changes to KenobiX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 0.7.0

### Added

#### Multi-Collection Support
- **Database collections** - Multiple isolated collections in a single database
  - Create collections with `db.collection("name", indexed_fields=[...])`
  - Dictionary-style access: `db["users"].insert({...})`
  - Each collection has its own table and indexes
  - List all collections with `db.collections()`
  - Collection caching for efficient reuse
  - Full backward compatibility: existing code uses default "documents" collection
- **Collection isolation** - Data and indexes are completely separated between collections
  - Each collection can have different indexed fields
  - Queries are scoped to individual collections
  - Transactions work across multiple collections
  - Collection-specific statistics via `collection.stats()`
- **17 collection tests** covering isolation, persistence, transactions, and backward compatibility

#### ODM Collection Support
- **Meta class configuration** for Document models
  - `Meta.collection_name` - Explicit collection name
  - `Meta.indexed_fields` - Per-model index configuration
- **Automatic collection name derivation** from class names
  - `User` → `users`
  - `Category` → `categories` (handles pluralization)
  - `Address` → `addresses`
  - `Box` → `boxes`
- **Per-model collections** - Each ODM model uses its own collection
  - Models are completely isolated from each other
  - Different models can have same field names without conflict
  - Transactions work seamlessly across model collections
- **Collection-specific indexes** - Each model defines its own indexed fields
  - `User` model can index `["email", "user_id"]`
  - `Order` model can index `["order_id", "user_id"]`
  - Indexes are automatically created per collection
- **16 ODM collection tests** covering pluralization, isolation, indexes, and transactions
- **Backward compatibility** - Models without Meta use auto-derived collection names

### Changed

#### Test Infrastructure Improvements
- **Refactored 73 tests** to use pytest fixtures instead of manual `tempfile` management

### Fixed
- **Database lock error** in `test_isolation_concurrent_transactions`
  - Issue: Multiple workers tried to initialize database simultaneously causing "database is locked" error
  - Solution: Create and initialize database before launching multiprocessing workers
  - Prevents race conditions during SQLite WAL mode initialization
- Removed unused `contextlib` import from `test_acid_compliance.py`

### Testing
- All 154 tests passing with improved reliability
- Test execution time: ~2 seconds for full suite
- Better test isolation and cleanup with pytest fixtures
- Improved multiprocessing test stability

## [0.6.0] - 2025-10-12

### Added

#### Full ACID Transaction Support
- Context manager API: `with db.transaction():` for automatic commit/rollback
- Manual control methods: `begin()`, `commit()`, `rollback()`
- Savepoints for nested transactions: `savepoint()`, `rollback_to()`, `release_savepoint()`
- Automatic rollback on exceptions
- Transaction context manager handles nested transactions automatically using savepoints
- 50-100x performance boost for bulk operations when using transactions

#### Comprehensive ACID Testing
- 25 ACID compliance tests with 100% pass rate
- **Atomicity tests** (6 tests): All-or-nothing execution, rollback on errors, large batches
- **Consistency tests** (5 tests): Balance transfers, business rules, referential integrity, counters
- **Isolation tests** (5 tests): No dirty reads, read committed level, concurrent transactions
- **Durability tests** (7 tests): Crash recovery simulation, WAL mode verification, persistence
- **Combined tests** (2 tests): Real-world banking and e-commerce scenarios
- Multiprocessing-based concurrency tests for true parallel access verification

#### ODM Transaction Integration
- `User.transaction()` context manager for ODM models
- `User.begin()`, `User.commit()`, `User.rollback()` class methods
- All ODM operations (save, delete, delete_many) are transaction-aware
- Full integration with savepoints and nested transactions

#### Documentation
- [docs/transactions.md](docs/transactions.md) - Complete transaction API guide with examples
- [docs/dev/acid-compliance.md](docs/dev/acid-compliance.md) - Comprehensive ACID test results and proof
- [examples/transaction_examples.py](examples/transaction_examples.py) - 7 real-world transaction examples:
  - Banking transfers with atomicity
  - Batch imports with error recovery
  - Savepoints for partial rollback
  - Nested transactions
  - ODM transaction usage
  - Performance optimization patterns
  - Manual transaction control
- Transaction examples and best practices in README Quick Start
- "When to Use Transactions" section with performance guidance

### Changed
- All write operations (`insert()`, `insert_many()`, `update()`, `remove()`, `purge()`) are now transaction-aware
- Write operations use `_maybe_commit()` pattern to respect transaction boundaries
- Auto-commit behavior maintained when not in a transaction
- Transaction state management with `_in_transaction` flag and `_savepoint_counter`

### Performance
- Bulk inserts: 50-100x faster when wrapped in transactions
- Zero overhead for single operations (auto-commit mode)
- Deferred commit reduces disk I/O for batch operations

### Testing
- Total test count: 100+ tests covering all features
- Test coverage maintained at 90%+
- New test files:
  - `tests/test_acid_compliance.py` (25 comprehensive ACID tests)
  - `tests/test_transactions.py` (14 basic transaction tests)

## [0.5.0] - 2025-10-11

### Added
- **KenobiX Initial Release** - Based on KenobiDB 4.0 with major enhancements
- **Generated Column Indexes** - VIRTUAL columns for 15-665x performance improvements
- **Optimized Concurrency** - Removed RLock from read operations for true concurrent reads
- **Cursor-Based Pagination** - Efficient `all_cursor()` method avoiding O(n) OFFSET cost
- **Query Plan Analysis** - Built-in `explain()` method for query optimization
- **Multi-Field Search** - `search_optimized()` for efficient multi-field queries
- **Optional ODM Layer** - Type-safe dataclass-based models with cattrs integration
  - Full CRUD operations: `save()`, `get()`, `filter()`, `delete()`
  - Bulk operations: `insert_many()`, `delete_many()`
  - Automatic index usage for queries
  - Type-safe models with zero boilerplate
  - `count()` method for aggregation
- **Performance Benchmarks** - Comprehensive benchmark suite:
  - `benchmarks/benchmark_scale.py` - Scale testing (1k-100k documents)
  - `benchmarks/benchmark_complexity.py` - Document complexity impact
  - `benchmarks/benchmark_odm.py` - ODM vs raw performance
- **Comprehensive Documentation**
  - [docs/index.md](docs/index.md) - Getting Started guide
  - [docs/odm.md](docs/odm.md) - Complete ODM documentation
  - [docs/performance.md](docs/performance.md) - Performance guide and benchmarks
  - [docs/api-reference.md](docs/api-reference.md) - Full API reference
- **Examples**
  - `examples/odm_example.py` - ODM usage examples

### Changed
- Modified `insert()` and `insert_many()` to return document IDs (for ODM integration)
- Enabled WAL (Write-Ahead Logging) mode by default for better concurrency
- Database statistics via `stats()` method
- `get_indexed_fields()` method to list indexed fields

### Performance
- **Exact search**: 724x faster with indexes (6.52ms → 0.009ms)
- **Bulk updates**: 83x faster with indexes (1.29s → 15.55ms)
- **Range queries**: 5.7x faster with indexes (2.96ms → 0.52ms)
- Document complexity multiplier: More complex documents see greater benefits (up to 665x)

### Testing
- 90%+ test coverage across core and ODM
- 81 tests covering CRUD, indexing, concurrency, and ODM features
- Concurrency tests using multiprocessing for true parallel access
- Test documentation: [docs/dev/concurrency-tests.md](docs/dev/concurrency-tests.md)

### Compatibility
- Full API compatibility with KenobiDB
- Existing KenobiDB databases work without modification
- Python 3.9+ required
- SQLite 3.31.0+ required (for generated columns)

## Links

- **Repository**: https://github.com/abilian/kenobix
- **Original KenobiDB**: https://github.com/patx/kenobi
- **PyPI**: https://pypi.org/project/kenobix/
- **Documentation**: See `docs/` directory
- **Issues**: https://github.com/abilian/kenobix/issues
