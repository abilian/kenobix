# KenobiX Concurrency Tests

This document describes the concurrency testing infrastructure for KenobiX, which verifies thread-safe and process-safe database operations.

## Overview

KenobiX is designed for concurrent access with:
- **WAL mode** (Write-Ahead Logging) for better concurrency
- **No read locks** - Multiple readers can access simultaneously
- **Write locks** - Writes serialize properly via `RLock`
- **Process-safe** - Multiple processes can access the same database file

## Test Files

### 1. `test_concurrency.py` - Comprehensive Test Suite

Full pytest test suite with 6 test scenarios:

```bash
# Run with pytest (if installed)
pytest tests/test_concurrency.py -v

# Or run directly
python3 tests/test_concurrency.py
```

**Tests included:**

1. **`test_multiple_concurrent_readers`**
   - Launches 4 processes, each performing 200 read operations
   - Verifies readers can run in parallel without blocking
   - Measures speedup from parallelism

2. **`test_concurrent_writers`**
   - Launches 4 processes, each performing 25 write operations
   - Verifies all writes complete successfully
   - Checks data integrity (all records present)

3. **`test_concurrent_readers_and_writers`**
   - Mixed workload: 3 reader processes + 2 writer processes
   - Each performs 30 operations
   - Verifies readers aren't blocked by writers (WAL mode benefit)

4. **`test_race_conditions`**
   - 4 processes increment a shared counter 20 times each
   - Demonstrates lost updates from read-modify-write races
   - Shows why application-level locking is needed for complex transactions

5. **`test_high_concurrency_stress`**
   - 10 processes, 20 operations each
   - Stress test with many concurrent writers
   - Verifies data integrity under load

6. **`test_database_integrity_after_concurrent_access`**
   - Verifies database remains consistent after heavy concurrent access
   - Checks all records present and accounted for
   - Verifies indexes still work correctly

### 2. `scripts/check_concurrency.py` - Quick Demonstration Script

Standalone script that demonstrates concurrency behavior:

```bash
python3 scripts/check_concurrency.py
```

**Output shows:**
- Wall clock time vs average worker time (parallelism verification)
- Throughput metrics (ops/sec)
- Data integrity confirmation
- Summary of concurrency capabilities

**Tests included:**
1. 4 concurrent readers (100 reads each)
2. 4 concurrent writers (50 writes each)
3. Mixed workload (3 readers + 2 writers, 50 ops each)

## Key Findings

### ✓ Multiple Readers Scale

Multiple reader processes can access the database simultaneously without blocking each other. This is enabled by:
- SQLite WAL mode
- No read locks in KenobiX code

### ✓ Writers Serialize Correctly

Multiple writers properly serialize via the write lock (`RLock`), ensuring:
- No data corruption
- All writes complete successfully
- No lost updates (except in race conditions)

### ✓ Readers Not Blocked by Writers

Readers can continue reading while writes are happening. This is a key benefit of WAL mode:
- Readers use the WAL
- Writers append to the WAL
- No blocking between readers and writers

### ⚠️ Application-Level Transactions Needed

For read-modify-write operations (like incrementing a counter), application code must implement proper locking:

```python
# ❌ WRONG - Race condition
results = db.search("key", "counter")
value = results[0]["value"]
db.update("key", "counter", {"value": value + 1})  # Lost updates!

# ✓ CORRECT - Use application-level lock
with some_lock:
    results = db.search("key", "counter")
    value = results[0]["value"]
    db.update("key", "counter", {"value": value + 1})
```

The `test_race_conditions` test demonstrates this - without application locking, many increments are lost.

## Implementation Details

### Why Multiprocessing?

Tests use `multiprocessing` (not `threading`) because:
1. **True parallelism** - Each process has its own Python interpreter
2. **Separate SQLite connections** - Each process opens its own connection to the database file
3. **Real-world simulation** - Mimics actual production scenarios with multiple application instances

### Process Communication

Each worker function:
1. Opens its own database connection
2. Performs operations
3. Closes connection
4. Returns statistics (elapsed time, operation counts)

### Database Setup

For tests to work correctly:
- All processes must use the **same indexed fields** when opening the database
- Cannot dynamically add indexes from different processes
- Initial setup creates the database with all required indexes

## Performance Notes

### Multiprocessing Overhead

For very small tasks (< 10ms), multiprocessing overhead can dominate:
- Process spawn time: ~20-50ms per process
- IPC (inter-process communication) overhead
- Results: `avg_worker_time` may be less than `wall_clock_time`

This is expected and doesn't indicate a concurrency problem - just that the overhead of spawning processes exceeds the work being done.

### Speedup Expectations

Expected speedup depends on workload:
- **Read-heavy**: Near-linear speedup (4 processes → ~3-4x faster)
- **Write-heavy**: Limited speedup (writes serialize)
- **Mixed**: Intermediate speedup

## Troubleshooting

### "No such column" errors

This happens when processes try to create indexes with different field names:

```python
# Process 1
db = KenobiX("test.db", indexed_fields=["name", "age"])

# Process 2 - ERROR!
db = KenobiX("test.db", indexed_fields=["name", "age", "email"])
```

**Solution**: All processes must use the same indexed_fields list.

### Very slow tests

If tests take much longer than expected:
- Check disk I/O (slow disk affects SQLite)
- Reduce number of operations per worker
- Check for resource contention

### Tests fail on CI

Set the multiprocessing start method explicitly:

```python
multiprocessing.set_start_method("spawn", force=True)
```

This ensures consistent behavior across platforms.

## Future Improvements

Potential enhancements:
1. **Connection pooling** - Reuse connections across operations
2. **Batch operations** - Group multiple operations
3. **Optimistic locking** - Version-based conflict resolution
4. **Read replicas** - Separate read and write databases

## References

- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [Python multiprocessing](https://docs.python.org/3/library/multiprocessing.html)
- [SQLite Concurrency](https://www.sqlite.org/lockingv3.html)
