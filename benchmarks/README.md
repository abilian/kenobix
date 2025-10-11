# KenobiX Benchmarks

Comprehensive benchmark suite demonstrating KenobiX performance with and without indexes.

## Available Benchmarks

### 1. Scale Benchmarks (`benchmark_scale.py`)

Tests performance across different dataset sizes.

**Usage:**
```bash
# Test with default sizes (1k, 10k, 100k)
python benchmarks/benchmark_scale.py

# Custom sizes
python benchmarks/benchmark_scale.py --sizes "1000,5000,10000"

# Include 1M test (WARNING: very slow, ~5-10 minutes)
python benchmarks/benchmark_scale.py --max-size

# Different document patterns
python benchmarks/benchmark_scale.py --pattern simple
python benchmarks/benchmark_scale.py --pattern medium  # default
python benchmarks/benchmark_scale.py --pattern complex

# Output formats
python benchmarks/benchmark_scale.py --output csv
python benchmarks/benchmark_scale.py --output json
```

**What it measures:**
- Bulk insert performance
- Indexed field search
- Non-indexed field search
- Range queries (multiple searches)
- Pagination performance
- Database file size

**Expected results:**
- 15-665x faster searches with indexes
- Slight insert overhead due to index creation
- Minimal storage overhead (7-20%, VIRTUAL columns)

### 2. Complexity Benchmarks (`benchmark_complexity.py`)

Tests how document complexity affects performance.

**Usage:**
```bash
# Test all complexity levels with 10k documents each
python benchmarks/benchmark_complexity.py

# Custom document count
python benchmarks/benchmark_complexity.py --size 50000

# Test specific complexity levels
python benchmarks/benchmark_complexity.py --complexities "simple,medium"

# Output formats
python benchmarks/benchmark_complexity.py --output table  # default
python benchmarks/benchmark_complexity.py --output csv
python benchmarks/benchmark_complexity.py --output json
```

**Document complexity levels:**
1. **Simple** (~50 bytes): 3 fields (id, name, value)
2. **Medium** (~100 bytes): 6 fields with mixed types
3. **Complex** (~300 bytes): 10+ fields with nested structures
4. **Very Complex** (~1KB): Large nested JSON, arrays, deep nesting

**What it measures:**
- Insert performance across complexity levels
- Search performance (indexed vs unindexed)
- Update operations
- File size impact
- How complexity affects indexing benefits

**Expected results:**
- More complex documents benefit more from indexing
- Insert overhead increases with complexity
- Search speedup more pronounced with complex docs

### 3. ODM vs Raw Benchmarks (`benchmark_odm.py`)

Compares performance of the ODM layer (dataclasses + cattrs) vs raw dictionary operations.

**Usage:**
```bash
# Test with default size (10k documents)
python benchmarks/benchmark_odm.py

# Custom size
python benchmarks/benchmark_odm.py --size 5000

# Output formats
python benchmarks/benchmark_odm.py --output table  # default
python benchmarks/benchmark_odm.py --output csv
python benchmarks/benchmark_odm.py --output json
```

**Methodology:**
- **Robust statistics**: Each test runs 5 times with trimmed mean (discard min/max, average remaining 3)
- **Warmup runs**: Ensures SQLite caches are populated equally for fair comparison
- **Fresh databases**: Bulk insert tests use fresh databases each iteration
- **Data restoration**: Delete tests re-insert data between iterations

This methodology minimizes variance from GC, disk I/O, scheduler jitter, and cache effects.

**What it measures:**
- Bulk insert (ODM vs raw)
- Single insert overhead (averaged over 100 inserts)
- Search by indexed field
- Retrieve all (pagination, 100 documents)
- Count operations
- Delete many operations

**Expected results (10,000 documents):**

| Operation | Raw | ODM | Overhead |
|-----------|-----|-----|----------|
| Bulk Insert | 45ms | 52ms | +15% |
| Search (indexed) | 15µs | 150µs | +900% |
| Retrieve All (100) | 200µs | 450µs | +125% |
| Count | 300µs | 350µs | +17% |
| Delete Many | 30ms | 34ms | +13% |
| Single Insert | 150µs | 160µs | +7% |

**Key insights:**
- Write operations: ~7-15% overhead (very acceptable)
- Read operations: ~100-900% overhead (cattrs deserialization cost)
- Count operation: Fixed from previous bug, now shows realistic ~17% overhead
- ODM should NEVER be faster than raw (any negative overhead is measurement noise)
- Trade-off: Type safety + developer productivity vs 2-10x slower reads
- Both use identical indexes (no query performance difference)

**When to use ODM:**
- Type safety and IDE autocomplete important
- Code maintainability priority
- Write-heavy or balanced workloads
- Can tolerate 2-10x slower reads
- Developer productivity matters more than raw speed

**When to use raw:**
- Maximum read performance critical
- High-throughput read operations (100k+ reads/sec)
- Performance-sensitive hot paths
- Every millisecond matters

**Hybrid approach:**
You can mix both in the same application:
```python
# Use ODM for most operations (type safety)
user = User.get(email="alice@example.com")

# Use raw for performance-critical paths
results = db.search('status', 'active')  # 10x faster than User.filter()
```

## Quick Start

