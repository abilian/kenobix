# Changelog

All notable changes to KenobiX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.11.0] - 2026/01/15

### Added
- **New `export` command** - Replaces `dump` with multi-format support:
  - `--format json` (default) - Human-readable JSON export
  - `--format csv` - Comma-separated values (single table, flattens nested fields)
  - `--format sql` - SQL statements preserving KenobiX schema (id + JSON data column)
  - `--format flat-sql` - Denormalized SQL with typed columns (like CSV but as SQL)
  - Nested JSON values are flattened to dot-notation columns in CSV and flat-sql formats
  - SQL formats include `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX` statements

- **Global `-c/--config` option** - Specify config file for any command:
  - `kenobix -c config.toml serve -d mydb.db`
  - Overrides auto-discovery of `kenobix.toml`

### Changed
- **CLI refactored** - One module per subcommand for better maintainability:
  - `cli/export.py` - export command (and deprecated dump alias)
  - `cli/info.py` - info command
  - `cli/serve.py` - serve command
  - `cli/migrate.py` - migrate command
  - `cli/import_cmd.py` - import command

### Deprecated
- `dump` command - Use `export` instead (shows deprecation warning)


## [0.10.0] - 2026-01-12

### Added
- **PostgreSQL Backend Support** - KenobiX now supports PostgreSQL in addition to SQLite:
  - Connection via URL: `KenobiX('postgresql://user:pass@host/db')`
  - Uses JSONB for document storage with GIN index support
  - STORED generated columns for indexed fields
  - Native regex support via `~` operator
  - Connection pooling via psycopg2.pool
  - Install with: `uv add kenobix[postgres]`

- **Database Backend Abstraction** - New `backends` module:
  - `DatabaseBackend` protocol for implementing database backends
  - `SQLDialect` protocol for database-specific SQL syntax
  - `SQLiteBackend` - Default backend (no external dependencies)
  - `PostgreSQLBackend` - Optional PostgreSQL support (requires psycopg2)

- **Database Migration Utilities** - New `migrate` module and CLI commands:
  - `migrate(source, dest)` - Migrate all collections between databases
  - `migrate_collection(source, dest, name)` - Migrate a single collection
  - `export_to_json()` / `import_from_json()` - JSON export/import functions
  - CLI commands:
    - `kenobix migrate source.db dest.db` - Migrate between databases
    - `kenobix import backup.json newdb.db` - Import from JSON file
  - Supports SQLite-to-SQLite, SQLite-to-PostgreSQL, and PostgreSQL-to-SQLite
  - Progress callbacks for monitoring long migrations
  - Batch processing with configurable batch size

### Changed
- Refactored core database layer to use backend abstraction
- `KenobiX` constructor now accepts `connection` parameter (string or Path)
- Added `backend` parameter for explicit backend configuration
- `stats()` now includes `backend` field indicating backend type

### Testing
- 35 new tests for backend abstraction layer (25 SQLite, 10 PostgreSQL)
- 19 new tests for migration utilities
- 10 new tests for migrate/import CLI commands
- PostgreSQL tests skipped if psycopg2 not installed
- Total test count: 426 tests
- Coverage: 91%+


## [0.9.0] - 2026-01-06

### Added
- **Query Lookup Operators** - Django-style filter operators for ODM:
  - `__gt`, `__gte`, `__lt`, `__lte` - Comparison operators
  - `__ne` - Not equal
  - `__in` - Membership in list/tuple/set
  - `__like` - SQL LIKE pattern matching
  - `__isnull` - NULL checking
  - Example: `User.filter(age__gte=18, status__in=["active", "pending"])`

### Testing
- 55 new tests for lookup operators
- Total test count: 362 tests


## [0.8.1] - 2025-12-17

### Added
- **Flexible database specification** - Multiple ways to specify the database:
  - `-d/--database` option (works before or after command)
  - `KENOBIX_DATABASE` environment variable
  - Auto-detection: single `.db` file in current directory
- **Pseudo-schema inference** for `kenobix info -t TABLE`:
  - Infers field types from actual JSON data (string, integer, number, boolean, array, object)
  - Shows field presence percentage (e.g., "80% present" for optional fields)
  - Marks indexed fields with `[indexed]`
  - `-v` shows sample values for each field
  - `-vv` shows underlying SQLite schema and indexes
