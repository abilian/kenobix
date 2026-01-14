"""Migrate command functionality.

This module provides functions for migrating data between databases.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def cmd_migrate(args: argparse.Namespace) -> None:
    """Handle the migrate command."""
    from ..migrate import migrate, migrate_collection  # noqa: PLC0415

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
        print(
            "\nFor PostgreSQL support, install: uv add kenobix[postgres]",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


def add_migrate_command(subparsers: Any) -> None:
    """Add the migrate subcommand."""
    parser = subparsers.add_parser(
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
    parser.add_argument(
        "source",
        help="Source database (file path or postgresql:// URL)",
    )
    parser.add_argument(
        "dest",
        help="Destination database (file path or postgresql:// URL)",
    )
    parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        help="Migrate only the specified table/collection",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        metavar="N",
        help="Documents per batch (default: 1000)",
    )
    parser.set_defaults(func=cmd_migrate)
