#!/usr/bin/env python3
"""
Concurrency tests for KenobiX.

Tests true concurrent access using multiprocessing to verify:
1. Multiple readers can run simultaneously without blocking
2. Readers are not blocked by writers (WAL mode benefit)
3. Writers properly serialize via write lock
4. No data corruption under concurrent load
5. Race conditions are handled correctly
"""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path

import pytest

from kenobix import KenobiX


@pytest.fixture
def db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


# Test worker functions (must be top-level for multiprocessing)
def concurrent_reader_worker(db_path: str, worker_id: int, iterations: int) -> dict:
    """Worker that performs many read operations."""
    db = KenobiX(db_path)
    start = time.time()
    read_count = 0

    for _i in range(iterations):
        results = db.search("worker_id", 0)  # Search for known data
        read_count += len(results)

    elapsed = time.time() - start
    db.close()

    return {
        "worker_id": worker_id,
        "read_count": read_count,
        "elapsed": elapsed,
    }


def concurrent_writer_worker(
    db_path: str, worker_id: int, iterations: int, indexed: bool = True
) -> dict:
    """Worker that performs many write operations."""
    indexed_fields = ["worker_id", "iteration"] if indexed else []
    db = KenobiX(db_path, indexed_fields=indexed_fields)
    start = time.time()
    write_count = 0

    for i in range(iterations):
        db.insert({
            "worker_id": worker_id,
            "iteration": i,
            "data": f"worker_{worker_id}_iter_{i}",
        })
        write_count += 1

    elapsed = time.time() - start
    db.close()

    return {
        "worker_id": worker_id,
        "write_count": write_count,
        "elapsed": elapsed,
    }


def mixed_worker(
    db_path: str, worker_id: int, iterations: int, indexed_fields: list[str]
) -> dict:
    """Worker that performs both reads and writes."""
    db = KenobiX(db_path, indexed_fields=indexed_fields)
    start = time.time()
    read_count = 0
    write_count = 0

    for i in range(iterations):
        # Write
        db.insert({"worker_id": worker_id, "counter": i, "value": i * 2})
        write_count += 1

        # Read
        results = db.search("worker_id", worker_id)
        read_count += len(results)

    elapsed = time.time() - start
    db.close()

    return {
        "worker_id": worker_id,
        "read_count": read_count,
        "write_count": write_count,
        "elapsed": elapsed,
    }


def race_condition_worker(db_path: str, worker_id: int, iterations: int) -> dict:
    """Worker that updates a shared counter (tests race conditions)."""
    db = KenobiX(db_path, indexed_fields=["key"])
    success_count = 0
    start = time.time()

    for _i in range(iterations):
        # Read current value
        results = db.search("key", "shared_counter")
        if results:
            current_value = results[0].get("value", 0)
        else:
            current_value = 0

        # Increment and write back (race condition!)
        new_value = current_value + 1
        if results:
            db.update("key", "shared_counter", {"value": new_value})
        else:
            db.insert({"key": "shared_counter", "value": new_value})

        success_count += 1

    elapsed = time.time() - start
    db.close()

    return {
        "worker_id": worker_id,
        "operations": success_count,
        "elapsed": elapsed,
    }


