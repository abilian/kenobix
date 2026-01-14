"""
KenobiX Command Line Interface

Commands:
    dump      Dump database contents in human-readable JSON format
    info      Show database information
    migrate   Migrate data between databases (SQLite/PostgreSQL)
    import    Import database from JSON file
    serve     Start Web UI server (requires kenobix[webui])

Examples:
    kenobix dump -d mydb.db
    kenobix -d mydb.db dump
    kenobix dump -d mydb.db -t users -o users.json
    KENOBIX_DATABASE=mydb.db kenobix info -v
    kenobix migrate source.db postgresql://localhost/dest
    kenobix import backup.json newdb.db
    kenobix serve -d mydb.db
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


def find_database() -> str | None:
    """
    Auto-detect database file.

    Resolution order:
    1. KENOBIX_DATABASE environment variable
    2. Single .db file in current directory

    Returns:
        Path to database file, or None if not found
    """
    # Check environment variable
    env_db = os.environ.get("KENOBIX_DATABASE")
    if env_db:
        return env_db

    # Look for single .db file in current directory
    db_files = list(Path.cwd().glob("*.db"))
    if len(db_files) == 1:
        return str(db_files[0])

    return None


def resolve_database(args: argparse.Namespace) -> str:
    """
    Resolve database path from arguments, environment, or auto-detection.

    Args:
        args: Parsed arguments (may have 'database' attribute)

    Returns:
        Path to database file

    Raises:
        SystemExit: If no database can be resolved
    """
    # Check explicit argument (handle both None and missing attribute)
    db_path = getattr(args, "database", None)
    if db_path is not None:
        return db_path

    # Try auto-detection
    db_path = find_database()
    if db_path:
        return db_path

    # No database found - show helpful error
    print("Error: No database specified.", file=sys.stderr)
    print("\nSpecify a database using one of:", file=sys.stderr)
    print("  -d/--database option:  kenobix dump -d mydb.db", file=sys.stderr)
    print(
        "  Environment variable:  KENOBIX_DATABASE=mydb.db kenobix dump",
        file=sys.stderr,
    )
    print(
        "  Auto-detection:        Place a single .db file in current directory",
        file=sys.stderr,
    )
    sys.exit(1)


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


def cmd_info(args: argparse.Namespace) -> None:
    """Handle the info command."""
    db_path = resolve_database(args)
    show_database_info(
        db_path,
        getattr(args, "verbose", 0),
        getattr(args, "table", None),
    )


def cmd_migrate(args: argparse.Namespace) -> None:
    """Handle the migrate command."""
    from .migrate import migrate, migrate_collection  # noqa: PLC0415

    source = args.source
    dest = args.dest
    table = getattr(args, "table", None)
    quiet = getattr(args, "quiet", False)
    batch_size = getattr(args, "batch_size", 1000)

    # Progress callback
    def on_progress(message: str) -> None:
        if not quiet:
            print(message)

    try:
        if table:
            # Migrate single collection
            stats = migrate_collection(
                source,
                dest,
                table,
                on_progress=on_progress,
                batch_size=batch_size,
            )
            if not quiet:
                print("\nMigration complete:")
                print(f"  Collection: {stats['collection']}")
                print(f"  Documents:  {stats['documents']}")
                print(f"  From:       {stats['source_type']}")
                print(f"  To:         {stats['dest_type']}")
        else:
            # Migrate all collections
            stats = migrate(
                source,
                dest,
                on_progress=on_progress,
                batch_size=batch_size,
            )
            if not quiet:
                print("\nMigration complete:")
                print(f"  Collections: {stats['collections']}")
                print(f"  Documents:   {stats['documents']}")
                print(f"  From:        {stats['source_type']}")
                print(f"  To:          {stats['dest_type']}")

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nFor PostgreSQL support, install: uv add kenobix[postgres]", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_serve(args: argparse.Namespace) -> None:
    """Handle the serve command."""
    try:
        from .webui import run_server  # noqa: PLC0415
        from .webui.config import (  # noqa: PLC0415
            ConfigError,
            get_config_path,
            load_config,
            validate_config_against_db,
        )
    except ImportError:
        print("Error: Web UI not installed.", file=sys.stderr)
        print("Install with: pip install kenobix[webui]", file=sys.stderr)
        sys.exit(1)

    db_path = resolve_database(args)
    check_database_exists(db_path)

    ignore_config = getattr(args, "no_config", False)
    validate_only = getattr(args, "validate_config", False)

    # Load and validate config if requested
    if validate_only:
        from kenobix import KenobiX  # noqa: PLC0415

        try:
            load_config(db_path, ignore_config=ignore_config)
            config_path = get_config_path()

            if config_path:
                print(f"Config file: {config_path}")
            else:
                print("Config file: (none, using defaults)")

            # Validate against database
            db = KenobiX(db_path)
            try:
                warnings = validate_config_against_db(db)
                if warnings:
                    print("\nValidation warnings:")
                    for warning in warnings:
                        print(f"  - {warning}")
                else:
                    print("\nValidation: OK")
            finally:
                db.close()

        except ConfigError as e:
            print(f"Config error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Normal serve mode
    try:
        run_server(
            db_path=db_path,
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8000),
            open_browser=not getattr(args, "no_browser", False),
            quiet=getattr(args, "quiet", False),
            ignore_config=ignore_config,
        )
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_import(args: argparse.Namespace) -> None:
    """Handle the import command."""
    from .migrate import import_from_json  # noqa: PLC0415

    json_path = args.input
    dest = args.dest
    quiet = getattr(args, "quiet", False)

    # Check input file exists
    if not Path(json_path).exists():
        print(f"Error: Input file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    # Progress callback
    def on_progress(message: str) -> None:
        if not quiet:
            print(message)

    try:
        stats = import_from_json(
            json_path,
            dest,
            on_progress=on_progress,
        )
        if not quiet:
            print("\nImport complete:")
            print(f"  Collections: {stats['collections']}")
            print(f"  Documents:   {stats['documents']}")

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Import failed: {e}", file=sys.stderr)
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    # Parent parser for shared options (inherited by subcommands)
    # Use SUPPRESS as default so subparser doesn't overwrite main parser values
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "-d",
        "--database",
        metavar="DATABASE",
        default=argparse.SUPPRESS,
        help="Path to database file (env: KENOBIX_DATABASE)",
    )
    parent_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=argparse.SUPPRESS,
        help="Increase verbosity (repeatable: -v, -vv)",
    )
    parent_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress non-essential output",
    )

    # Main parser - set actual defaults here
    parser = argparse.ArgumentParser(
        prog="kenobix",
        description="KenobiX - Simple document database CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
        epilog="""
