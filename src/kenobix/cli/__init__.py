"""
KenobiX Command Line Interface

Commands:
    dump      Inspect table data (human-readable, with filtering)
    export    Export database contents (JSON, CSV, or SQL)
    schema    Show inferred schema of tables
    info      Show database information
    migrate   Migrate data between databases (SQLite/PostgreSQL)
    import    Import database from JSON file
    serve     Start Web UI server (requires kenobix[webui])

Examples:
    kenobix dump -d mydb.db -t users name=John
    kenobix export -d mydb.db
    kenobix export -d mydb.db -t users -f csv
    kenobix schema -d mydb.db -t users
    KENOBIX_DATABASE=mydb.db kenobix info -v
    kenobix migrate source.db postgresql://localhost/dest
    kenobix import backup.json newdb.db
    kenobix serve -d mydb.db
"""

from __future__ import annotations

# Re-export all functions for backward compatibility
from .dump import add_dump_command, cmd_dump, dump_table
from .export import (
    add_export_command,
    cmd_export,
    export_csv,
    export_database,
    export_flat_sql,
    export_json,
    export_sql,
    get_table_records,
)
from .import_cmd import add_import_command, cmd_import
from .info import (
    add_info_command,
    cmd_info,
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
from .migrate import add_migrate_command, cmd_migrate
from .parser import create_parser
from .schema import add_schema_command, cmd_schema, infer_schema, show_schema
from .serve import add_serve_command, cmd_serve
from .utils import (
    check_database_exists,
    find_database,
    get_all_tables,
    resolve_database,
)

__all__ = [
    "add_dump_command",
    "add_export_command",
    "add_import_command",
    "add_info_command",
    "add_migrate_command",
    "add_schema_command",
    "add_serve_command",
    "check_database_exists",
    "cmd_dump",
    "cmd_export",
    "cmd_import",
    "cmd_info",
    "cmd_migrate",
    "cmd_schema",
    "cmd_serve",
    "create_parser",
    "dump_table",
    "export_csv",
    "export_database",
    "export_flat_sql",
    "export_json",
    "export_sql",
    "find_database",
    "get_all_tables",
    "get_indexed_fields",
    "get_table_info",
    "get_table_records",
    "infer_json_type",
    "infer_pseudo_schema",
    "infer_schema",
    "main",
    "merge_types",
    "print_column_details",
    "print_database_header",
    "print_index_details",
    "resolve_database",
    "show_basic_table_list",
    "show_database_info",
    "show_detailed_table_info",
    "show_schema",
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
