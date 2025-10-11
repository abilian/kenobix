# KenobiX Performance Guide

This guide covers performance optimization, benchmarks, and best practices for KenobiX.

## Quick Performance Facts

- **15-53x faster searches** on indexed fields
- **80-665x faster updates** compared to basic implementations
- **Sub-millisecond** query times on 10,000+ documents
- **Minimal overhead**: 7-20% storage, 5-10% insert time

## Benchmark Results

### Real-World Performance (10,000 Documents)

| Operation | Without Indexes | With Indexes | Speedup |
|-----------|----------------|--------------|---------|
| Exact search | 6.52ms | 0.009ms | **724x** |
| Update 100 docs | 1.29s | 15.55ms | **83x** |
| Range-like queries | 2.96ms | 0.52ms | **5.7x** |
| Pagination | 1.45ms | 1.42ms | **1.02x** |

### Scaling Performance

| Documents | Search (indexed) | Search (unindexed) | Insert Many |
|-----------|-----------------|-------------------|-------------|
| 1,000 | 0.01ms | 0.25ms | 45ms |
| 10,000 | 0.01ms | 2.50ms | 450ms |
| 100,000 | 0.01ms | 25.0ms | 4.5s |
| 1,000,000 | 0.02ms | 250ms | 45s |

**Key Insight:** Indexed searches stay constant (O(log n)), unindexed searches scale linearly (O(n)).

### Document Complexity Impact

| Document Type | Size | Indexed Search | Unindexed Search | Update 100 |
|---------------|------|----------------|------------------|------------|
| Simple (3 fields) | ~50 bytes | 0.009ms | 1.2ms | 8ms |
| Medium (6 fields) | ~100 bytes | 0.009ms | 2.5ms | 15ms |
| Complex (10+ fields) | ~300 bytes | 0.010ms | 4.1ms | 35ms |
| Very Complex | ~1KB | 0.012ms | 8.5ms | 85ms |

**Key Insight:** More complex documents benefit MORE from indexing.

## Index Strategy

### Rule of Thumb

Index your **3-6 most frequently queried fields**.

```python
# Good indexing strategy
db = KenobiX('app.db', indexed_fields=[
    'user_id',      # Primary lookups
    'email',        # Authentication
    'status',       # Filtering
    'created_at',   # Time-based queries
])
```

### Index Cost vs Benefit

**Benefits:**
- 15-665x faster queries
- 80-665x faster updates
- Sub-millisecond response times

**Costs:**
- ~5-10% slower inserts per index
- ~7-20% storage overhead (VIRTUAL columns are efficient!)
- Slightly more memory usage

**Example with 3 indexes:**
- Insert overhead: ~15-30% slower
- Query speedup: 15-665x faster
- **Net benefit: Massive win for read-heavy workloads**

### When to Index

✅ **Index fields that are:**
- Frequently searched (`search()`, `search_optimized()`)
- Used in updates (`update()` key parameter)
- Used for filtering (ODM `filter()`)
- High cardinality (many unique values like IDs, emails)

❌ **Don't index fields that are:**
- Rarely queried
- Low cardinality (e.g., boolean flags with only 2 values)
- Only used in full-text search
- Changed very frequently

### Dynamic Indexing

```python
# Start without indexes
db = KenobiX('app.db', indexed_fields=[])

# Add index later (requires table recreation)
db.create_index('email')

# Check which fields are indexed
indexed = db.get_indexed_fields()
print(indexed)  # {'email'}
```

**Note:** Dynamic indexing is slower than specifying at initialization. Better to plan ahead.

## Query Optimization

### Use Indexed Fields

```python
# Fast: Uses index
db.search('email', 'alice@example.com')  # ~0.01ms

# Slow: No index, full scan
db.search('bio', 'developer')  # ~2.5ms on 10k docs
```

### Multi-Field Queries

```python
# Use search_optimized() for multiple fields
results = db.search_optimized(
    status='active',
    role='admin',
    verified=True
)
# If all fields indexed: 70x faster than separate searches
```

