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

# Re-export all functions for backward compatibility
from .commands import cmd_dump, cmd_import, cmd_info, cmd_migrate, cmd_serve
from .dump import dump_database, dump_table
from .info import (
    get_indexed_fields,
    get_table_info,
    infer_json_type,
    infer_pseudo_schema,
    merge_types,
    print_column_details,
    print_database_header,
    print_index_details,
    show_basic_table_list,
    show_database_info,
    show_detailed_table_info,
    show_single_table_info,
)
from .parser import create_parser
from .utils import (
    check_database_exists,
    find_database,
    get_all_tables,
    resolve_database,
)

__all__ = [
    "check_database_exists",
    "cmd_dump",
    "cmd_import",
    "cmd_info",
    "cmd_migrate",
    "cmd_serve",
    "create_parser",
    "dump_database",
    "dump_table",
    "find_database",
    "get_all_tables",
    "get_indexed_fields",
    "get_table_info",
    "infer_json_type",
    "infer_pseudo_schema",
    "main",
    "merge_types",
    "print_column_details",
    "print_database_header",
    "print_index_details",
    "resolve_database",
    "show_basic_table_list",
    "show_database_info",
    "show_detailed_table_info",
    "show_single_table_info",
]


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
