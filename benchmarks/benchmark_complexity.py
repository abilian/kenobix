#!/usr/bin/env python3
"""
Benchmark KenobiX vs KenobiX with varying record complexity.

Tests how document structure affects performance:
- Simple: 3 fields (id, name, value)
- Medium: 6 fields with mixed types
- Complex: 10+ fields with nested structures, arrays
- Very Complex: Large nested JSON with many arrays

Usage:
    python benchmarks/benchmark_complexity.py

Options:
    --size: Number of documents to test (default: 10000)
    --output: Output format (table, csv, json, default: table)
"""

import argparse
import json
import os
import random
import string
import sys
import tempfile
import time
from typing import Dict, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pathlib

from kenobix import KenobiX


def random_string(length: int = 10) -> str:
    """Generate random string."""
    return "".join(random.choices(string.ascii_letters, k=length))


def generate_simple_document(i: int) -> Dict:
    """Generate simple document: 3 fields, ~50 bytes."""
    return {"id": i, "name": f"user_{i}", "value": i * 10}


def generate_medium_document(i: int) -> Dict:
    """Generate medium document: 6 fields, ~100 bytes."""
    return {
        "id": i,
        "name": f"user_{i}",
        "age": 20 + (i % 50),
        "city": f"city_{i % 100}",
        "score": i * 0.5,
        "active": i % 2 == 0,
    }


def generate_complex_document(i: int) -> Dict:
    """Generate complex document: 10+ fields with nesting, ~300 bytes."""
    return {
        "id": i,
        "name": f"user_{i}",
        "email": f"user_{i}@example.com",
        "age": 20 + (i % 50),
        "city": f"city_{i % 100}",
        "country": f"country_{i % 20}",
        "score": i * 0.5,
        "active": i % 2 == 0,
        "tags": [f"tag_{i % 10}", f"tag_{(i + 1) % 10}", f"tag_{(i + 2) % 10}"],
        "metadata": {
            "created": f"2024-01-{(i % 28) + 1:02d}",
            "modified": f"2024-02-{(i % 28) + 1:02d}",
            "source": "benchmark",
            "version": i % 5,
        },
        "preferences": {
            "theme": "dark" if i % 2 else "light",
            "language": ["en", "es", "fr"][i % 3],
            "notifications": i % 3 == 0,
        },
    }


def generate_very_complex_document(i: int) -> Dict:
    """Generate very complex document: many nested structures, ~1KB."""
    return {
        "id": i,
        "name": f"user_{i}",
        "email": f"user_{i}@example.com",
        "username": random_string(15),
        "age": 20 + (i % 50),
        "city": f"city_{i % 100}",
        "country": f"country_{i % 20}",
        "postal_code": f"{10000 + i:05d}",
        "score": i * 0.5,
        "rating": (i % 5) + 1,
        "active": i % 2 == 0,
        "verified": i % 3 == 0,
        "premium": i % 5 == 0,
        "tags": [f"tag_{i % 10}", f"tag_{(i + 1) % 10}", f"tag_{(i + 2) % 10}"],
        "categories": [f"cat_{i % 5}", f"cat_{(i + 1) % 5}"],
        "metadata": {
            "created": f"2024-01-{(i % 28) + 1:02d}T12:00:00Z",
            "modified": f"2024-02-{(i % 28) + 1:02d}T12:00:00Z",
            "source": "benchmark",
            "version": i % 5,
            "ip_address": f"192.168.{i % 256}.{(i // 256) % 256}",
            "user_agent": f"Mozilla/5.0 (Test {i})",
        },
        "preferences": {
            "theme": "dark" if i % 2 else "light",
            "language": ["en", "es", "fr", "de", "it"][i % 5],
            "timezone": f"UTC{(i % 24) - 12:+d}",
            "notifications": {
                "email": i % 3 == 0,
                "sms": i % 5 == 0,
                "push": i % 2 == 0,
            },
            "privacy": {
                "show_email": i % 4 == 0,
                "show_phone": i % 6 == 0,
                "searchable": i % 3 == 0,
            },
        },
        "stats": {
            "login_count": i * 10,
            "post_count": i * 2,
            "follower_count": i * 5,
            "following_count": i * 3,
            "last_login": f"2024-03-{(i % 28) + 1:02d}T08:00:00Z",
        },
        "history": [
            {"action": "login", "timestamp": f"2024-03-{(i % 28) + 1:02d}"},
            {
                "action": "update_profile",
                "timestamp": f"2024-03-{((i + 1) % 28) + 1:02d}",
            },
            {
                "action": "post_content",
                "timestamp": f"2024-03-{((i + 2) % 28) + 1:02d}",
            },
        ],
        "billing": {
            "plan": ["free", "basic", "premium", "enterprise"][i % 4],
            "billing_cycle": ["monthly", "yearly"][i % 2],
            "amount": [0, 9.99, 29.99, 99.99][i % 4],
            "currency": "USD",
            "next_billing": f"2024-04-{(i % 28) + 1:02d}",
        },
    }