### Verify Index Usage

```python
# Check if query uses index
plan = db.explain('search', 'email', 'test@example.com')
print(plan)

# Look for:
# "SEARCH ... USING INDEX idx_email" ✅ Good!
# "SCAN documents" ❌ Bad - no index used
```

## Pagination Strategies

### Offset Pagination (Simple but Slow for Deep Pages)

```python
# Works but gets slower as offset increases (O(n))
page1 = db.all(limit=100, offset=0)      # Fast
page2 = db.all(limit=100, offset=100)    # Fast
page10 = db.all(limit=100, offset=1000)  # Slower
```

### Cursor Pagination (Fast for All Pages)

```python
# Much better for large datasets (O(1))
result = db.all_cursor(limit=100)
documents = result['documents']

# Next page
if result['has_more']:
    next_page = db.all_cursor(
        after_id=result['next_cursor'],
        limit=100
    )
```

**Performance Comparison:**
- Page 1: Both methods ~1.5ms
- Page 100: Offset ~150ms, Cursor ~1.5ms
- **Cursor is 100x faster for deep pagination**

## Bulk Operations

### Batch Inserts

```python
# Slow: Individual inserts
for doc in documents:
    db.insert(doc)  # 1000 inserts: ~500ms

# Fast: Bulk insert
db.insert_many(documents)  # 1000 inserts: ~50ms
# 10x faster!
```

### Batch Updates

```python
# If updating many documents with same criteria
db.update('status', 'pending', {'status': 'processing'})
# Updates all matching documents in one operation
```

## Concurrency

### Read Concurrency

```python
# Multiple threads can read simultaneously (lock-free)
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [
        executor.submit(db.search, 'status', 'active')
        for _ in range(10)
    ]
    results = [f.result() for f in futures]
# All queries execute concurrently
```

### Write Serialization

```python
# Writes are serialized (protected by RLock)
# This is necessary for data integrity

# But you can still do concurrent reads while writing
write_thread = Thread(target=db.insert, args=(doc,))
read_threads = [
    Thread(target=db.search, args=('status', 'active'))
    for _ in range(5)
]

write_thread.start()
for t in read_threads:
    t.start()  # Reads proceed concurrently with write
```

## Memory Optimization

### Storage Overhead

VIRTUAL generated columns use minimal space:

```
Simple docs (50 bytes):
- Without indexes: 50KB for 1000 docs
- With 3 indexes: 54KB (+8% overhead)

Complex docs (1KB):
- Without indexes: 1MB for 1000 docs
- With 3 indexes: 1.2MB (+20% overhead)
```

### Query Results

```python
# Large result sets can use memory
results = db.all()  # May load thousands of documents

# Better: Use pagination
for offset in range(0, total_docs, 1000):
    batch = db.all(limit=1000, offset=offset)
    process(batch)
    # Process in chunks, lower memory usage
```

## Async Operations

```python
# Execute queries asynchronously
future = db.execute_async(db.search, 'email', 'test@example.com')

# Do other work...

# Get result when needed
results = future.result(timeout=5)
```

**Note:** The `ThreadPoolExecutor` has max 5 workers. Don't forget to call `db.close()` to shut it down properly.

## Running Benchmarks

### Scale Benchmarks

```bash
# Quick test (1k, 10k documents)
python benchmarks/benchmark_scale.py --sizes "1000,10000"

# Full test (up to 100k)
python benchmarks/benchmark_scale.py

# Include 1M document test (slow!)
python benchmarks/benchmark_scale.py --max-size
```

### Complexity Benchmarks

```bash
# Test how document complexity affects performance
python benchmarks/benchmark_complexity.py

# Custom document count
python benchmarks/benchmark_complexity.py --size 50000
```

### ODM vs Raw Benchmarks

```bash
# Compare ODM vs raw operations
python benchmarks/benchmark_odm.py

# Custom document count
python benchmarks/benchmark_odm.py --size 10000

# CSV output
python benchmarks/benchmark_odm.py --output csv
```

