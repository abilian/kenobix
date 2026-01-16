"""Schema command functionality.

This module provides functions for inferring and displaying
the implicit schema of KenobiX tables.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import Any

from .utils import check_database_exists, get_all_tables, resolve_database


def infer_type(value: Any) -> str:
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
        result += "?"
    return result


def analyze_value(
    value: Any,
    prefix: str,
    field_info: dict[str, dict[str, Any]],
    depth: int = 0,
    max_depth: int = 5,
) -> None:
    """
    Recursively analyze a value and update field_info.

    Args:
        value: The value to analyze
        prefix: Field name prefix (for nested fields)
        field_info: Dictionary to update with field information
        depth: Current nesting depth
        max_depth: Maximum depth to recurse into nested objects
    """
    if prefix not in field_info:
        field_info[prefix] = {
            "types": set(),
            "count": 0,
            "sample_values": [],
            "null_count": 0,
        }

    field_info[prefix]["types"].add(infer_type(value))
    field_info[prefix]["count"] += 1

    if value is None:
        field_info[prefix]["null_count"] += 1
    elif isinstance(value, dict) and depth < max_depth:
        # Recurse into nested objects
        for k, v in value.items():
            nested_key = f"{prefix}.{k}" if prefix else k
            analyze_value(v, nested_key, field_info, depth + 1, max_depth)
    elif isinstance(value, list) and value and depth < max_depth:
        # Analyze first few list items to infer element types
        element_types: set[str] = set()
        element_types.update(infer_type(item) for item in value[:5])
        field_info[prefix]["element_types"] = element_types
    else:
        # Store sample values for primitives
        samples = field_info[prefix]["sample_values"]
        if len(samples) < 3 and value is not None:
            display_value = _format_sample(value)
            if display_value not in samples:
                samples.append(display_value)


def _format_sample(value: Any) -> str:
    """Format a value for display as a sample."""
    if isinstance(value, str):
        if len(value) > 40:
            return repr(value[:37] + "...")
        return repr(value)
    if isinstance(value, (list, dict)):
        return f"<{infer_type(value)}>"
    return repr(value)


def _finalize_field_info(
    field_info: dict[str, dict[str, Any]], records_analyzed: int
) -> dict[str, dict[str, Any]]:
    """Convert raw field_info into final schema fields."""
    fields: dict[str, dict[str, Any]] = {}
    for field_name, info in sorted(field_info.items()):
        field_schema: dict[str, Any] = {
            "type": merge_types(info["types"]),
            "count": info["count"],
            "presence": round(info["count"] / records_analyzed * 100, 1),
        }

        if info["null_count"] > 0:
            field_schema["null_count"] = info["null_count"]

        if info.get("element_types"):
            field_schema["element_types"] = sorted(info["element_types"])

        if info["sample_values"]:
            field_schema["examples"] = info["sample_values"]

        fields[field_name] = field_schema
    return fields


def infer_schema(
    db_path: str,
    table_name: str,
    sample_size: int | None = None,
) -> dict[str, Any]:
    """
    Infer schema by analyzing all (or sampled) records in a table.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table
        sample_size: Number of records to sample (None = all records)

    Returns:
        Dictionary with schema information
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get total count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_count = cursor.fetchone()[0]

    # Fetch records
    if sample_size and sample_size < total_count:
        cursor.execute(f"SELECT data FROM {table_name} LIMIT {sample_size}")
        is_sampled = True
    else:
        cursor.execute(f"SELECT data FROM {table_name}")
        is_sampled = False

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            "_meta": {
                "table": table_name,
                "total_records": 0,
                "records_analyzed": 0,
                "sampled": False,
            },
            "fields": {},
        }

    # Analyze all records
    field_info: dict[str, dict[str, Any]] = {}
    records_analyzed = len(rows)

    for (data_json,) in rows:
        try:
            data = json.loads(data_json)
            if isinstance(data, dict):
                for key, value in data.items():
                    analyze_value(value, key, field_info)
        except json.JSONDecodeError:
            continue

    fields = _finalize_field_info(field_info, records_analyzed)

    return {
        "_meta": {
            "table": table_name,
            "total_records": total_count,
            "records_analyzed": records_analyzed,
            "sampled": is_sampled,
        },
        "fields": fields,
    }


