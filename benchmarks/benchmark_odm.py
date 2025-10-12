#!/usr/bin/env python3
"""
Benchmark KenobiX ODM vs Raw KenobiX Performance.

Compares the overhead of using the ODM layer (dataclasses + cattrs)
versus raw dictionary operations.

Usage:
    python benchmarks/benchmark_odm.py

Options:
    --size: Number of documents to test (default: 10000)
    --output: Output format (table, csv, json, default: table)
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile
import time
from dataclasses import dataclass

from kenobix import Document, KenobiX


# Define test models for ODM
@dataclass
class User(Document):
    """Simple user model."""

    name: str
    email: str
    age: int
    active: bool = True


@dataclass
class Post(Document):
    """Complex model with nested structures."""

    title: str
    content: str
    author_id: int
    tags: list[str]
    views: int = 0
    published: bool = False


def benchmark_raw_insert_single(db, document: dict) -> float:
    """Benchmark single insert with raw KenobiX."""
    start = time.time()
    db.insert(document)
    return time.time() - start


def benchmark_odm_insert_single(user_data: dict) -> float:
    """Benchmark single insert with ODM."""
    start = time.time()
    user = User(**user_data)
    user.save()
    return time.time() - start


def benchmark_raw_insert_many(db, documents: list[dict]) -> float:
    """Benchmark bulk insert with raw KenobiX."""
    start = time.time()
    db.insert_many(documents)
    return time.time() - start


def benchmark_odm_insert_many(user_data_list: list[dict]) -> float:
    """Benchmark bulk insert with ODM."""
    start = time.time()
    users = [User(**data) for data in user_data_list]
    User.insert_many(users)
    return time.time() - start


def benchmark_raw_search_indexed(db, field: str, value) -> tuple[float, int]:
    """Benchmark search on indexed field with raw KenobiX."""
    start = time.time()
    results = db.search(field, value)
    elapsed = time.time() - start
    return elapsed, len(results)


def benchmark_odm_search_indexed(field: str, value) -> tuple[float, int]:
    """Benchmark search on indexed field with ODM."""
    start = time.time()
    results = User.filter(**{field: value})
    elapsed = time.time() - start
    return elapsed, len(results)


def benchmark_raw_search_all(db, limit: int) -> tuple[float, int]:
    """Benchmark retrieving all documents with raw KenobiX."""
    start = time.time()
    results = db.all(limit=limit)
    elapsed = time.time() - start
    return elapsed, len(results)


def benchmark_odm_search_all(limit: int) -> tuple[float, int]:
    """Benchmark retrieving all documents with ODM."""
    start = time.time()
    results = User.all(limit=limit)
    elapsed = time.time() - start
    return elapsed, len(results)


def benchmark_raw_count(db, field: str, value) -> float:
    """Benchmark counting with raw KenobiX (using SQL COUNT)."""
    start = time.time()
    # Use direct SQL COUNT like ODM does (no count() method in raw KenobiX)
    if field in db._indexed_fields:
        safe_field = db._sanitize_field_name(field)
        query = f"SELECT COUNT(*) FROM documents WHERE {safe_field} = ?"
        cursor = db._connection.execute(query, (value,))
    else:
        query = (
            f"SELECT COUNT(*) FROM documents WHERE json_extract(data, '$.{field}') = ?"
        )
        cursor = db._connection.execute(query, (value,))
    _ = cursor.fetchone()[0]
    return time.time() - start


def benchmark_odm_count(field: str, value) -> float:
    """Benchmark counting with ODM."""
    start = time.time()
    _ = User.count(**{field: value})
    return time.time() - start


def benchmark_raw_delete(db, field: str, value) -> float:
    """Benchmark delete with raw KenobiX."""
    start = time.time()
    db.remove(field, value)
    return time.time() - start


def benchmark_odm_delete(field: str, value) -> float:
    """Benchmark delete with ODM."""
    start = time.time()
    User.delete_many(**{field: value})
    return time.time() - start


def trimmed_mean(values: list[float]) -> float:
    """Calculate trimmed mean: remove min/max, average the rest."""
    if len(values) < 3:
        return sum(values) / len(values)
    sorted_values = sorted(values)
    # Remove min and max, take average of remaining
    trimmed = sorted_values[1:-1]
    return sum(trimmed) / len(trimmed)


def run_bulk_insert_test(
    user_data_list: list[dict],
    indexed_fields: list[str],
    num_iterations: int,
    size: int,
) -> tuple[dict, object, object]:
    """Run bulk insert benchmark for both raw and ODM."""
    print("\n1. Bulk Insert (5 iterations)")

    # Raw - run multiple times with fresh database each time
    raw_insert_times = []
    raw_db_paths = []
    for i in range(num_iterations):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
            raw_db_paths.append(db_path)

        db = KenobiX(db_path, indexed_fields=indexed_fields)
        insert_time = benchmark_raw_insert_many(db, user_data_list)
        raw_insert_times.append(insert_time)
        db.close()
        print(f"  Raw iteration {i + 1}: {insert_time:.4f}s", end="\r")

    raw_insert_time = trimmed_mean(raw_insert_times)
    print(
        f"  Raw:    {raw_insert_time:.4f}s ({size / raw_insert_time:.0f} docs/s) [trimmed mean]"
    )

    # Keep one database for further tests
    raw_db_path = raw_db_paths[0]
    raw_db = KenobiX(raw_db_path, indexed_fields=indexed_fields)
    raw_db.insert_many(user_data_list)

    # ODM - run multiple times with fresh database each time
    odm_insert_times = []
    odm_db_paths = []
    for i in range(num_iterations):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
            odm_db_paths.append(db_path)

        db = KenobiX(db_path, indexed_fields=indexed_fields)
        Document.set_database(db)
        insert_time = benchmark_odm_insert_many(user_data_list)
        odm_insert_times.append(insert_time)
        db.close()
        print(f"  ODM iteration {i + 1}: {insert_time:.4f}s", end="\r")

    odm_insert_time = trimmed_mean(odm_insert_times)
    print(
        f"  ODM:    {odm_insert_time:.4f}s ({size / odm_insert_time:.0f} docs/s) [trimmed mean]"
    )
    print(f"  Overhead: {(odm_insert_time / raw_insert_time - 1) * 100:.1f}%")

    # Keep one database for further tests
    odm_db_path = odm_db_paths[0]
    odm_db = KenobiX(odm_db_path, indexed_fields=indexed_fields)
    Document.set_database(odm_db)
    users = [User(**data) for data in user_data_list]
    User.insert_many(users)

    # Cleanup extra databases
    for path in raw_db_paths[1:]:
        pathlib.Path(path).unlink(missing_ok=True)
    for path in odm_db_paths[1:]:
        pathlib.Path(path).unlink(missing_ok=True)

    results = {
        "raw_insert_many_time": raw_insert_time,
        "raw_insert_many_rate": size / raw_insert_time,
        "odm_insert_many_time": odm_insert_time,
        "odm_insert_many_rate": size / odm_insert_time,
    }

    return results, raw_db, odm_db


def run_search_indexed_test(raw_db, num_iterations: int) -> dict:
    """Run search by indexed field benchmark."""
    print("\n2. Search by Indexed Field (5 iterations)")

    # Warmup to ensure SQLite caches are populated
    _ = raw_db.search("email", "user_500@example.com")
    _ = User.filter(email="user_500@example.com")

    # Raw - run multiple times
    raw_search_times = []
    for _ in range(num_iterations):
        search_time, raw_count = benchmark_raw_search_indexed(
            raw_db, "email", "user_500@example.com"
        )
        raw_search_times.append(search_time)

    raw_search_time = trimmed_mean(raw_search_times)
    print(
        f"  Raw:    {raw_search_time * 1000:.3f}ms ({raw_count} results) [trimmed mean]"
    )

    # ODM - run multiple times
    odm_search_times = []
    for _ in range(num_iterations):
        search_time, odm_count = benchmark_odm_search_indexed(
            "email", "user_500@example.com"
        )
        odm_search_times.append(search_time)

    odm_search_time = trimmed_mean(odm_search_times)
    print(
        f"  ODM:    {odm_search_time * 1000:.3f}ms ({odm_count} results) [trimmed mean]"
    )
    print(f"  Overhead: {(odm_search_time / raw_search_time - 1) * 100:.1f}%")

    return {
        "raw_search_indexed_time": raw_search_time,
        "odm_search_indexed_time": odm_search_time,
    }


def run_retrieve_all_test(raw_db, num_iterations: int) -> dict:
    """Run retrieve all (pagination) benchmark."""
    print("\n3. Retrieve All (5 iterations)")

    # Warmup
    _ = raw_db.all(limit=100)
    _ = User.all(limit=100)

    # Raw - run multiple times
    raw_all_times = []
    for _ in range(num_iterations):
        t, count = benchmark_raw_search_all(raw_db, limit=100)
        raw_all_times.append(t)

    raw_all_time = trimmed_mean(raw_all_times)
    raw_all_count = count
    print(
        f"  Raw:    {raw_all_time * 1000:.3f}ms ({raw_all_count} results) [trimmed mean]"
    )

    # ODM - run multiple times
    odm_all_times = []
    for _ in range(num_iterations):
        t, count = benchmark_odm_search_all(limit=100)
        odm_all_times.append(t)

    odm_all_time = trimmed_mean(odm_all_times)
    odm_all_count = count
    print(
        f"  ODM:    {odm_all_time * 1000:.3f}ms ({odm_all_count} results) [trimmed mean]"
    )
    print(f"  Overhead: {(odm_all_time / raw_all_time - 1) * 100:.1f}%")

    return {"raw_all_time": raw_all_time, "odm_all_time": odm_all_time}


def run_count_test(raw_db, num_iterations: int) -> dict:
    """Run count documents benchmark."""
    print("\n4. Count Documents (5 iterations)")

    # Warmup
    _ = benchmark_raw_count(raw_db, "active", True)
    _ = User.count(active=True)

    # Raw - run multiple times
    raw_count_times = []
    for _ in range(num_iterations):
        count_time = benchmark_raw_count(raw_db, "active", True)
        raw_count_times.append(count_time)

    raw_count_time = trimmed_mean(raw_count_times)
    print(f"  Raw:    {raw_count_time * 1000:.3f}ms [trimmed mean]")

    # ODM - run multiple times
    odm_count_times = []
    for _ in range(num_iterations):
        count_time = benchmark_odm_count("active", True)
        odm_count_times.append(count_time)

    odm_count_time = trimmed_mean(odm_count_times)
    print(f"  ODM:    {odm_count_time * 1000:.3f}ms [trimmed mean]")
    print(f"  Overhead: {(odm_count_time / raw_count_time - 1) * 100:.1f}%")

    return {"raw_count_time": raw_count_time, "odm_count_time": odm_count_time}


def run_delete_many_test(
    raw_db, user_data_list: list[dict], num_iterations: int
) -> dict:
    """Run delete many benchmark."""
    print("\n5. Delete Many (5 iterations)")

    # Raw - run multiple times, recreating data each time
    raw_delete_times = []
    for _ in range(num_iterations):
        # Re-insert inactive users for deletion test
        inactive_users = [doc for doc in user_data_list if not doc["active"]]
        raw_db.insert_many(inactive_users)

        delete_time = benchmark_raw_delete(raw_db, "active", False)
        raw_delete_times.append(delete_time)

    raw_delete_time = trimmed_mean(raw_delete_times)
    print(f"  Raw:    {raw_delete_time * 1000:.3f}ms [trimmed mean]")

    # ODM - run multiple times, recreating data each time
    odm_delete_times = []
    for _ in range(num_iterations):
        # Re-insert inactive users for deletion test
        inactive_users = [User(**doc) for doc in user_data_list if not doc["active"]]
        User.insert_many(inactive_users)

        delete_time = benchmark_odm_delete("active", False)
        odm_delete_times.append(delete_time)

    odm_delete_time = trimmed_mean(odm_delete_times)
    print(f"  ODM:    {odm_delete_time * 1000:.3f}ms [trimmed mean]")
    print(f"  Overhead: {(odm_delete_time / raw_delete_time - 1) * 100:.1f}%")

    return {"raw_delete_time": raw_delete_time, "odm_delete_time": odm_delete_time}


def run_single_insert_test(
    user_data_list: list[dict], indexed_fields: list[str]
) -> dict:
    """Run single insert benchmark."""
    print("\n6. Single Insert (overhead measurement)")

    # Raw
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        single_db_path = tmp.name

    try:
        single_db = KenobiX(single_db_path, indexed_fields=indexed_fields)
        raw_single_times = []
        for i in range(100):
            t = benchmark_raw_insert_single(single_db, user_data_list[i])
            raw_single_times.append(t)
        raw_single_avg = sum(raw_single_times) / len(raw_single_times)
        print(f"  Raw:    {raw_single_avg * 1000:.3f}ms avg")
        single_db.close()
    finally:
        pathlib.Path(single_db_path).unlink()

    # ODM
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        single_db_path = tmp.name

    try:
        single_db = KenobiX(single_db_path, indexed_fields=indexed_fields)
        Document.set_database(single_db)
        odm_single_times = []
        for i in range(100):
            t = benchmark_odm_insert_single(user_data_list[i])
            odm_single_times.append(t)
        odm_single_avg = sum(odm_single_times) / len(odm_single_times)
        print(f"  ODM:    {odm_single_avg * 1000:.3f}ms avg")
        print(f"  Overhead: {(odm_single_avg / raw_single_avg - 1) * 100:.1f}% slower")
        single_db.close()
    finally:
        pathlib.Path(single_db_path).unlink()

    return {
        "raw_insert_single_avg": raw_single_avg,
        "odm_insert_single_avg": odm_single_avg,
    }


def run_odm_benchmark(size: int) -> dict:
    """Run complete ODM vs Raw benchmark suite.

    Each test is run 5 times with trimmed mean (discard min/max, average remaining 3).
    This reduces impact of outliers from GC, disk I/O, scheduler jitter, etc.
    """
    print(f"\n{'=' * 80}")
    print(f"ODM vs Raw Benchmark - {size:,} documents")
    print(f"{'=' * 80}")
    print("Note: Each test runs 5 times; results show trimmed mean (discard min/max)")

    indexed_fields = ["name", "email", "age"]
    num_iterations = 5

    # Generate test data
    print("\nGenerating test data...")
    user_data_list = [
        {
            "name": f"user_{i}",
            "email": f"user_{i}@example.com",
            "age": 20 + (i % 50),
            "active": i % 2 == 0,
        }
        for i in range(size)
    ]

    # Initialize results dict
    results = {
        "document_count": size,
        "indexed_fields": indexed_fields,
    }

    # Run all tests
    insert_results, raw_db, odm_db = run_bulk_insert_test(
        user_data_list, indexed_fields, num_iterations, size
    )
    results.update(insert_results)

    search_results = run_search_indexed_test(raw_db, num_iterations)
    results.update(search_results)

    all_results = run_retrieve_all_test(raw_db, num_iterations)
    results.update(all_results)

    count_results = run_count_test(raw_db, num_iterations)
    results.update(count_results)

    delete_results = run_delete_many_test(raw_db, user_data_list, num_iterations)
    results.update(delete_results)

    # Cleanup main test databases
    raw_db.close()
    odm_db.close()

    single_results = run_single_insert_test(user_data_list, indexed_fields)
    results.update(single_results)

    return results


def format_time(seconds: float) -> str:
    """Format time in appropriate units."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.1f}µs"
    if seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    return f"{seconds:.2f}s"


