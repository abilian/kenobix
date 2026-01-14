"""Info command functionality.

This module provides functions for displaying database information
and inferring pseudo-schemas from JSON data.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .utils import check_database_exists, get_all_tables


def get_table_info(db_path: str, table_name: str) -> dict[str, Any]:
    """
    Get detailed information about a table.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table

    Returns:
        Dictionary with table information
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]

    # Get table schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [
        {
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "primary_key": bool(row[5]),
        }
        for row in cursor.fetchall()
    ]

    # Get indexes
    cursor.execute(f"PRAGMA index_list({table_name})")
    indexes = []
    for row in cursor.fetchall():
        index_name = row[1]
        cursor.execute(f"PRAGMA index_info({index_name})")
        index_columns = [col[2] for col in cursor.fetchall()]
        indexes.append({"name": index_name, "columns": index_columns})

    conn.close()

    return {
        "name": table_name,
        "row_count": count,
        "columns": columns,
        "indexes": indexes,
    }


def infer_json_type(value: Any) -> str:
    """Infer a type name from a JSON value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def merge_types(types: set[str]) -> str:
    """Merge multiple types into a single type description."""
    # Remove null for display, track separately
    has_null = "null" in types
    types = types - {"null"}

    if not types:
        return "null"

    # Merge numeric types
    if types == {"integer", "number"}:
        types = {"number"}

    if len(types) == 1:
        result = types.pop()
    else:
        result = " | ".join(sorted(types))

    if has_null and result != "null":
        result += "?"  # Mark as nullable
    return result


def _get_display_value(value: Any) -> Any:
    """Convert a value to a display-friendly format for sample values."""
    if isinstance(value, str) and len(value) > 50:
        return value[:47] + "..."
    if isinstance(value, (list, dict)):
        return f"<{infer_json_type(value)}>"
    return value


def _analyze_record(
    data: dict[str, Any], field_info: dict[str, dict[str, Any]]
) -> None:
    """Analyze a single record and update field_info."""
    for field_name, value in data.items():
        if field_name not in field_info:
            field_info[field_name] = {
                "types": set(),
                "count": 0,
                "sample_values": [],
            }

        field_info[field_name]["types"].add(infer_json_type(value))
        field_info[field_name]["count"] += 1

        # Keep a few sample values for display
        samples = field_info[field_name]["sample_values"]
        if len(samples) < 3 and value is not None:
            display_value = _get_display_value(value)
            if display_value not in samples:
                samples.append(display_value)


def _finalize_schema(
    field_info: dict[str, dict[str, Any]], records_analyzed: int
) -> None:
    """Finalize schema info by computing types and presence."""
    for info in field_info.values():
        info["type"] = merge_types(info["types"])
        info["presence"] = info["count"] / records_analyzed if records_analyzed else 0
        info["optional"] = info["count"] < records_analyzed
        del info["types"]  # Clean up intermediate data


def infer_pseudo_schema(
    db_path: str, table_name: str, sample_size: int = 100
) -> dict[str, dict[str, Any]]:
    """
    Infer a pseudo-schema by analyzing JSON data in the table.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table
        sample_size: Number of records to sample for inference

    Returns:
        Dictionary mapping field names to their inferred properties
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get total count and sample records
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_count = cursor.fetchone()[0]
    cursor.execute(f"SELECT data FROM {table_name} LIMIT {sample_size}")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {}

    # Analyze fields
    field_info: dict[str, dict[str, Any]] = {}
    records_analyzed = len(rows)

    for (data_json,) in rows:
        try:
            data = json.loads(data_json)
            if isinstance(data, dict):
                _analyze_record(data, field_info)
        except json.JSONDecodeError:
            continue

    _finalize_schema(field_info, records_analyzed)

    # Add metadata and return
    return {
        "_meta": {
            "records_analyzed": records_analyzed,
            "total_records": total_count,
            "sample_coverage": records_analyzed / total_count if total_count else 0,
        },
        **dict(sorted(field_info.items())),
    }


