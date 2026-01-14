"""Export command functionality.

This module provides functions for exporting database contents
to various formats (JSON, CSV, SQL).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import warnings
from pathlib import Path
from typing import Any

from .utils import check_database_exists, get_all_tables, resolve_database

# Supported export formats
FORMATS = ("json", "csv", "sql", "flat-sql")


def get_table_records(db_path: str, table_name: str) -> list[dict[str, Any]]:
    """
    Get all records from a table.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table to read

    Returns:
        List of records with their data
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(f"SELECT id, data FROM {table_name}")

    records = []
    for row in cursor.fetchall():
        record_id, data_json = row
        try:
            data = json.loads(data_json)
            records.append({"_id": record_id, **data})
        except json.JSONDecodeError:
            records.append({"_id": record_id, "_raw_data": data_json})

    conn.close()
    return records


def flatten_value(value: Any, prefix: str = "") -> dict[str, Any]:
    """
    Flatten a nested value into dot-notation keys.

    Args:
        value: The value to flatten
        prefix: Key prefix for nested values

    Returns:
        Dictionary with flattened keys
    """
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            new_key = f"{prefix}.{k}" if prefix else k
            result.update(flatten_value(v, new_key))
        return result
    if isinstance(value, list):
        # For lists, convert to JSON string
        return {prefix: json.dumps(value, ensure_ascii=False)}
    return {prefix: value}


def flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten a record, converting nested dicts to dot-notation columns.

    Args:
        record: The record to flatten

    Returns:
        Flattened record with dot-notation keys for nested values
    """
    result = {}
    for key, value in record.items():
        if isinstance(value, dict):
            result.update(flatten_value(value, key))
        elif isinstance(value, list):
            result[key] = json.dumps(value, ensure_ascii=False)
        else:
            result[key] = value
    return result


def get_all_columns(records: list[dict[str, Any]]) -> list[str]:
    """
    Get all unique column names from flattened records.

    Args:
        records: List of flattened records

    Returns:
        Sorted list of column names, with _id first
    """
    columns: set[str] = set()
    for record in records:
        columns.update(record.keys())

    # Ensure _id is first
    result = ["_id"] if "_id" in columns else []
    columns.discard("_id")
    result.extend(sorted(columns))
    return result


def export_json(
    db_path: str,
    tables: list[str],
    *,
    compact: bool = False,
) -> str:
    """Export tables to JSON format."""
    database_export: dict[str, Any] = {
        "database": db_path,
        "tables": {},
    }

    for table in tables:
        records = get_table_records(db_path, table)
        database_export["tables"][table] = {
            "count": len(records),
            "records": records,
        }

    if compact:
        return json.dumps(database_export, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(database_export, indent=2, ensure_ascii=False)


def export_csv(
    db_path: str,
    tables: list[str],
) -> str:
    """
    Export tables to CSV format.

    For multiple tables, exports only the first table with a warning.
    Nested values are flattened using dot notation.
    """
    if len(tables) > 1:
        print(
            f"Warning: CSV format only supports single table export. "
            f"Exporting '{tables[0]}' only.",
            file=sys.stderr,
        )
        tables = tables[:1]

    table = tables[0]
    records = get_table_records(db_path, table)

    if not records:
        return ""

    # Flatten all records
    flat_records = [flatten_record(r) for r in records]
    columns = get_all_columns(flat_records)

    # Write CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in flat_records:
        writer.writerow(record)

    return output.getvalue()


def escape_sql_value(value: Any) -> str:
    """Escape a value for SQL insertion."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    # Escape single quotes
    return "'" + str(value).replace("'", "''") + "'"


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
            field_name = index_name[len(prefix):]
            indexed.append(field_name)

    conn.close()
    return sorted(indexed)


def generate_create_table_sql(table_name: str, indexed_fields: list[str]) -> list[str]:
    """
    Generate CREATE TABLE and CREATE INDEX statements for a KenobiX table.

    Args:
        table_name: Name of the table
        indexed_fields: List of fields that have indexes

    Returns:
        List of SQL statements
    """
    lines: list[str] = []

    # Build column definitions
    columns = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "data TEXT NOT NULL",
    ]

    # Add generated virtual columns for indexed fields
    columns.extend(
        f"{field} TEXT GENERATED ALWAYS AS (json_extract(data, '$.{field}')) VIRTUAL"
        for field in indexed_fields
    )

    # CREATE TABLE statement
    columns_sql = ",\n    ".join(columns)
    lines.extend((
        f"CREATE TABLE IF NOT EXISTS {table_name} (",
        f"    {columns_sql}",
        ");",
        "",
    ))

    # CREATE INDEX statements for each indexed field
    lines.extend(
        f"CREATE INDEX IF NOT EXISTS {table_name}_idx_{field} ON {table_name}({field});"
        for field in indexed_fields
    )

    if indexed_fields:
        lines.append("")

    return lines