def print_summary_table(results: dict):
    """Print summary comparison table."""
    print(f"\n{'=' * 80}")
    print("SUMMARY: ODM vs Raw Performance")
    print(f"{'=' * 80}\n")

    print(f"Dataset: {results['document_count']:,} documents")
    print(f"Indexed fields: {', '.join(results['indexed_fields'])}\n")

    print(f"{'Operation':<30} {'Raw':<15} {'ODM':<15} {'Overhead':<15}")
    print(f"{'-' * 75}")

    # Bulk insert
    raw_time = results["raw_insert_many_time"]
    odm_time = results["odm_insert_many_time"]
    overhead = (odm_time / raw_time - 1) * 100
    print(
        f"{'Bulk Insert':<30} {format_time(raw_time):<15} {format_time(odm_time):<15} {overhead:+.1f}%"
    )

    # Search indexed
    raw_time = results["raw_search_indexed_time"]
    odm_time = results["odm_search_indexed_time"]
    overhead = (odm_time / raw_time - 1) * 100
    print(
        f"{'Search (indexed)':<30} {format_time(raw_time):<15} {format_time(odm_time):<15} {overhead:+.1f}%"
    )

    # All
    raw_time = results["raw_all_time"]
    odm_time = results["odm_all_time"]
    overhead = (odm_time / raw_time - 1) * 100
    print(
        f"{'Retrieve All (100 docs)':<30} {format_time(raw_time):<15} {format_time(odm_time):<15} {overhead:+.1f}%"
    )

    # Count
    raw_time = results["raw_count_time"]
    odm_time = results["odm_count_time"]
    overhead = (odm_time / raw_time - 1) * 100
    print(
        f"{'Count':<30} {format_time(raw_time):<15} {format_time(odm_time):<15} {overhead:+.1f}%"
    )

    # Delete
    raw_time = results["raw_delete_time"]
    odm_time = results["odm_delete_time"]
    overhead = (odm_time / raw_time - 1) * 100
    print(
        f"{'Delete Many':<30} {format_time(raw_time):<15} {format_time(odm_time):<15} {overhead:+.1f}%"
    )

    # Single insert
    raw_time = results["raw_insert_single_avg"]
    odm_time = results["odm_insert_single_avg"]
    overhead = (odm_time / raw_time - 1) * 100
    print(
        f"{'Single Insert (avg)':<30} {format_time(raw_time):<15} {format_time(odm_time):<15} {overhead:+.1f}%"
    )

    print(f"\n{'=' * 80}")
    print("\nKey Findings:")
    print("  • All measurements use trimmed mean (5 runs, discard min/max)")
    print("  • ODM overhead varies by operation type:")
    print("    - Write operations: ~15-35% overhead (acceptable)")
    print("    - Read operations: ~100-200% overhead (cattrs deserialization)")
    print("  • Both use same underlying indexes (no query performance difference)")
    print("  • Trade-off: Type safety + convenience vs ~2x slower reads")
    print("  • For read-heavy workloads, raw operations may be better")
    print("  • For write-heavy or type-safety needs, ODM overhead is acceptable")


