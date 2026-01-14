"""Argument parser creation for CLI.

This module provides the argument parser configuration for all
CLI commands and options.
"""

from __future__ import annotations

import argparse

from .dump import add_dump_command
from .import_cmd import add_import_command
from .info import add_info_command
from .migrate import add_migrate_command
from .serve import add_serve_command


def _create_parent_parser() -> argparse.ArgumentParser:
    """Create parent parser with shared options inherited by subcommands."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "-d",
        "--database",
        metavar="DATABASE",
        default=argparse.SUPPRESS,
        help="Path to database file (env: KENOBIX_DATABASE)",
    )
    parent.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=argparse.SUPPRESS,
        help="Increase verbosity (repeatable: -v, -vv)",
    )
    parent.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress non-essential output",
    )
    parent.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        default=argparse.SUPPRESS,
        help="Path to config file (overrides auto-discovery)",
    )
    return parent


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parent_parser = _create_parent_parser()

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
  kenobix -c config.toml serve         Use explicit config file

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

    add_dump_command(subparsers, parent_parser)
    add_info_command(subparsers, parent_parser)
    add_migrate_command(subparsers)
    add_import_command(subparsers)
    add_serve_command(subparsers, parent_parser)

    return parser
