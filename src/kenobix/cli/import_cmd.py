"""Import command functionality.

This module provides functions for importing data from JSON files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def cmd_import(args: argparse.Namespace) -> None:
    """Handle the import command."""
    from ..migrate import import_from_json  # noqa: PLC0415

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


def add_import_command(subparsers: Any) -> None:
    """Add the import subcommand."""
    parser = subparsers.add_parser(
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
    parser.add_argument(
        "input",
        metavar="JSON_FILE",
        help="Input JSON file path",
    )
    parser.add_argument(
        "dest",
        metavar="DATABASE",
        help="Destination database (file path or postgresql:// URL)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.set_defaults(func=cmd_import)
