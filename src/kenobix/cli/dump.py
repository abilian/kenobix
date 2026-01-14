"""Dump command functionality.

This module provides functions for dumping database contents
to JSON format.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .utils import check_database_exists, get_all_tables, resolve_database

if TYPE_CHECKING:
    pass


def dump_table(db_path: str, table_name: str) -> list[dict[str, Any]]:
    """
    Dump all records from a table.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table to dump

    Returns:
        List of records with their data
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all rows from the table
    cursor.execute(f"SELECT id, data FROM {table_name}")

    records = []
    for row in cursor.fetchall():
        record_id, data_json = row
        try:
            data = json.loads(data_json)
            records.append({"_id": record_id, **data})
        except json.JSONDecodeError:
            # If data is not valid JSON, include raw data
            records.append({"_id": record_id, "_raw_data": data_json})

    conn.close()
    return records


def dump_database(
    db_path: str,
    output_file: str | None = None,
    table_name: str | None = None,
    *,
    compact: bool = False,
    quiet: bool = False,
) -> None:
    """
    Dump database contents in human-readable JSON format.

    Args:
        db_path: Path to the SQLite database
        output_file: Optional output file path (prints to stdout if None)
        table_name: Optional table name to dump only one table
        compact: If True, output compact JSON without indentation
        quiet: If True, suppress status messages
    """
    check_database_exists(db_path)

    # Get all tables or validate specified table
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
        tables_to_dump = [table_name]
    else:
        tables_to_dump = all_tables

    # Dump selected tables
    database_dump: dict[str, Any] = {
        "database": db_path,
        "tables": {},
    }

    for table in tables_to_dump:
        records = dump_table(db_path, table)
        database_dump["tables"][table] = {
            "count": len(records),
            "records": records,
        }

    # Format as JSON
    if compact:
        json_output = json.dumps(
            database_dump, ensure_ascii=False, separators=(",", ":")
        )
    else:
        json_output = json.dumps(database_dump, indent=2, ensure_ascii=False)

    # Output to file or stdout
    if output_file:
        Path(output_file).write_text(json_output, encoding="utf-8")
        if not quiet:
            print(f"Database dumped to: {output_file}", file=sys.stderr)
    else:
        print(json_output)


def cmd_dump(args: argparse.Namespace) -> None:
    """Handle the dump command."""
    db_path = resolve_database(args)
    dump_database(
        db_path,
        args.output,
        args.table,
        compact=getattr(args, "compact", False),
        quiet=getattr(args, "quiet", False),
    )


def add_dump_command(
    subparsers: Any, parent_parser: argparse.ArgumentParser
) -> None:
    """Add the dump subcommand."""
    parser = subparsers.add_parser(
        "dump",
        help="Dump database contents in JSON format",
        description="Dump all tables and records from a KenobiX database in human-readable JSON format.",
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