**Benchmark Methodology:**
- Each test runs **5 times** with **trimmed mean** (discard min/max, average remaining 3)
- Warmup runs ensure SQLite caches are populated equally
- Fresh databases for bulk insert tests to eliminate cache effects
- Minimizes variance from GC, disk I/O, scheduler jitter

**Sample Results (10,000 documents):**

| Operation | Raw | ODM | Overhead |
|-----------|-----|-----|----------|
| Bulk Insert | 45ms | 52ms | +15% |
| Search (indexed) | 15µs | 150µs | +900% |
| Retrieve All (100) | 200µs | 450µs | +125% |
| Count | 300µs | 350µs | +17% |
| Delete Many | 30ms | 34ms | +13% |
| Single Insert | 150µs | 160µs | +7% |

**Key Insights:**
- **Write operations**: 7-15% overhead (very acceptable)
- **Read operations**: 100-900% overhead (cattrs deserialization cost)
- **Search has highest overhead**: Deserializing complex objects is expensive
- **Count operation**: Now shows realistic ~17% overhead (previous versions had bugs)
- **Both use identical indexes**: Query performance difference is purely deserialization

### Output Formats

```bash
# CSV output
python benchmarks/benchmark_scale.py --output csv > results.csv

# JSON output
python benchmarks/benchmark_scale.py --output json > results.json
```

## Performance Anti-Patterns

### ❌ Don't Do This

```python
# 1. Searching unindexed fields in a loop
for user_id in user_ids:
    results = db.search('bio', user_id)  # Slow!

# 2. Individual inserts
for doc in documents:
    db.insert(doc)  # 10x slower than insert_many

# 3. Deep offset pagination
page_100 = db.all(limit=100, offset=10000)  # Very slow!

# 4. Indexing everything
db = KenobiX('app.db', indexed_fields=[
    'field1', 'field2', 'field3', 'field4',
    'field5', 'field6', 'field7', 'field8',
])  # Too many indexes, insert performance suffers

# 5. Not using search_optimized for multi-field queries
results1 = db.search('status', 'active')
results2 = [r for r in results1 if r['role'] == 'admin']
```

### ✅ Do This Instead

```python
# 1. Index frequently queried fields
db = KenobiX('app.db', indexed_fields=['user_id'])
for user_id in user_ids:
    results = db.search('user_id', user_id)  # Fast!

# 2. Bulk inserts
db.insert_many(documents)

# 3. Cursor pagination
result = db.all_cursor(limit=100)
while result['has_more']:
    result = db.all_cursor(after_id=result['next_cursor'], limit=100)

# 4. Index 3-6 most important fields
db = KenobiX('app.db', indexed_fields=['user_id', 'email', 'status'])

# 5. Use search_optimized
results = db.search_optimized(status='active', role='admin')
```

## Performance Monitoring

### Database Statistics

```python
stats = db.stats()
print(f"Documents: {stats['document_count']}")
print(f"Size: {stats['database_size_bytes']} bytes")
print(f"Indexed fields: {stats['indexed_fields']}")
print(f"WAL mode: {stats['wal_mode']}")
```

### Query Plans

```python
# Check if index is being used
plan = db.explain('search', 'email', 'test@example.com')
for row in plan:
    print(row)

# Expected output (good):
# SEARCH documents USING INDEX idx_email (email=?)

# Bad output (needs index):
# SCAN documents
```

## When KenobiX Is Fast

✅ **Optimal Use Cases:**
- 1,000 - 1,000,000 documents
- Frequent searches on indexed fields
- Many updates on indexed fields
- Known query patterns
- Read-heavy workloads
- Complex documents

## When to Use Alternatives

⚠️ **Consider Alternatives When:**
- < 100 documents (indexing overhead not worth it)
- Pure insert-only workloads (no queries)
- > 10M documents (use PostgreSQL, MongoDB)
- Extremely high write throughput requirements
- Need distributed/replicated database

## ODM Performance Trade-offs

The ODM layer provides type safety and developer convenience at the cost of performance:

### Performance Impact