```bash
# Quick comparison (fast, ~30 seconds)
python benchmarks/benchmark_scale.py --sizes "1000,10000"
python benchmarks/benchmark_odm.py --size 1000

# Comprehensive test (medium, ~2-3 minutes)
python benchmarks/benchmark_scale.py
python benchmarks/benchmark_complexity.py
python benchmarks/benchmark_odm.py

# Full suite (slow, ~15-20 minutes)
python benchmarks/benchmark_scale.py --max-size
python benchmarks/benchmark_complexity.py --size 50000
python benchmarks/benchmark_odm.py --size 50000
```

## Understanding Results

### Scale Benchmark Output

```
Dataset Size: 10,000 documents
────────────────────────────────────────────────
Database                  Insert          Search (idx)    Search (no idx)
KenobiX (no indexes)      0.85s | 11765/s 2.50ms         2.45ms
KenobiX (4 indexes)       0.92s | 10870/s 0.01ms         2.48ms

✓ Indexed search speedup: 250x faster
⚠ Insert overhead: 1.08x (indexed version creates indexes)
```

**Key metrics:**
- **Insert time**: How long to insert all documents
- **Insert rate**: Documents per second
- **Search (idx)**: Time for exact match on indexed field
- **Search (no idx)**: Time for exact match on non-indexed field
- **Pagination**: Time to retrieve 10 pages of 100 documents

### Complexity Benchmark Output

```
Document Complexity: COMPLEX (Document size: ~300 bytes)
────────────────────────────────────────────────
Database                      Insert              Search (idx)    Search (no idx)
KenobiX (no indexes)          2.15s | 4651/s     3.20ms | 3.18ms 3.15ms
KenobiX (5 indexes)           2.28s | 4386/s     0.02ms | 0.01ms 3.12ms

✓ Indexed search speedup: 160x faster
✓ Unindexed search speedup: 1.0x (no change expected)
⚠ Storage overhead: +2.3% (indexes use VIRTUAL columns)
```

**Insights:**
- Complex documents show greater benefits from indexing
- JSON parsing overhead is significant
- VIRTUAL generated columns add minimal storage

### ODM Benchmark Output

```
================================================================================
SUMMARY: ODM vs Raw Performance
================================================================================

Dataset: 5,000 documents
Indexed fields: name, email, age

Operation                      Raw             ODM             Overhead
---------------------------------------------------------------------------
Bulk Insert                    34.81ms         40.12ms         +15.2%
Search (indexed)               144.7µs         1.30ms          +796.9%
Retrieve All (100 docs)        171.9µs         234.1µs         +36.2%
Count                          287.1µs         6.52ms          +2170.9%
Delete Many                    30.40ms         28.28ms         -7.0%
Single Insert (avg)            144.0µs         140.9µs         -2.2%
```

**Insights:**
- ODM overhead varies significantly by operation
- Write operations: 15-35% overhead (acceptable)
- Read operations: 100-2000% overhead (deserialization cost)
- Trade-off: Type safety + productivity vs read performance
- Both use identical indexes (no query difference)

## Performance Guidelines

Based on benchmark results:

### When to use KenobiX without indexes:
- ✓ < 1,000 documents
- ✓ Rare queries
- ✓ Simple document structures
- ✓ No performance requirements

### When to use KenobiX with indexes:
- ✓ > 1,000 documents
- ✓ Frequent queries
- ✓ Known query patterns (can index those fields)
- ✓ Need < 1ms query times
- ✓ Complex document structures

### Index Selection Strategy:

```python
# Index frequently queried fields
db = KenobiX('app.db', indexed_fields=['user_id', 'email', 'status'])

# For complex queries
db = KenobiX('app.db', indexed_fields=[
    'user_id',      # Primary lookups
    'email',        # Auth lookups
    'status',       # Filtering
    'created_at',   # Time-based queries
    'category'      # Grouping/filtering
])
```

**Rules of thumb:**
- Index 3-6 most frequently queried fields
- Each index adds ~5-10% insert overhead
- Indexes add minimal storage (VIRTUAL columns)
- Rarely queried fields: don't index (will fall back to json_extract)

## Expected Performance Results

Based on comprehensive benchmarking (10,000 document dataset):

```bash
# 10k documents test
python benchmarks/benchmark_scale.py --sizes "10000" --pattern medium

# Expected results:
# - KenobiX (no indexes) search: ~2.5ms (full scan)
# - KenobiX (with indexes) search: ~0.01ms
# - Speedup: ~250x for exact match, up to 665x for updates
```

## Exporting Results

```bash
# CSV for spreadsheet analysis
python benchmarks/benchmark_scale.py --output csv > results_scale.csv
python benchmarks/benchmark_complexity.py --output csv > results_complexity.csv

# JSON for programmatic analysis
python benchmarks/benchmark_scale.py --output json > results.json
```

## Notes

- Benchmarks use temporary databases (deleted after test)
- Each test runs multiple iterations for accuracy
- Results may vary based on system performance
- SQLite version affects JSON function performance (use 3.31.0+)
- First run may be slower due to Python imports

## System Requirements

- Python 3.9+
- SQLite 3.31.0+ (for generated columns)
- ~500MB free disk space (for 1M document test)
- ~2GB RAM (for 1M document test)

## Troubleshooting

**"module 'kenobi' has no attribute 'KenobiX'"**
- Make sure you're running from the project root
- Ensure kenobix is installed: `pip install -e .`

**Benchmarks very slow**
- Start with smaller sizes: `--sizes "1000,10000"`
- Skip 1M test (don't use `--max-size`)
- Use simpler patterns: `--pattern simple`

**Out of memory**
- Reduce document count: `--size 5000`
- Use simpler document pattern
- Close other applications
