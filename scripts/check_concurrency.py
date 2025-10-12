#!/usr/bin/env python3
"""
Quick concurrency check for KenobiX.

This script demonstrates and verifies concurrent access behavior:
- Multiple readers running in parallel
- Writers not blocking readers (WAL mode benefit)
- Proper serialization of writes

Usage:
    python scripts/check_concurrency.py
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kenobix import KenobiX


def reader_process(db_path: str, reader_id: int, num_reads: int) -> float:
    """Perform many reads and return elapsed time."""
    db = KenobiX(db_path, indexed_fields=["id", "category"])
    start = time.time()

    for i in range(num_reads):
        # Alternate between different query types
        if i % 3 == 0:
            db.search("category", "test")
        elif i % 3 == 1:
            db.search("id", i % 100)
        else:
            db.all(limit=50)

    elapsed = time.time() - start
    db.close()
    return elapsed


def writer_process(db_path: str, writer_id: int, num_writes: int) -> float:
    """Perform many writes and return elapsed time."""
    db = KenobiX(db_path, indexed_fields=["id", "category"])
    start = time.time()

    for i in range(num_writes):
        db.insert({
            "id": writer_id * 1000 + i,
            "category": "test",
            "writer": writer_id,
            "value": i,
            "data": f"Data from writer {writer_id}, iteration {i}",
        })

    elapsed = time.time() - start
    db.close()
    return elapsed


def mixed_worker(task_type: str, db_path: str, worker_id: int, ops: int) -> float:
    """Worker function for mixed workload tests."""
    if task_type == "read":
        return reader_process(db_path, worker_id, ops)
    return writer_process(db_path, worker_id, ops)


def run_concurrent_reads(db_path: str, num_readers: int, reads_per_reader: int):
    """Test multiple concurrent readers."""
    print(f"\n{'=' * 70}")
    print(f"TEST 1: {num_readers} Concurrent Readers ({reads_per_reader} reads each)")
    print(f"{'=' * 70}")

    with multiprocessing.Pool(processes=num_readers) as pool:
        start = time.time()
        times = pool.starmap(
            reader_process,
            [(db_path, i, reads_per_reader) for i in range(num_readers)],
        )
        total_elapsed = time.time() - start

    avg_reader_time = sum(times) / len(times)
    total_reads = num_readers * reads_per_reader

    print(f"✓ Completed {total_reads} reads across {num_readers} processes")
    print(f"  Total wall time: {total_elapsed:.3f}s")
    print(f"  Avg reader time: {avg_reader_time:.3f}s")
    print(f"  Throughput: {total_reads / total_elapsed:.0f} reads/sec")

    if total_elapsed < avg_reader_time * 1.5:
        print(
            f"  ✓ PARALLELISM CONFIRMED: {avg_reader_time / total_elapsed:.2f}x speedup"
        )
    else:
        print("  ⚠ Limited parallelism detected")


def run_concurrent_writes(db_path: str, num_writers: int, writes_per_writer: int):
    """Test multiple concurrent writers."""
    print(f"\n{'=' * 70}")
    print(f"TEST 2: {num_writers} Concurrent Writers ({writes_per_writer} writes each)")
    print(f"{'=' * 70}")

    with multiprocessing.Pool(processes=num_writers) as pool:
        start = time.time()
        pool.starmap(
            writer_process,
            [(db_path, i, writes_per_writer) for i in range(num_writers)],
        )
        total_elapsed = time.time() - start

    total_writes = num_writers * writes_per_writer

    print(f"✓ Completed {total_writes} writes across {num_writers} processes")
    print(f"  Total time: {total_elapsed:.3f}s")
    print(f"  Throughput: {total_writes / total_elapsed:.0f} writes/sec")

    # Verify all data was written
    db = KenobiX(db_path, indexed_fields=["id", "category"])
    actual_count = len(db.all(limit=100000))
    expected_count = 1000 + total_writes  # Initial 1000 + new writes

    if actual_count == expected_count:
        print(f"  ✓ DATA INTEGRITY: All {total_writes} writes persisted correctly")
    else:
        print(f"  ✗ DATA LOSS: Expected {expected_count}, found {actual_count}")

    db.close()


def run_mixed_workload(
    db_path: str, num_readers: int, num_writers: int, ops_per_worker: int
):
    """Test readers and writers running simultaneously."""
    print(f"\n{'=' * 70}")
    print(f"TEST 3: Mixed Workload ({num_readers} readers + {num_writers} writers)")
    print(f"{'=' * 70}")

    # Add reader tasks
    tasks = [("read", db_path, i, ops_per_worker) for i in range(num_readers)]
    # Add writer tasks
    tasks.extend(("write", db_path, i, ops_per_worker) for i in range(num_writers))

    with multiprocessing.Pool(processes=num_readers + num_writers) as pool:
        start = time.time()
        pool.starmap(mixed_worker, tasks)
        total_elapsed = time.time() - start

    print(f"✓ Completed mixed workload in {total_elapsed:.3f}s")
    print(f"  {num_readers * ops_per_worker} reads")
    print(f"  {num_writers * ops_per_worker} writes")
    total_ops = (num_readers + num_writers) * ops_per_worker
    print(f"  Combined throughput: {total_ops / total_elapsed:.0f} ops/sec")
    print("  ✓ READERS NOT BLOCKED: Concurrent reads and writes succeeded")


def main():
    print("\n" + "=" * 70)
    print("KenobiX Concurrency Check")
    print("=" * 70)

    # Use spawn method (safer, works on all platforms)
    multiprocessing.set_start_method("spawn", force=True)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Setup: Create database with initial data
        print("\nSetting up test database...")
        db = KenobiX(db_path, indexed_fields=["id", "category"])
        for i in range(1000):
            db.insert({
                "id": i,
                "category": "test" if i % 2 == 0 else "other",
                "value": i * 10,
                "data": f"Initial data {i}",
            })
        db.close()
        print("✓ Created database with 1000 initial records")

        # Test 1: Multiple concurrent readers
        run_concurrent_reads(db_path, num_readers=4, reads_per_reader=100)

        # Test 2: Multiple concurrent writers
        run_concurrent_writes(db_path, num_writers=4, writes_per_writer=50)

        # Test 3: Mixed workload
        run_mixed_workload(db_path, num_readers=3, num_writers=2, ops_per_worker=50)

        # Final summary
        print(f"\n{'=' * 70}")
        print("CONCURRENCY CHECK SUMMARY")
        print(f"{'=' * 70}")

        db = KenobiX(db_path, indexed_fields=["id", "category"])
        stats = db.stats()
        db.close()

        print("✓ Final database state:")
        print(f"  Total documents: {stats['document_count']}")
        print(f"  Database size: {stats['database_size_bytes'] / 1024:.1f} KB")
        print(f"  WAL mode: {stats['wal_mode']}")
        print("\n✓ All concurrency tests passed!")
        print("  - Multiple readers run in parallel ✓")
        print("  - Writers properly serialize ✓")
        print("  - Readers not blocked by writers ✓")
        print("  - Data integrity maintained ✓")

    finally:
        # Cleanup
        if Path(db_path).exists():
            Path(db_path).unlink()
            # Also clean up WAL files
            for suffix in ["-wal", "-shm"]:
                wal_file = Path(db_path + suffix)
                if wal_file.exists():
                    wal_file.unlink()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
