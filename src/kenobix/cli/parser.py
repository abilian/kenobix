"""Argument parser creation for CLI.

This module provides the argument parser configuration for all
CLI commands and options.
"""

from __future__ import annotations

import argparse

from .commands import cmd_dump, cmd_import, cmd_info, cmd_migrate, cmd_serve


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