Examples:
  kenobix dump -d mydb.db              Dump entire database
  kenobix -d mydb.db dump -t users     Dump only users table
  kenobix info -d mydb.db -v           Show detailed database info
  kenobix dump -o backup.json          Dump to file (auto-detect database)
  kenobix serve -d mydb.db             Start web UI (requires kenobix[webui])

Environment:
  KENOBIX_DATABASE    Default database path

Database Resolution:
  1. -d/--database argument
  2. KENOBIX_DATABASE environment variable
  3. Single .db file in current directory
""",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.8.1",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        description="Available commands",
        dest="command",
        metavar="<command>",
    )

    # Dump command
    dump_parser = subparsers.add_parser(
        "dump",
        help="Dump database contents in JSON format",
        description="Dump all tables and records from a KenobiX database in human-readable JSON format.",
        parents=[parent_parser],
    )
    dump_parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output file path (default: stdout)",
    )
    dump_parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        help="Dump only the specified table",
    )
    dump_parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation)",
    )
    dump_parser.set_defaults(func=cmd_dump, compact=False)

    # Info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show database information",
        description="Display information about a KenobiX database including tables, columns, and indexes.",
        parents=[parent_parser],
    )
    info_parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        help="Show info for only the specified table",
    )
    info_parser.set_defaults(func=cmd_info)

    # Migrate command (doesn't use parent_parser for database)
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate data between databases",
        description="""Migrate data between SQLite and PostgreSQL databases.

Examples:
    # SQLite to PostgreSQL
    kenobix migrate mydb.db postgresql://user:pass@localhost/newdb

    # PostgreSQL to SQLite
    kenobix migrate postgresql://user:pass@localhost/db backup.db

    # Migrate single collection
    kenobix migrate mydb.db newdb.db -t users
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    migrate_parser.add_argument(
        "source",
        help="Source database (file path or postgresql:// URL)",
    )
    migrate_parser.add_argument(
        "dest",
        help="Destination database (file path or postgresql:// URL)",
    )
    migrate_parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        help="Migrate only the specified table/collection",
    )
    migrate_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    migrate_parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        metavar="N",
        help="Documents per batch (default: 1000)",
    )
    migrate_parser.set_defaults(func=cmd_migrate)

    # Import command
    import_parser = subparsers.add_parser(
        "import",
        help="Import database from JSON file",
        description="""Import data from a JSON file into a KenobiX database.

The JSON file should have the format:
{
    "collection_name": [
        {"field": "value", ...},
        ...
    ],
    ...
}

Examples:
    # Import to SQLite database
    kenobix import backup.json mydb.db

    # Import to PostgreSQL
    kenobix import backup.json postgresql://user:pass@localhost/db
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    import_parser.add_argument(
        "input",
        metavar="JSON_FILE",
        help="Input JSON file path",
    )
    import_parser.add_argument(
        "dest",
        metavar="DATABASE",
        help="Destination database (file path or postgresql:// URL)",
    )
    import_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    import_parser.set_defaults(func=cmd_import)

    # Serve command (Web UI)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the Web UI server",
        description="""Start a read-only web interface for exploring the database.

Requires optional dependencies: pip install kenobix[webui]

Configuration:
    The Web UI can be customized using a kenobix.toml file placed in:
    1. Same directory as the database file
    2. Current working directory

Examples:
    # Start server with auto-detected database
    kenobix serve

    # Specify database file
    kenobix serve -d mydb.db

    # Custom host and port
    kenobix serve -d mydb.db --host 0.0.0.0 --port 8080

    # Don't open browser automatically
    kenobix serve -d mydb.db --no-browser

    # Validate config file without starting server
    kenobix serve -d mydb.db --validate-config

    # Ignore config file (use defaults)
    kenobix serve -d mydb.db --no-config
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number (default: 8000)",
    )
    serve_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )
    serve_parser.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore kenobix.toml configuration file",
    )
    serve_parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate config file and exit (don't start server)",
    )
    serve_parser.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point.

    Args:
        argv: Command line arguments. If None, uses sys.argv.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Show help if no command provided
    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
