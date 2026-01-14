"""Command handlers for CLI subcommands.

This module provides the handler functions for each CLI command:
dump, info, migrate, serve, and import.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .dump import dump_database
from .info import show_database_info
from .utils import check_database_exists, resolve_database

if TYPE_CHECKING:
    import argparse


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
        print("\nFor PostgreSQL support, install: uv add kenobix[postgres]", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_serve(args: argparse.Namespace) -> None:
    """Handle the serve command."""
    try:
        from ..webui import run_server  # noqa: PLC0415
        from ..webui.config import (  # noqa: PLC0415
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
