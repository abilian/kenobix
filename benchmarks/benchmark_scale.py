#!/usr/bin/env python3
"""
Benchmark KenobiX performance across different dataset sizes and index configurations.

Tests performance at 1k, 10k, 100k, and 1M document scales.
Compares indexed vs non-indexed field searches.

Usage:
    python benchmarks/benchmark_scale.py

Options:
    --sizes: Comma-separated list of sizes to test (default: 1000,10000,100000)
    --max-size: Include 1M test (slow, default: no)
    --output: Output format (table, csv, json, default: table)
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tempfile
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(pathlib.Path(__file__).parent, "..", "src"))

import pathlib

from kenobix import KenobiX


def generate_documents(count: int, pattern: str = "simple") -> list[dict]:
    """Generate test documents.

    Args:
        count: Number of documents to generate
        pattern: Document pattern (simple, medium, complex)
    """
    if pattern == "simple":
        return [{"id": i, "name": f"user_{i}", "value": i * 10} for i in range(count)]
    if pattern == "medium":
        return [
            {
                "id": i,
                "name": f"user_{i}",
                "age": 20 + (i % 50),
                "city": f"city_{i % 100}",
                "score": i * 0.5,
                "active": i % 2 == 0,
            }
            for i in range(count)
        ]
    # complex
    return [
        {
            "id": i,
            "name": f"user_{i}",
            "email": f"user_{i}@example.com",
            "age": 20 + (i % 50),
            "city": f"city_{i % 100}",
            "country": f"country_{i % 20}",
            "score": i * 0.5,
            "active": i % 2 == 0,
            "tags": [f"tag_{i % 10}", f"tag_{(i + 1) % 10}"],
            "metadata": {
                "created": f"2024-01-{(i % 28) + 1:02d}",
                "source": "benchmark",
                "version": i % 5,
            },
        }
        for i in range(count)
    ]


def benchmark_insert(db, documents: list[dict]) -> float:
    """Benchmark bulk insert operation."""
    start = time.time()
    db.insert_many(documents)
    return time.time() - start


def benchmark_search_indexed(db, field: str, value) -> tuple[float, int]:
    """Benchmark search on indexed field."""
    start = time.time()
    results = db.search(field, value)
    elapsed = time.time() - start
    return elapsed, len(results)


def benchmark_search_unindexed(db, field: str, value) -> tuple[float, int]:
    """Benchmark search on non-indexed field."""
    start = time.time()
    results = db.search(field, value)
    elapsed = time.time() - start
    return elapsed, len(results)


def benchmark_search_range(db, count: int) -> tuple[float, int]:
    """Benchmark range-like searches (multiple searches)."""
    start = time.time()
    all_results = []
    # Search for 10 different values
    for i in range(0, min(count, 100), 10):
        results = db.search("id", i)
        all_results.extend(results)
    elapsed = time.time() - start
    return elapsed, len(all_results)


def benchmark_pagination(db, count: int) -> float:
    """Benchmark pagination through dataset."""
    start = time.time()
    page_size = 100
    total_retrieved = 0
    offset = 0

    # Read first 10 pages
    for _ in range(10):
        results = db.all(limit=page_size, offset=offset)
        total_retrieved += len(results)
        offset += page_size
        if not results:
            break

    return time.time() - start


def run_benchmark_suite(
    db_name: str,
    db_factory,
    size: int,
    documents: list[dict],
    indexed_fields: list[str] | None = None,
) -> dict:
    """Run full benchmark suite on a database instance."""
    results = {
        "name": db_name,
        "size": size,
        "indexed_fields": indexed_fields or [],
    }

    # Create database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        if indexed_fields:
            db = db_factory(db_path, indexed_fields=indexed_fields)
        else:
            db = db_factory(db_path)

        # 1. Insert benchmark
        print(f"  Inserting {size:,} documents...")
        insert_time = benchmark_insert(db, documents)
        results["insert_time"] = insert_time
        results["insert_rate"] = size / insert_time if insert_time > 0 else 0

        # 2. Search indexed field
        print("  Searching indexed field...")
        search_time, search_count = benchmark_search_indexed(db, "id", size // 2)
        results["search_indexed_time"] = search_time
        results["search_indexed_count"] = search_count

        # 3. Search unindexed field
        if len(documents[0]) > 3:  # Has extra fields
            print("  Searching unindexed field...")
            search_time, search_count = benchmark_search_unindexed(
                db, "city", "city_50"
            )
            results["search_unindexed_time"] = search_time
            results["search_unindexed_count"] = search_count
        else:
            results["search_unindexed_time"] = None
            results["search_unindexed_count"] = 0

        # 4. Multiple searches
        print("  Range-like search (10 queries)...")
        range_time, range_count = benchmark_search_range(db, size)
        results["range_search_time"] = range_time
        results["range_search_count"] = range_count

        # 5. Pagination
        print("  Pagination (10 pages of 100)...")
        page_time = benchmark_pagination(db, size)
        results["pagination_time"] = page_time

        # 6. Database stats
        if hasattr(db, "stats"):
            stats = db.stats()
            results["db_size_bytes"] = stats.get("database_size_bytes", 0)
        else:
            results["db_size_bytes"] = pathlib.Path(db_path).stat().st_size

        db.close()

    finally:
        if pathlib.Path(db_path).exists():
            pathlib.Path(db_path).unlink()

    return results


def format_time(seconds: float) -> str:
    """Format time in appropriate units."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.1f}µs"
    if seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    return f"{seconds:.2f}s"