def export_sql(
    db_path: str,
    tables: list[str],
    *,
    dialect: str = "sqlite",
) -> str:
    """
    Export tables to SQL statements (DDL + INSERT).

    Args:
        db_path: Path to the database
        tables: List of tables to export
        dialect: SQL dialect (currently only 'sqlite' supported)

    Returns:
        SQL statements as string
    """
    lines = [
        f"-- Exported from: {db_path}",
        f"-- Dialect: {dialect}",
        "",
    ]

    for table in tables:
        indexed_fields = get_indexed_fields(db_path, table)
        records = get_table_records(db_path, table)

        # Generate DDL (CREATE TABLE + indexes)
        lines.append(f"-- Table: {table}")
        lines.extend(generate_create_table_sql(table, indexed_fields))

        if not records:
            lines.extend(("-- (empty table)", ""))
            continue

        # Generate INSERT statements
        lines.append(f"-- Data: {len(records)} records")
        for record in records:
            # Store as JSON in data column (KenobiX format)
            record_id = record.pop("_id")
            data_json = json.dumps(record, ensure_ascii=False)

            lines.append(
                f"INSERT INTO {table} (id, data) VALUES "
                f"({record_id}, {escape_sql_value(data_json)});"
            )

        lines.append("")

    return "\n".join(lines)


def infer_sql_type(value: Any) -> str:
    """Infer SQL column type from a Python value."""
    if value is None:
        return "TEXT"  # Default for NULL
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def infer_column_types(
    records: list[dict[str, Any]], columns: list[str]
) -> dict[str, str]:
    """
    Infer SQL types for each column from sample records.

    Args:
        records: Flattened records
        columns: Column names

    Returns:
        Dictionary mapping column names to SQL types
    """
    types: dict[str, str] = {}
    for col in columns:
        # Sample non-null values to infer type
        for record in records:
            value = record.get(col)
            if value is not None:
                types[col] = infer_sql_type(value)
                break
        else:
            types[col] = "TEXT"  # Default if all nulls
    return types


def escape_sql_identifier(name: str) -> str:
    """Escape a SQL identifier (column/table name)."""
    # Replace dots with underscores for flattened column names
    safe_name = name.replace(".", "_").replace("-", "_")
    # Quote if it contains special chars or is a reserved word
    if not safe_name.isidentifier() or safe_name.upper() in {"ORDER", "GROUP", "SELECT", "FROM", "WHERE", "INDEX", "TABLE"}:
        return f'"{safe_name}"'
    return safe_name


def export_flat_sql(
    db_path: str,
    tables: list[str],
    *,
    dialect: str = "sqlite",
) -> str:
    """
    Export tables to flat SQL (denormalized, like CSV but as SQL).

    Nested JSON values are flattened to dot-notation columns.
    Each table becomes a regular SQL table with typed columns.

    Args:
        db_path: Path to the database
        tables: List of tables to export
        dialect: SQL dialect (currently only 'sqlite' supported)

    Returns:
        SQL statements as string
    """
    lines = [
        f"-- Exported from: {db_path}",
        f"-- Dialect: {dialect}",
        "-- Format: flat (denormalized)",
        "",
    ]

    for table in tables:
        records = get_table_records(db_path, table)

        if not records:
            lines.extend((f"-- Table '{table}' is empty", ""))
            continue

        # Flatten all records
        flat_records = [flatten_record(r) for r in records]
        columns = get_all_columns(flat_records)
        col_types = infer_column_types(flat_records, columns)

        # Generate CREATE TABLE
        lines.append(f"-- Table: {table}")
        col_defs: list[str] = []
        for col in columns:
            safe_col = escape_sql_identifier(col)
            sql_type = col_types[col]
            if col == "_id":
                col_defs.append(f"{safe_col} INTEGER PRIMARY KEY")
            else:
                col_defs.append(f"{safe_col} {sql_type}")

        lines.extend((
            f"CREATE TABLE IF NOT EXISTS {table} (",
            "    " + ",\n    ".join(col_defs),
            ");",
            "",
            f"-- Data: {len(flat_records)} records",
        ))
        safe_columns = [escape_sql_identifier(c) for c in columns]
        columns_str = ", ".join(safe_columns)

        for record in flat_records:
            values: list[str] = []
            for col in columns:
                value = record.get(col)
                values.append(escape_sql_value(value))
            values_str = ", ".join(values)
            lines.append(f"INSERT INTO {table} ({columns_str}) VALUES ({values_str});")

        lines.append("")

    return "\n".join(lines)