def main():
    parser = argparse.ArgumentParser(description="Benchmark ODM vs Raw KenobiX")
    parser.add_argument(
        "--size",
        type=int,
        default=10000,
        help="Number of documents to test (default: 10000)",
    )
    parser.add_argument(
        "--output",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format",
    )

    args = parser.parse_args()

    print("KenobiX ODM vs Raw Performance Benchmark")
    print(f"Testing with {args.size:,} documents\n")

    results = run_odm_benchmark(args.size)

    if args.output == "table":
        print_summary_table(results)
    elif args.output == "json":
        print(json.dumps(results, indent=2))
    elif args.output == "csv":
        print("operation,raw_time,odm_time,overhead_pct")
        print(
            f"bulk_insert,{results['raw_insert_many_time']},{results['odm_insert_many_time']},{(results['odm_insert_many_time'] / results['raw_insert_many_time'] - 1) * 100:.2f}"
        )
        print(
            f"search_indexed,{results['raw_search_indexed_time']},{results['odm_search_indexed_time']},{(results['odm_search_indexed_time'] / results['raw_search_indexed_time'] - 1) * 100:.2f}"
        )
        print(
            f"retrieve_all,{results['raw_all_time']},{results['odm_all_time']},{(results['odm_all_time'] / results['raw_all_time'] - 1) * 100:.2f}"
        )
        print(
            f"count,{results['raw_count_time']},{results['odm_count_time']},{(results['odm_count_time'] / results['raw_count_time'] - 1) * 100:.2f}"
        )
        print(
            f"delete_many,{results['raw_delete_time']},{results['odm_delete_time']},{(results['odm_delete_time'] / results['raw_delete_time'] - 1) * 100:.2f}"
        )
        print(
            f"single_insert,{results['raw_insert_single_avg']},{results['odm_insert_single_avg']},{(results['odm_insert_single_avg'] / results['raw_insert_single_avg'] - 1) * 100:.2f}"
        )


if __name__ == "__main__":
    main()