**Write Operations (Low Overhead):**
- Bulk insert: +15% overhead
- Single insert: +7% overhead
- Delete many: +13% overhead
- **Verdict:** Write performance overhead is minimal and acceptable for virtually all applications

**Read Operations (Significant Overhead):**
- Search (indexed): +900% overhead (cattrs deserialization is expensive)
- Retrieve all: +125% overhead (deserializing multiple objects)
- Count: +17% overhead (minimal since no deserialization needed)
- **Verdict:** Reads are 2-10x slower due to cattrs deserialization

**Why is ODM Search So Much Slower?**
- Raw: Fetch JSON from SQLite → Parse JSON → Return dict (fast)
- ODM: Fetch JSON from SQLite → Parse JSON → cattrs.structure() → Validate types → Create dataclass instance (slow)
- The overhead is purely in object construction and type validation, not in the SQL query itself

### Benchmark Improvements

**Note:** Previous benchmarks had bugs that showed unrealistic results:
- Old count benchmark: +2100% overhead (bug: raw was using limited search instead of SQL COUNT)
- Fixed count benchmark: +17% overhead (both now use SQL COUNT)
- New methodology: 5 iterations with trimmed mean for statistical robustness

### Choosing Between ODM and Raw

**Use ODM when:**
- Type safety is important (IDE autocomplete, type checking)
- Developer productivity matters more than raw speed
- Write-heavy or balanced workloads
- Application can tolerate 2-10x slower reads
- Code maintainability is a priority
- You want dataclass benefits (equality, repr, etc.)

**Use Raw when:**
- Maximum read performance is critical
- High-throughput read operations (100k+ reads/sec)
- Performance-sensitive hot paths
- Every millisecond matters
- You're okay with dict typing: `dict[str, Any]`

**Hybrid Approach:**
You can mix both approaches in the same application:
```python
# Use ODM for most operations (type safety, maintainability)
user = User.get(email="alice@example.com")
user.age = 31
user.save()

# Use raw for performance-critical paths (hot loops, high-throughput)
results = db.search('status', 'active')  # 10x faster than User.filter()
for doc in results:
    process(doc)  # Work with dicts directly
```

**Real-world recommendation:** Start with ODM for developer productivity. Profile your application. Only optimize hot paths to raw operations if profiling shows ODM deserialization is a bottleneck.

## Comparison with Other Solutions

| Feature | KenobiX Raw | KenobiX ODM | MongoDB | PostgreSQL JSON |
|---------|-------------|-------------|---------|----------------|
| Setup | Zero config | Zero config | Server | Server |
| Dependencies | None | cattrs | Driver | Driver |
| Type safety | No | Yes | With ODM | With ORM |
| Index performance | Excellent | Excellent | Excellent | Excellent |
| Read overhead | Baseline | 2-3x | Baseline | Baseline |
| Storage | Single file | Single file | Multiple | Database |
| Scaling | < 10M docs | < 10M docs | Unlimited | Unlimited |
| Use case | Embedded | Type-safe embedded | Large scale | Large scale |

**KenobiX sweet spot:** Embedded applications, prototypes, small-to-medium scale applications (1k-1M documents) that need excellent performance without operational complexity.

## Tips and Tricks

1. **Start with indexes** - Easier than adding later
2. **Use explain()** - Verify queries use indexes
3. **Batch operations** - insert_many() is 10x faster
4. **Cursor pagination** - 100x faster for deep pages
5. **3-6 indexes optimal** - Balance performance vs overhead
6. **Test with realistic data** - Performance varies by document complexity
7. **Monitor stats()** - Keep track of database growth
8. **Close connections** - Call db.close() to shutdown ThreadPoolExecutor

## Conclusion

KenobiX delivers **15-665x performance improvements** over basic document stores through:
- Smart indexing with generated columns
- Lock-free concurrent reads
- Efficient VIRTUAL columns (minimal overhead)
- Automatic index usage
- Optimized pagination

For applications in the 1k-1M document range, KenobiX provides database-level performance with zero operational overhead.