def format_size(bytes: int) -> str:
    """Format byte size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes < 1024:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024
    return f"{bytes:.1f}TB"


def print_size_section(size: int, size_results: list[dict]) -> None:
    """Print results for a single size level."""
    print(f"\n{'─' * 100}")
    print(f"Dataset Size: {size:,} documents")
    print(f"{'─' * 100}")

    # Header
    print(
        f"{'Database':<25} {'Insert':<15} {'Search (idx)':<15} {'Search (no idx)':<15} {'Pagination':<15}"
    )
    print(f"{'':<25} {'Time | Rate':<15} {'Time':<15} {'Time':<15} {'Time':<15}")
    print(f"{'─' * 100}")

    for result in size_results:
        name = result["name"]
        if result["indexed_fields"]:
            name += f" ({len(result['indexed_fields'])} indexes)"

        insert_str = (
            f"{format_time(result['insert_time'])} | {result['insert_rate']:.0f}/s"
        )
        search_idx_str = format_time(result["search_indexed_time"])

        if result["search_unindexed_time"] is not None:
            search_no_idx_str = format_time(result["search_unindexed_time"])
        else:
            search_no_idx_str = "N/A"

        page_str = format_time(result["pagination_time"])

        print(
            f"{name:<25} {insert_str:<15} {search_idx_str:<15} {search_no_idx_str:<15} {page_str:<15}"
        )


def print_scale_speedup(old: dict, new: dict) -> None:
    """Print speedup comparison for scale benchmark."""
    print()

    if new["search_indexed_time"] > 0:
        speedup = old["search_indexed_time"] / new["search_indexed_time"]
        print(f"  Indexed search speedup: {speedup:.1f}x faster")

    if old["search_unindexed_time"] and new["search_unindexed_time"]:
        # Both did unindexed search
        if new["search_unindexed_time"] > 0:
            speedup = old["search_unindexed_time"] / new["search_unindexed_time"]
            print(f"  Unindexed search speedup: {speedup:.1f}x")

    if new["insert_time"] > 0:
        ratio = new["insert_time"] / old["insert_time"]
        if ratio > 1:
            print(
                f"  Insert overhead: {ratio:.2f}x (indexed version creates indexes)"
            )
        else:
            print(f"  Insert speedup: {1 / ratio:.2f}x")


def print_results_table(all_results: list[dict]):
    """Print results in a formatted table."""
    print("\n" + "=" * 100)
    print("BENCHMARK RESULTS")
    print("=" * 100)

    sizes = sorted({r["size"] for r in all_results})

    for size in sizes:
        size_results = [r for r in all_results if r["size"] == size]

        print_size_section(size, size_results)

        # Show speedup if we have two results (no idx vs indexed)
        if len(size_results) == 2:
            print_scale_speedup(size_results[0], size_results[1])

        # DB size
        print()
        for result in size_results:
            print(
                f"  {result['name']} database size: {format_size(result['db_size_bytes'])}"
            )

    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(description="Benchmark KenobiX at scale")
    parser.add_argument(
        "--sizes",
        type=str,
        default="1000,10000,100000",
        help="Comma-separated list of dataset sizes",
    )
    parser.add_argument(
        "--max-size", action="store_true", help="Include 1M document test (very slow)"
    )
    parser.add_argument(
        "--output",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format",
    )
    parser.add_argument(
        "--pattern",
        choices=["simple", "medium", "complex"],
        default="medium",
        help="Document complexity pattern",
    )

    args = parser.parse_args()

    sizes = [int(s.strip()) for s in args.sizes.split(",")]
    if args.max_size:
        sizes.append(1_000_000)

    print("Benchmarking KenobiX Performance")
    print(f"Document pattern: {args.pattern}")
    print(f"Dataset sizes: {', '.join(f'{s:,}' for s in sizes)}")
    print()

    all_results = []

    for size in sizes:
        print(f"\n{'=' * 60}")
        print(f"Testing with {size:,} documents")
        print(f"{'=' * 60}")

        # Generate documents
        print(f"Generating {size:,} documents...")
        documents = generate_documents(size, args.pattern)

        # Benchmark without indexes
        print("\n1. KenobiX (no indexes)")
        result_no_idx = run_benchmark_suite(
            "KenobiX (no indexes)", KenobiX, size, documents, indexed_fields=[]
        )
        all_results.append(result_no_idx)

        # Benchmark with indexes
        print("\n2. KenobiX (with indexes)")
        indexed_fields = ["id", "name"]
        if args.pattern != "simple":
            indexed_fields.extend(["age", "city"])

        result_with_idx = run_benchmark_suite(
            "KenobiX (indexed)", KenobiX, size, documents, indexed_fields=indexed_fields
        )
        all_results.append(result_with_idx)

    # Output results
    if args.output == "table":
        print_results_table(all_results)
    elif args.output == "json":
        print(json.dumps(all_results, indent=2))
    elif args.output == "csv":
        # CSV header
        print(
            "database,size,insert_time,insert_rate,search_indexed_time,search_unindexed_time,pagination_time,db_size_bytes"
        )
        for r in all_results:
            print(
                f"{r['name']},{r['size']},{r['insert_time']},{r['insert_rate']},"
                f"{r['search_indexed_time']},{r['search_unindexed_time']},"
                f"{r['pagination_time']},{r['db_size_bytes']}"
            )


if __name__ == "__main__":
    main()