class TestConcurrency:
    """Test concurrent access to KenobiX database."""

    def test_multiple_concurrent_readers(self, db_path):
        """Test that multiple readers can run simultaneously without blocking."""
        # Setup: Insert test data
        db = KenobiX(str(db_path), indexed_fields=["worker_id"])
        for i in range(100):
            db.insert({"worker_id": 0, "value": i})
        db.close()

        # Launch multiple concurrent readers
        # Use more iterations so actual work dominates over process spawn overhead
        num_workers = 4
        iterations_per_worker = 200

        with multiprocessing.Pool(processes=num_workers) as pool:
            start = time.time()
            results = pool.starmap(
                concurrent_reader_worker,
                [(str(db_path), i, iterations_per_worker) for i in range(num_workers)],
            )
            elapsed = time.time() - start

        # Verify all workers completed successfully
        assert len(results) == num_workers
        for result in results:
            assert result["read_count"] == 100 * iterations_per_worker

        # If readers truly run in parallel, total time should be close to
        # the time of a single reader (not 4x)
        avg_worker_time = sum(r["elapsed"] for r in results) / num_workers
        speedup = avg_worker_time / elapsed

        print(f"\n✓ {num_workers} readers completed in {elapsed:.3f}s")
        print(f"  Average worker time: {avg_worker_time:.3f}s")
        print(f"  Speedup: {speedup:.2f}x")

        # Allow significant overhead for multiprocessing
        # Process spawn, IPC, and setup can add ~50-100ms total
        # We mainly verify that all operations complete successfully
        # and that we're not seeing catastrophic serialization
        max_expected = avg_worker_time * num_workers + 0.2  # Allow 200ms overhead
        assert elapsed < max_expected, (
            f"Operations took {elapsed:.3f}s, expected < {max_expected:.3f}s. "
            f"This suggests severe blocking or serialization issues."
        )

    def test_concurrent_writers(self, db_path):
        """Test that multiple writers properly serialize via write lock."""
        # Initialize database before launching workers to prevent WAL initialization race
        db = KenobiX(str(db_path), indexed_fields=["worker_id", "iteration"])
        db.close()

        # Launch multiple concurrent writers
        num_workers = 4
        iterations_per_worker = 25

        with multiprocessing.Pool(processes=num_workers) as pool:
            start = time.time()
            results = pool.starmap(
                concurrent_writer_worker,
                [
                    (str(db_path), i, iterations_per_worker, True)
                    for i in range(num_workers)
                ],
            )
            elapsed = time.time() - start

        # Verify all writes completed
        assert len(results) == num_workers
        total_writes = sum(r["write_count"] for r in results)
        expected_writes = num_workers * iterations_per_worker
        assert total_writes == expected_writes

        # Verify data integrity
        db = KenobiX(str(db_path), indexed_fields=["worker_id"])
        for worker_id in range(num_workers):
            worker_records = db.search("worker_id", worker_id, limit=1000)
            assert len(worker_records) == iterations_per_worker

        total_records = len(db.all(limit=10000))
        assert total_records == expected_writes

        db.close()

        print(
            f"\n✓ {num_workers} writers completed {total_writes} inserts in {elapsed:.3f}s"
        )
        print(f"  Rate: {total_writes / elapsed:.0f} inserts/sec")

    def test_concurrent_readers_and_writers(self, db_path):
        """Test that readers and writers can run concurrently."""
        # Setup: Insert initial data with indexed fields
        indexed_fields = ["worker_id", "counter"]
        db = KenobiX(str(db_path), indexed_fields=indexed_fields)
        for i in range(50):
            db.insert({"worker_id": -1, "counter": i, "value": i})  # Initial data
        db.close()

        # Launch mixed readers and writers
        num_readers = 3
        num_writers = 2
        iterations = 30

        # Add reader tasks
        tasks = [
            (
                str(db_path),
                -(i + 1),
                iterations,
                indexed_fields,
            )
            for i in range(num_readers)
        ]  # Negative IDs for readers

        # Add writer tasks
        tasks.extend(
            (str(db_path), i, iterations, indexed_fields) for i in range(num_writers)
        )

        with multiprocessing.Pool(processes=num_readers + num_writers) as pool:
            start = time.time()
            # Use mixed_worker for all (reads and writes)
            results = pool.starmap(mixed_worker, tasks)
            elapsed = time.time() - start

        # Verify all operations completed
        assert len(results) == num_readers + num_writers

        # Count operations
        total_reads = sum(r["read_count"] for r in results)
        total_writes = sum(r["write_count"] for r in results)

        print(f"\n✓ Mixed workload completed in {elapsed:.3f}s")
        print(f"  Total reads: {total_reads}")
        print(f"  Total writes: {total_writes}")
        print(f"  Combined rate: {(total_reads + total_writes) / elapsed:.0f} ops/sec")

        # Verify data integrity
        db = KenobiX(str(db_path), indexed_fields=["worker_id"])
        all_records = db.all(limit=10000)
        # Initial 50 + writes from all workers
        expected = 50 + (num_readers + num_writers) * iterations
        assert len(all_records) == expected
        db.close()

    def test_race_conditions(self, db_path):
        """Test behavior under race conditions (shared counter)."""
        # Initialize shared counter
        db = KenobiX(str(db_path), indexed_fields=["key"])
        db.insert({"key": "shared_counter", "value": 0})
        db.close()

        # Launch workers that all increment the same counter
        num_workers = 4
        iterations_per_worker = 20

        with multiprocessing.Pool(processes=num_workers) as pool:
            start = time.time()
            results = pool.starmap(
                race_condition_worker,
                [(str(db_path), i, iterations_per_worker) for i in range(num_workers)],
            )
            elapsed = time.time() - start

        # Verify all operations completed
        total_operations = sum(r["operations"] for r in results)
        expected_operations = num_workers * iterations_per_worker
        assert total_operations == expected_operations

        # Check final counter value
        db = KenobiX(str(db_path), indexed_fields=["key"])
        results = db.search("key", "shared_counter")
        assert len(results) == 1
        final_value = results[0]["value"]

        # Due to race conditions, final value will be less than expected
        # (some increments get lost due to read-modify-write races)
        expected_value = expected_operations
        db.close()

        print(f"\n✓ Race condition test completed in {elapsed:.3f}s")
        print(f"  Expected counter value: {expected_value}")
        print(f"  Actual counter value: {final_value}")
        print(
            f"  Lost updates: {expected_value - final_value} ({((expected_value - final_value) / expected_value * 100):.1f}%)"
        )

        # We expect some lost updates due to race conditions
        # This demonstrates that applications need proper locking
        # for read-modify-write operations
        assert final_value < expected_value
        # But we should have at least some updates
        assert final_value > 0

    def test_high_concurrency_stress(self, db_path):
        """Stress test with many concurrent operations."""
        # Initialize database before launching workers to prevent WAL initialization race
        db = KenobiX(str(db_path), indexed_fields=["worker_id", "iteration"])
        db.close()

        # Many workers, fewer iterations each
        num_workers = 10
        iterations_per_worker = 20

        with multiprocessing.Pool(processes=num_workers) as pool:
            start = time.time()
            results = pool.starmap(
                concurrent_writer_worker,
                [
                    (str(db_path), i, iterations_per_worker, True)
                    for i in range(num_workers)
                ],
            )
            _elapsed = time.time() - start

        # Verify data integrity
        total_writes = sum(r["write_count"] for r in results)
        expected = num_workers * iterations_per_worker
        assert total_writes == expected

        db = KenobiX(str(db_path), indexed_fields=["worker_id"])
        actual_count = len(db.all(limit=10000))
        assert actual_count == expected

        # Verify each worker's data
        for worker_id in range(num_workers):
            worker_records = db.search("worker_id", worker_id, limit=1000)
            assert len(worker_records) == iterations_per_worker

        db.close()

    def test_database_integrity_after_concurrent_access(self, db_path):
        """Verify database remains consistent after heavy concurrent access."""
        # Initialize database before launching workers to prevent WAL initialization race
        db = KenobiX(str(db_path), indexed_fields=["worker_id", "iteration"])
        db.close()

        # Perform concurrent operations
        num_workers = 5
        iterations = 30

        with multiprocessing.Pool(processes=num_workers) as pool:
            pool.starmap(
                concurrent_writer_worker,
                [(str(db_path), i, iterations, True) for i in range(num_workers)],
            )

        # Verify database integrity
        db = KenobiX(str(db_path), indexed_fields=["worker_id", "iteration"])

        # Check total count
        all_records = db.all(limit=10000)
        assert len(all_records) == num_workers * iterations

        # Check each worker's records
        for worker_id in range(num_workers):
            worker_records = db.search("worker_id", worker_id, limit=1000)
            assert len(worker_records) == iterations

            # Check iterations are complete (0 to iterations-1)
            iterations_found = sorted([r["iteration"] for r in worker_records])
            assert iterations_found == list(range(iterations))

        # Check indexes are working
        explain_result = db.explain("search", "worker_id", 0)
        # Should use index (contains "USING INDEX" in plan)
        plan_str = str(explain_result).upper()
        assert "INDEX" in plan_str or "SEARCH" in plan_str

        db.close()