def get_indexed_fields(db_path: str, table_name: str) -> list[str]:
    """Get list of indexed fields for a table (from KenobiX indexes)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # KenobiX creates indexes with naming pattern: {table_name}_idx_{field_name}
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
        (table_name,),
    )

    prefix = f"{table_name}_idx_"
    indexed = []
    for (index_name,) in cursor.fetchall():
        if index_name.startswith(prefix):
            field_name = index_name[len(prefix) :]
            indexed.append(field_name)

    conn.close()
    return sorted(indexed)


def show_single_table_info(db_path: str, table_name: str, verbosity: int = 0) -> None:
    """
    Show detailed information for a single table including pseudo-schema.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table
        verbosity: Verbosity level (0=basic, 1=detailed, 2+=very detailed)
    """
    info = get_table_info(db_path, table_name)
    indexed_fields = get_indexed_fields(db_path, table_name)
    schema = infer_pseudo_schema(db_path, table_name)

    # Header
    print(f"\nTable: {table_name}")
    print(f"Records: {info['row_count']:,}")

    # Indexed fields
    if indexed_fields:
        print(f"Indexed fields: {', '.join(indexed_fields)}")
    else:
        print("Indexed fields: (none)")

    # Pseudo-schema
    meta = schema.pop("_meta", {})
    if schema:
        print(
            f"\nPseudo-schema (inferred from {meta.get('records_analyzed', 0)} records):"
        )
        for field_name, field_info in schema.items():
            type_str = field_info["type"]
            presence = field_info["presence"]
            indexed_marker = " [indexed]" if field_name in indexed_fields else ""

            # Show presence percentage if not 100%
            if presence < 1.0:
                presence_str = f" ({presence:.0%} present)"
            else:
                presence_str = ""

            print(f"  {field_name}: {type_str}{presence_str}{indexed_marker}")

            # Show sample values at higher verbosity
            if verbosity >= 1 and field_info.get("sample_values"):
                samples = field_info["sample_values"]
                samples_str = ", ".join(repr(s) for s in samples[:3])
                print(f"    examples: {samples_str}")
    else:
        print("\nPseudo-schema: (no data to analyze)")

    # SQLite schema details at higher verbosity
    if verbosity >= 2:
        print("\nSQLite Schema:")
        for col in info["columns"]:
            pk = " [PRIMARY KEY]" if col["primary_key"] else ""
            notnull = " NOT NULL" if col["notnull"] else ""
            print(f"  {col['name']}: {col['type']}{pk}{notnull}")

        if info["indexes"]:
            print("\nIndexes:")
            for idx in info["indexes"]:
                print(f"  {idx['name']} on ({', '.join(idx['columns'])})")


def print_database_header(db_path: str, tables: list[str]) -> None:
    """Print basic database information header."""
    db_file = Path(db_path)
    file_size = db_file.stat().st_size

    print(f"Database: {db_path}")
    print(f"Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    print(f"Tables: {len(tables)}")


def show_basic_table_list(db_path: str, tables: list[str]) -> None:
    """Show basic table list with record counts (verbosity 0)."""
    print("\nTables:")
    for table in tables:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        conn.close()
        print(f"  - {table} ({count:,} records)")


def print_column_details(columns: list[dict[str, Any]]) -> None:
    """Print detailed column information."""
    print("    Column Details:")
    for col in columns:
        pk = " [PRIMARY KEY]" if col["primary_key"] else ""
        notnull = " NOT NULL" if col["notnull"] else ""
        default = f" DEFAULT {col['default']}" if col["default"] else ""
        print(f"      - {col['name']}: {col['type']}{pk}{notnull}{default}")


def print_index_details(indexes: list[dict[str, Any]], verbosity: int) -> None:
    """Print index information."""
    if not indexes:
        return

    print(f"    Indexes: {len(indexes)}")
    if verbosity >= 2:
        for idx in indexes:
            print(f"      - {idx['name']} on ({', '.join(idx['columns'])})")


def show_detailed_table_info(db_path: str, tables: list[str], verbosity: int) -> None:
    """Show detailed table information (verbosity >= 1)."""
    print("\nTable Details:")
    for table in tables:
        info = get_table_info(db_path, table)
        print(f"\n  {info['name']}:")
        print(f"    Records: {info['row_count']:,}")
        print(f"    Columns: {len(info['columns'])}")

        if verbosity >= 2:
            print_column_details(info["columns"])

        print_index_details(info["indexes"], verbosity)


def show_database_info(
    db_path: str, verbosity: int = 0, table_name: str | None = None
) -> None:
    """
    Show database information with varying detail levels.

    Args:
        db_path: Path to the SQLite database
        verbosity: Verbosity level (0=basic, 1=detailed, 2+=very detailed)
        table_name: Optional table name to show detailed info for that table
    """
    check_database_exists(db_path)

    all_tables = get_all_tables(db_path)
    if not all_tables:
        print(f"No tables found in database: {db_path}")
        return

    # Single table mode: show detailed info with pseudo-schema
    if table_name:
        if table_name not in all_tables:
            print(f"Error: Table '{table_name}' not found in database", file=sys.stderr)
            print(f"Available tables: {', '.join(all_tables)}", file=sys.stderr)
            sys.exit(1)
        print(f"Database: {db_path}")
        show_single_table_info(db_path, table_name, verbosity)
        return

    # Multi-table mode: show database overview
    print_database_header(db_path, all_tables)

    if verbosity == 0:
        show_basic_table_list(db_path, all_tables)
    else:
        show_detailed_table_info(db_path, all_tables, verbosity)