COMPLEXITY_LEVELS = {
    "simple": (generate_simple_document, "~50 bytes", ["id", "name"]),
    "medium": (generate_medium_document, "~100 bytes", ["id", "name", "age", "city"]),
    "complex": (
        generate_complex_document,
        "~300 bytes",
        ["id", "name", "email", "age", "city"],
    ),
    "very_complex": (
        generate_very_complex_document,
        "~1KB",
        ["id", "name", "email", "age", "city", "score"],
    ),
}


def benchmark_operations(
    db, documents: List[Dict], db_name: str, complexity: str
) -> Dict:
    """Run benchmark operations on database."""
    generator, size_desc, indexed_fields = COMPLEXITY_LEVELS[complexity]

    results = {
        "database": db_name,
        "complexity": complexity,
        "doc_count": len(documents),
        "doc_size": size_desc,
        "avg_doc_bytes": len(json.dumps(documents[0])) if documents else 0,
    }

    # 1. Bulk insert
    print(f"    Inserting {len(documents):,} documents...")
    start = time.time()
    db.insert_many(documents)
    insert_time = time.time() - start
    results["insert_time"] = insert_time
    results["insert_rate"] = len(documents) / insert_time if insert_time > 0 else 0

    # 2. Single searches (indexed)
    print("    Searching indexed field (id)...")
    search_times = []
    for _ in range(10):
        search_id = random.randint(0, len(documents) - 1)
        start = time.time()
        result = db.search("id", search_id)
        search_times.append(time.time() - start)
    results["search_indexed_avg"] = sum(search_times) / len(search_times)
    results["search_indexed_min"] = min(search_times)

    # 3. Single search (non-indexed)
    if "city" in documents[0]:
        print("    Searching non-indexed field (city)...")
        search_times = []
        for _ in range(10):
            start = time.time()
            result = db.search("city", "city_50")
            search_times.append(time.time() - start)
        results["search_unindexed_avg"] = sum(search_times) / len(search_times)
    else:
        results["search_unindexed_avg"] = None

    # 4. Retrieve all (pagination test)
    print("    Retrieving pages...")
    start = time.time()
    total = 0
    for offset in range(0, min(1000, len(documents)), 100):
        page = db.all(limit=100, offset=offset)
        total += len(page)
    results["retrieve_time"] = time.time() - start
    results["retrieve_count"] = total

    # 5. Update operations
    print("    Updating 100 documents...")
    start = time.time()
    for i in range(100):
        db.update("id", i, {"updated": True})
    results["update_time"] = time.time() - start

    # 6. Delete operations
    print("    Deleting 100 documents...")
    start = time.time()
    for i in range(len(documents) - 100, len(documents)):
        db.remove("id", i)
    results["delete_time"] = time.time() - start

    return results


def run_complexity_benchmark(complexity: str, count: int) -> List[Dict]:
    """Run benchmark for a specific complexity level."""
    generator, size_desc, indexed_fields = COMPLEXITY_LEVELS[complexity]

    print(f"\n{'─' * 80}")
    print(f"Complexity: {complexity.upper()} ({size_desc})")
    print(f"{'─' * 80}")

    # Generate documents
    print(f"  Generating {count:,} documents...")
    documents = [generator(i) for i in range(count)]
    actual_size = len(json.dumps(documents[0]))
    print(f"  Actual document size: {actual_size} bytes")

    results = []

    # Test without indexes
    print("\n  Testing KenobiX (no indexes)...")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=[])
        result = benchmark_operations(db, documents, "KenobiX (no idx)", complexity)
        db.close()

        # Get file size
        result["db_file_size"] = pathlib.Path(db_path).stat().st_size
        results.append(result)
    finally:
        if pathlib.Path(db_path).exists():
            pathlib.Path(db_path).unlink()

    # Test with indexes
    print("\n  Testing KenobiX (with indexes)...")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=indexed_fields)
        result = benchmark_operations(db, documents, "KenobiX (indexed)", complexity)
        db.close()

        # Get file size
        result["db_file_size"] = pathlib.Path(db_path).stat().st_size
        result["indexed_fields"] = indexed_fields
        results.append(result)
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
    for unit in ["B", "KB", "MB"]:
        if bytes < 1024:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024
    return f"{bytes:.1f}GB"


