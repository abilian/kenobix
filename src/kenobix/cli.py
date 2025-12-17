"""
KenobiX Command Line Interface

Commands:
    dump    Dump database contents in human-readable JSON format
    info    Show database information
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def check_database_exists(db_path: str) -> None:
    """Check if database file exists and exit if not."""
    if not Path(db_path).exists():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)


def get_all_tables(db_path: str) -> list[str]:
    """
    Get all table names from the database.

    Args:
        db_path: Path to the SQLite database

    Returns:
        List of table names
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables except SQLite internal tables
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )

    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


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
    db_path: str, output_file: str | None = None, table_name: str | None = None
) -> None:
    """
    Dump database contents in human-readable JSON format.

    Args:
        db_path: Path to the SQLite database
        output_file: Optional output file path (prints to stdout if None)
        table_name: Optional table name to dump only one table
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

    # Format as pretty JSON
    json_output = json.dumps(database_dump, indent=2, ensure_ascii=False)

    # Output to file or stdout
    if output_file:
        Path(output_file).write_text(json_output, encoding="utf-8")
        print(f"Database dumped to: {output_file}")
    else:
        print(json_output)


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


def show_database_info(db_path: str, verbosity: int = 0) -> None:
    """
    Show database information with varying detail levels.

    Args:
        db_path: Path to the SQLite database
        verbosity: Verbosity level (0=basic, 1=detailed, 2+=very detailed)
    """
    check_database_exists(db_path)

    tables = get_all_tables(db_path)
    if not tables:
        print(f"No tables found in database: {db_path}")
        return

    print_database_header(db_path, tables)

    if verbosity == 0:
        show_basic_table_list(db_path, tables)
    else:
        show_detailed_table_info(db_path, tables, verbosity)


def cmd_dump(args: argparse.Namespace) -> None:
    """Handle the dump command."""
    dump_database(args.database, args.output, args.table)


def cmd_info(args: argparse.Namespace) -> None:
    """Handle the info command."""
    show_database_info(args.database, args.verbose)


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point.

    Args:
        argv: Command line arguments. If None, uses sys.argv.
    """
    parser = argparse.ArgumentParser(
        prog="kenobix",
        description="KenobiX - Simple document database CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.7.2",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        description="Available commands",
        dest="command",
        required=True,
    )

    # Dump command
    dump_parser = subparsers.add_parser(
        "dump",
        help="Dump database contents in JSON format",
        description="Dump all tables and records from a KenobiX database in human-readable JSON format.",
    )
    dump_parser.add_argument(
        "database",
        help="Path to the SQLite database file",
    )
    dump_parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: print to stdout)",
        default=None,
    )
    dump_parser.add_argument(
        "-t",
        "--table",
        help="Dump only the specified table",
        default=None,
    )
    dump_parser.set_defaults(func=cmd_dump)

    # Info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show database information",
        description="Display information about a KenobiX database including tables, columns, and indexes.",
    )
    info_parser.add_argument(
        "database",
        help="Path to the SQLite database file",
    )
    info_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for detailed, -vv for very detailed)",
    )
    info_parser.set_defaults(func=cmd_info)

    # Parse arguments and run command
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
