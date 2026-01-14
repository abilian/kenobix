"""Serve command functionality.

This module provides functions for starting the Web UI server.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from kenobix import KenobiX

from .utils import check_database_exists, resolve_database


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

    def validate_config(
        db_path: str, ignore_config: bool, config_path: str | None
    ) -> None:
        """Validate config file and print results."""
        try:
            load_config(db_path, ignore_config=ignore_config, config_path=config_path)
            resolved_path = get_config_path()

            if resolved_path:
                print(f"Config file: {resolved_path}")
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

    db_path = resolve_database(args)
    check_database_exists(db_path)

    ignore_config = getattr(args, "no_config", False)
    validate_only = getattr(args, "validate_config", False)
    explicit_config_path = getattr(args, "config", None)

    if validate_only:
        validate_config(db_path, ignore_config, explicit_config_path)
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
            config_path=explicit_config_path,
        )
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)


def add_serve_command(subparsers: Any, parent_parser: argparse.ArgumentParser) -> None:
    """Add the serve subcommand (Web UI)."""
    parser = subparsers.add_parser(
        "serve",
        help="Start the Web UI server",
        description="""Start a read-only web interface for exploring the database.

Requires optional dependencies: pip install kenobix[webui]

Configuration:
    The Web UI can be customized using a kenobix.toml config file.
    By default, config files are auto-discovered from:
    1. Same directory as the database file
    2. Current working directory

    Use -c/--config (global option) to specify a config file explicitly.

Examples:
    # Start server with auto-detected database
    kenobix serve

    # Specify database file
    kenobix serve -d mydb.db

    # Custom host and port
    kenobix serve -d mydb.db --host 0.0.0.0 --port 8080

    # Don't open browser automatically
    kenobix serve -d mydb.db --no-browser

    # Use explicit config file (global option before command)
    kenobix -c /path/to/config.toml serve -d mydb.db

    # Validate config file without starting server
    kenobix serve -d mydb.db --validate-config

    # Ignore config file (use defaults)
    kenobix serve -d mydb.db --no-config
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number (default: 8000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore kenobix.toml configuration file",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate config file and exit (don't start server)",
    )
    parser.set_defaults(func=cmd_serve)