def _get_exporter(format: str) -> Any:
    """Get the export function for a format."""
    exporters = {
        "json": export_json,
        "csv": export_csv,
        "sql": export_sql,
        "flat-sql": export_flat_sql,
    }
    return exporters.get(format)


def export_database(
    db_path: str,
    output_file: str | None = None,
    table_name: str | None = None,
    *,
    format: str = "json",
    compact: bool = False,
    quiet: bool = False,
) -> None:
    """
    Export database contents in the specified format.

    Args:
        db_path: Path to the SQLite database
        output_file: Optional output file path (prints to stdout if None)
        table_name: Optional table name to export only one table
        format: Export format (json, csv, sql, flat-sql)
        compact: If True and format is json, output compact JSON
        quiet: If True, suppress status messages
    """
    check_database_exists(db_path)

    all_tables = get_all_tables(db_path)

    if not all_tables:
        print(f"No tables found in database: {db_path}", file=sys.stderr)
        sys.exit(0)

    # Filter to specific table if requested
    if table_name:
        if table_name not in all_tables:
            print(f"Error: Table '{table_name}' not found in database", file=sys.stderr)
            print(f"Available tables: {', '.join(all_tables)}", file=sys.stderr)
            sys.exit(1)
        tables = [table_name]
    else:
        tables = all_tables

    # CSV requires single table
    if format == "csv" and not table_name and len(tables) > 1:
        print(
            "Error: CSV format requires specifying a single table with -t/--table",
            file=sys.stderr,
        )
        sys.exit(1)

    # Export in requested format
    exporter = _get_exporter(format)
    if not exporter:
        print(f"Error: Unknown format '{format}'", file=sys.stderr)
        sys.exit(1)

    if format == "json":
        output = exporter(db_path, tables, compact=compact)
    else:
        output = exporter(db_path, tables)

    # Output to file or stdout
    if output_file:
        Path(output_file).write_text(output, encoding="utf-8")
        if not quiet:
            print(f"Database exported to: {output_file}", file=sys.stderr)
    else:
        print(output)


def cmd_export(args: argparse.Namespace) -> None:
    """Handle the export command."""
    db_path = resolve_database(args)
    export_database(
        db_path,
        args.output,
        args.table,
        format=getattr(args, "format", "json"),
        compact=getattr(args, "compact", False),
        quiet=getattr(args, "quiet", False),
    )


def cmd_dump(args: argparse.Namespace) -> None:
    """Handle the dump command (deprecated, use export)."""
    warnings.warn(
        "The 'dump' command is deprecated. Use 'export' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # For backward compatibility, dump always uses JSON format
    db_path = resolve_database(args)
    export_database(
        db_path,
        args.output,
        args.table,
        format="json",
        compact=getattr(args, "compact", False),
        quiet=getattr(args, "quiet", False),
    )


def add_export_command(
    subparsers: Any, parent_parser: argparse.ArgumentParser
) -> None:
    """Add the export subcommand."""
    parser = subparsers.add_parser(
        "export",
        help="Export database contents (JSON, CSV, or SQL)",
        description="""Export tables and records from a KenobiX database.

Supported formats:
  json      Human-readable JSON (default)
  csv       Comma-separated values (single table only)
  sql       SQL statements (KenobiX format with JSON data column)
  flat-sql  SQL statements with flattened columns (denormalized)

The 'sql' format preserves the KenobiX schema (id + JSON data column).
The 'flat-sql' format denormalizes JSON into typed columns (like CSV).

Examples:
    # Export entire database as JSON
    kenobix export -d mydb.db

    # Export single table as CSV
    kenobix export -d mydb.db -t users --format csv

    # Export as SQL statements (KenobiX format)
    kenobix export -d mydb.db --format sql -o backup.sql

    # Export as flat SQL (denormalized)
    kenobix export -d mydb.db -t users --format flat-sql
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        help="Export only the specified table",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=FORMATS,
        default="json",
        help="Output format: json (default), csv, sql, flat-sql",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation, json format only)",
    )
    parser.set_defaults(func=cmd_export, compact=False, format="json")


def add_dump_command(
    subparsers: Any, parent_parser: argparse.ArgumentParser
) -> None:
    """Add the dump subcommand (deprecated alias for export)."""
    parser = subparsers.add_parser(
        "dump",
        help="[Deprecated] Use 'export' instead",
        description="Deprecated: Use 'kenobix export' instead. This command will be removed in a future version.",
        parents=[parent_parser],
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        help="Dump only the specified table",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation)",
    )
    parser.set_defaults(func=cmd_dump, compact=False)


# Backward compatibility aliases
dump_table = get_table_records
dump_database = export_database