- `--compact` option for `dump` command - outputs minified JSON
- `-q/--quiet` option - suppresses non-essential output

### Testing
- 35 new tests for database resolution, pseudo-schema, and new options
- Total test count: 307 tests


## [0.8.0] - 2025-12-17

### Added
- **Command-Line Interface** - New `kenobix` CLI tool for database operations
  - `kenobix dump <database>` - Dump database contents in human-readable JSON format
    - `--output/-o` option to save dump to file instead of stdout
    - `--table/-t` option to dump only a specific table
    - Multi-collection support - shows all tables with record counts
  - `kenobix info <database>` - Display database information
    - Basic mode: Shows database size and table names with record counts
    - `-v` (verbose): Shows table details including column and index counts
    - `-vv` (very verbose): Shows full column definitions and index details
  - Multiple command aliases: `kenobix` and `kbx`
  - Zero dependencies - uses only Python standard library (argparse, sqlite3, json)
  - Testable API: `main(argv)` accepts optional arguments for testing without monkeypatching

### Fixed
- Fixed mypy errors: overloaded function signatures now properly distinguish return types
- ODM `filter()` and `all()` overloads now use `Literal[True]`/`Literal[False]` for better type inference

### Testing
- 43 new CLI tests covering all commands, options, error handling, and edge cases
- Total test count: 272 tests (229 existing + 43 new)
- Test coverage: 90%+ maintained


## [0.7.3] - 2025-10-14

### Changed
- **BREAKING: ODM Query API Redesign** - `all()` and `filter()` now default to no limit instead of 100 records
  - `all()` and `filter()` now return all matching records by default (previous behavior: limited to 100)
  - Optional `limit` and `offset` parameters for explicit pagination control
  - New `paginate=True` parameter returns memory-efficient generator for large datasets
  - Generator-based pagination internally fetches in 100-record chunks to avoid excessive memory usage
  - Example: `for user in User.all(paginate=True): process(user)`
  - Principle of Least Astonishment: methods named `all()` now truly return "all" records

### Testing
- 12 new pagination tests covering generator behavior, chunking, filtering, and edge cases
- Total test count: 229 tests (217 existing + 12 new)


## [0.7.2] - 2025-10-13

### Fixed
- Database lock errors in concurrent multiprocessing tests
- ODM cattrs converter now auto-initializes in `__init_subclass__`, eliminating manual setup requirement


## [0.7.1] - 2025-10-13

### Added
- **ODM Relationships** - ForeignKey, RelatedSet, and ManyToMany support for managing relationships between models
  - ForeignKey for many-to-one relationships with lazy loading and caching
  - RelatedSet for one-to-many relationships with query/filter/management methods
  - ManyToMany for many-to-many relationships through automatic junction tables
  - Bidirectional navigation between related objects
  - Full transaction support and ACID compliance
- **Multi-Collection Support** - Multiple isolated collections in a single database
  - Per-collection tables, indexes, and configuration
  - ODM models automatically use separate collections with pluralized names
  - Dictionary-style access and backward compatibility
- **Documentation** - Complete relationship guide with examples (docs/relationships.md)
  - Comprehensive ManyToMany documentation (~540 lines)
  - 8 new examples demonstrating ManyToMany patterns (examples 19-26)
  - Real-world use cases: student enrollment, user roles, product tagging

### Changed
- ODM serialization now skips relationship descriptor fields (ForeignKey, RelatedSet, ManyToMany)

### Testing
- Total test count: 217 tests (195 existing + 22 new)

### Fixed
- Database lock errors in concurrent multiprocessing tests

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
- [examples/transaction_examples.py](examples/transaction_examples.py) - 7 real-world transaction examples.
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
- Python 3.11+ required
- SQLite 3.31.0+ required (for generated columns)

## Links

- **Repository**: https://github.com/abilian/kenobix
- **Original KenobiDB**: https://github.com/patx/kenobi
- **PyPI**: https://pypi.org/project/kenobix/
- **Documentation**: See `docs/` directory
- **Issues**: https://github.com/abilian/kenobix/issues