def format_schema_text(schema: dict[str, Any], verbose: int = 0) -> str:
    """Format schema as human-readable text."""
    lines: list[str] = []
    meta = schema["_meta"]
    fields = schema["fields"]

    # Header
    lines.extend((
        f"Table: {meta['table']}",
        f"Records: {meta['total_records']:,}",
    ))
    if meta["sampled"]:
        lines.append(f"Analyzed: {meta['records_analyzed']:,} (sampled)")
    lines.append("")

    if not fields:
        lines.append("(no data)")
        return "\n".join(lines)

    # Fields
    lines.append("Fields:")
    for name, info in fields.items():
        type_str = info["type"]
        presence = info["presence"]

        # Build field line
        line = f"  {name}: {type_str}"

        # Add presence if not 100%
        if presence < 100:
            line += f" ({presence}%)"

        # Add element types for arrays
        if "element_types" in info:
            elem_types = ", ".join(info["element_types"])
            line += f" [{elem_types}]"

        lines.append(line)

        # Show examples at higher verbosity
        if verbose >= 1 and info.get("examples"):
            examples = ", ".join(str(e) for e in info["examples"][:3])
            lines.append(f"    examples: {examples}")

    return "\n".join(lines)


def format_schema_json(schema: dict[str, Any]) -> str:
    """Format schema as JSON."""
    return json.dumps(schema, indent=2, ensure_ascii=False)


def show_schema(
    db_path: str,
    table_name: str | None = None,
    sample_size: int | None = None,
    output_format: str = "text",
    verbose: int = 0,
) -> None:
    """
    Display schema for one or all tables.

    Args:
        db_path: Path to the database
        table_name: Optional table name (None = all tables)
        sample_size: Optional sample size for large tables
        output_format: Output format (text or json)
        verbose: Verbosity level
    """
    check_database_exists(db_path)

    all_tables = get_all_tables(db_path)
    if not all_tables:
        print(f"No tables found in database: {db_path}", file=sys.stderr)
        return

    if table_name:
        if table_name not in all_tables:
            print(f"Error: Table '{table_name}' not found", file=sys.stderr)
            print(f"Available tables: {', '.join(all_tables)}", file=sys.stderr)
            sys.exit(1)
        tables = [table_name]
    else:
        tables = all_tables

    if output_format == "json":
        # JSON output: single object with all tables
        tables_dict: dict[str, Any] = {}
        for table in tables:
            schema = infer_schema(db_path, table, sample_size)
            tables_dict[table] = schema
        result = {"database": db_path, "tables": tables_dict}
        print(format_schema_json(result))
    else:
        # Text output
        print(f"Database: {db_path}")
        print()
        for i, table in enumerate(tables):
            if i > 0:
                print()
                print("-" * 40)
                print()
            schema = infer_schema(db_path, table, sample_size)
            print(format_schema_text(schema, verbose))


def cmd_schema(args: argparse.Namespace) -> None:
    """Handle the schema command."""
    db_path = resolve_database(args)
    show_schema(
        db_path,
        table_name=getattr(args, "table", None),
        sample_size=getattr(args, "sample", None),
        output_format=getattr(args, "format", "text"),
        verbose=getattr(args, "verbose", 0),
    )


def add_schema_command(
    subparsers: Any, parent_parser: argparse.ArgumentParser
) -> None:
    """Add the schema subcommand."""
    parser = subparsers.add_parser(
        "schema",
        help="Show inferred schema of tables",
        description="""Infer and display the implicit schema of KenobiX tables.

Analyzes the JSON data stored in tables to determine field names,
types, and presence statistics. By default, analyzes all records.
Use --sample for large tables.

Output shows:
  - Field names (including nested fields with dot notation)
  - Inferred types (string, integer, number, boolean, array, object, null)
  - Presence percentage (how often the field appears)
  - Optional: example values (-v)

Examples:
    # Show schema for all tables
    kenobix schema -d mydb.db

    # Show schema for specific table
    kenobix schema -d mydb.db -t users

    # Sample first 1000 records (for large tables)
    kenobix schema -d mydb.db -t logs --sample 1000

    # Show with example values
    kenobix schema -d mydb.db -v

    # Output as JSON
    kenobix schema -d mydb.db --format json
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )
    parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        help="Show schema for only the specified table",
    )
    parser.add_argument(
        "--sample",
        type=int,
        metavar="N",
        help="Sample N records instead of analyzing all (for large tables)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (default) or json",
    )
    parser.set_defaults(func=cmd_schema)