def print_comparison_table(all_results: List[Dict]):
    """Print results in comparison table."""
    print("\n" + "=" * 120)
    print("COMPLEXITY BENCHMARK RESULTS")
    print("=" * 120)

    # Group by complexity
    complexities = ["simple", "medium", "complex", "very_complex"]

    for complexity in complexities:
        comp_results = [r for r in all_results if r["complexity"] == complexity]
        if not comp_results:
            continue

        print(f"\n{'─' * 120}")
        print(
            f"Document Complexity: {complexity.upper()} (Document size: {comp_results[0]['doc_size']})"
        )
        print(f"{'─' * 120}")

        # Table header
        print(
            f"{'Database':<30} {'Insert':<18} {'Search (idx)':<15} {'Search (no idx)':<15} {'Update 100':<12} {'File Size':<12}"
        )
        print(
            f"{'':<30} {'Time | Rate':<18} {'Avg | Min':<15} {'Avg':<15} {'Time':<12} {'':<12}"
        )
        print(f"{'─' * 120}")

        for result in comp_results:
            name = result["database"]
            if result.get("indexed_fields"):
                name += f" (+{len(result['indexed_fields'])} idx)"

            insert_str = (
                f"{format_time(result['insert_time'])} | {result['insert_rate']:.0f}/s"
            )

            search_idx_str = f"{format_time(result['search_indexed_avg'])} | {format_time(result['search_indexed_min'])}"

            if result.get("search_unindexed_avg"):
                search_noidx_str = format_time(result["search_unindexed_avg"])
            else:
                search_noidx_str = "N/A"

            update_str = format_time(result["update_time"])
            size_str = format_size(result["db_file_size"])

            print(
                f"{name:<30} {insert_str:<18} {search_idx_str:<15} {search_noidx_str:<15} {update_str:<12} {size_str:<12}"
            )

        # Show speedup comparison
        print()
        if len(comp_results) == 2:
            old, new = comp_results[0], comp_results[1]

            if new["search_indexed_avg"] > 0:
                speedup = old["search_indexed_avg"] / new["search_indexed_avg"]
                print(f"  ✓ Indexed search speedup: {speedup:.1f}x faster")

            if old.get("search_unindexed_avg") and new.get("search_unindexed_avg"):
                speedup = old["search_unindexed_avg"] / new["search_unindexed_avg"]
                print(f"  ✓ Unindexed search speedup: {speedup:.1f}x faster")

            if new["update_time"] > 0:
                speedup = old["update_time"] / new["update_time"]
                if speedup > 1:
                    print(f"  ✓ Update speedup: {speedup:.1f}x faster")
                else:
                    print(f"  ⚠ Update slower: {1 / speedup:.1f}x (index maintenance)")

            size_overhead = (
                (new["db_file_size"] - old["db_file_size"]) / old["db_file_size"] * 100
            )
            print(
                f"  ℹ Storage overhead: {size_overhead:+.1f}% (indexes use VIRTUAL columns, minimal overhead)"
            )

    print("=" * 120)
    print("\nKey Insights:")
    print("  • Simple docs: Indexing overhead noticeable but search gains significant")
    print("  • Complex docs: Greater benefit from indexing as JSON parsing is heavier")
    print("  • VIRTUAL generated columns minimize storage impact")


def main():
    parser = argparse.ArgumentParser(description="Benchmark record complexity impact")
    parser.add_argument(
        "--size",
        type=int,
        default=10000,
        help="Number of documents to test (default: 10000)",
    )
    parser.add_argument(
        "--complexities",
        type=str,
        default="simple,medium,complex,very_complex",
        help="Comma-separated list of complexity levels to test",
    )
    parser.add_argument(
        "--output",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format",
    )

    args = parser.parse_args()

    complexities = [c.strip() for c in args.complexities.split(",")]

    print("Benchmarking Record Complexity Impact")
    print(f"Document count: {args.size:,}")
    print(f"Complexity levels: {', '.join(complexities)}")

    all_results = []

    for complexity in complexities:
        if complexity not in COMPLEXITY_LEVELS:
            print(f"Unknown complexity level: {complexity}")
            continue

        results = run_complexity_benchmark(complexity, args.size)
        all_results.extend(results)

    # Output results
    if args.output == "table":
        print_comparison_table(all_results)
    elif args.output == "json":
        print(json.dumps(all_results, indent=2))
    elif args.output == "csv":
        print(
            "database,complexity,doc_count,insert_time,search_indexed_avg,search_unindexed_avg,update_time,db_file_size"
        )
        for r in all_results:
            print(
                f"{r['database']},{r['complexity']},{r['doc_count']},"
                f"{r['insert_time']},{r['search_indexed_avg']},"
                f"{r.get('search_unindexed_avg', 'N/A')},{r['update_time']},{r['db_file_size']}"
            )


if __name__ == "__main__":
    main()
