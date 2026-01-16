"""Dump command functionality.

This module provides human-readable data inspection with filtering.
Unlike 'export' (for data transfer), 'dump' is optimized for terminal viewing.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from typing import Any

from .utils import check_database_exists, get_all_tables, resolve_database

# ANSI color codes
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "key": "\033[94m",  # Blue
    "string": "\033[92m",  # Green
    "number": "\033[93m",  # Yellow
    "boolean": "\033[95m",  # Magenta
    "null": "\033[91m",  # Red
    "separator": "\033[90m",  # Gray
}


@dataclass
class Selector:
    """A parsed selector condition."""

    field: str
    operator: str  # =, !=, >, >=, <, <=, ~
    value: Any
    is_null_check: bool = False


def parse_selector(selector_str: str) -> Selector:
    """Parse a selector string into a Selector object.

    Supported formats:
        field=value     Equals
        field!=value    Not equals
        field>value     Greater than
        field>=value    Greater or equal
        field<value     Less than
        field<=value    Less or equal
        field~pattern   LIKE pattern
        field=null      IS NULL
        field!=null     IS NOT NULL
        field=true      Boolean true
        field=false     Boolean false

    Args:
        selector_str: The selector string to parse

    Returns:
        Selector object

    Raises:
        ValueError: If selector format is invalid
    """
    # Match operators in order of specificity (longer first)
    pattern = r"^([a-zA-Z_][a-zA-Z0-9_.]*)([!><=~]+)(.*)$"
    match = re.match(pattern, selector_str)

    if not match:
        msg = f"Invalid selector format: {selector_str}"
        raise ValueError(msg)

    field = match.group(1)
    op = match.group(2)
    value_str = match.group(3)

    # Validate operator
    valid_ops = ("=", "!=", ">", ">=", "<", "<=", "~")
    if op not in valid_ops:
        msg = f"Invalid operator '{op}' in selector: {selector_str}"
        raise ValueError(msg)

    # Handle special values
    if value_str.lower() == "null":
        return Selector(field=field, operator=op, value=None, is_null_check=True)

    if value_str.lower() == "true":
        return Selector(field=field, operator=op, value=True)

    if value_str.lower() == "false":
        return Selector(field=field, operator=op, value=False)

    # Try to parse as number
    value: str | int | float
    try:
        if "." in value_str:
            value = float(value_str)
        else:
            value = int(value_str)
    except ValueError:
        value = value_str

    return Selector(field=field, operator=op, value=value)


def selector_to_sql(selector: Selector) -> tuple[str, list[Any]]:
    """Convert a Selector to SQL WHERE clause fragment.

    Args:
        selector: The Selector to convert

    Returns:
        Tuple of (SQL fragment, list of parameters)
    """
    # Convert field name to JSON path (support nested fields)
    json_path = "$." + selector.field

    # Handle null checks
    if selector.is_null_check:
        if selector.operator == "=":
            return f"json_extract(data, ?) IS NULL", [json_path]
        else:  # !=
            return f"json_extract(data, ?) IS NOT NULL", [json_path]

    # Handle boolean values
    if isinstance(selector.value, bool):
        sql_value = 1 if selector.value else 0
        sql_op = "=" if selector.operator == "=" else "!="
        return f"json_extract(data, ?) {sql_op} ?", [json_path, sql_value]

    # Handle LIKE operator
    if selector.operator == "~":
        return f"json_extract(data, ?) LIKE ?", [json_path, selector.value]

    # Handle comparison operators
    op_map = {
        "=": "=",
        "!=": "!=",
        ">": ">",
        ">=": ">=",
        "<": "<",
        "<=": "<=",
    }
    sql_op = op_map[selector.operator]

    return f"json_extract(data, ?) {sql_op} ?", [json_path, selector.value]


def build_query(
    table_name: str,
    selectors: list[Selector],
    limit: int | None = None,
    offset: int | None = None,
    count_only: bool = False,
) -> tuple[str, list[Any]]:
    """Build a SQL query from selectors.

    Args:
        table_name: Name of the table
        selectors: List of Selector objects
        limit: Maximum records to return
        offset: Number of records to skip
        count_only: If True, return COUNT(*) query

    Returns:
        Tuple of (SQL query, list of parameters)
    """
    params: list[Any] = []

    if count_only:
        sql = f"SELECT COUNT(*) FROM {table_name}"
    else:
        sql = f"SELECT id, data FROM {table_name}"

    # Build WHERE clause
    if selectors:
        where_parts: list[str] = []
        for selector in selectors:
            fragment, selector_params = selector_to_sql(selector)
            where_parts.append(fragment)
            params.extend(selector_params)
        sql += " WHERE " + " AND ".join(where_parts)

    # Add LIMIT and OFFSET
    if not count_only:
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"

    return sql, params


def colorize_json(obj: Any, use_color: bool = True) -> str:
    """Pretty-print JSON with optional syntax highlighting.

    Args:
        obj: Object to format
        use_color: Whether to apply colors

    Returns:
        Formatted string
    """
    if not use_color:
        return json.dumps(obj, indent=2, ensure_ascii=False)

    def colorize_value(v: Any, indent: int = 0) -> str:
        prefix = "  " * indent
        c = COLORS

        if v is None:
            return f"{c['null']}null{c['reset']}"
        if isinstance(v, bool):
            return f"{c['boolean']}{str(v).lower()}{c['reset']}"
        if isinstance(v, int | float):
            return f"{c['number']}{v}{c['reset']}"
        if isinstance(v, str):
            escaped = json.dumps(v)
            return f"{c['string']}{escaped}{c['reset']}"
        if isinstance(v, list):
            if not v:
                return "[]"
            items = [colorize_value(item, indent + 1) for item in v]
            inner = ",\n".join(f"{prefix}  {item}" for item in items)
            return f"[\n{inner}\n{prefix}]"
        if isinstance(v, dict):
            if not v:
                return "{}"
            pairs: list[str] = []
            for key, val in v.items():
                colored_key = f"{c['key']}\"{key}\"{c['reset']}"
                colored_val = colorize_value(val, indent + 1)
                pairs.append(f"{prefix}  {colored_key}: {colored_val}")
            inner = ",\n".join(pairs)
            return f"{{\n{inner}\n{prefix}}}"
        return str(v)

    return colorize_value(obj)


def truncate_value(value: str, max_len: int = 50) -> str:
    """Truncate a string value for display."""
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def format_table(
    records: list[dict[str, Any]],
    use_color: bool = True,
    truncate: bool = True,
) -> str:
    """Format records as a table.

    Args:
        records: List of record dictionaries
        use_color: Whether to apply colors
        truncate: Whether to truncate long values

    Returns:
        Formatted table string
    """
    if not records:
        return "(no records)"

    # Collect all columns
    columns: set[str] = set()
    for record in records:
        columns.update(record.keys())

    # Sort columns with _id first
    sorted_cols = sorted(columns - {"_id"})
    if "_id" in columns:
        sorted_cols = ["_id"] + sorted_cols

    # Calculate column widths
    col_widths: dict[str, int] = {}
    for col in sorted_cols:
        max_width = len(col)
        for record in records:
            val = record.get(col, "")
            val_str = _value_to_str(val)
            if truncate:
                val_str = truncate_value(val_str)
            max_width = max(max_width, len(val_str))
        col_widths[col] = min(max_width, 50)  # Cap at 50

    # Get terminal width
    term_width = shutil.get_terminal_size().columns

    # Build header
    c = COLORS if use_color else {k: "" for k in COLORS}
    lines: list[str] = []

    header = "  ".join(f"{c['bold']}{col:<{col_widths[col]}}{c['reset']}" for col in sorted_cols)
    lines.append(header)

    # Separator
    sep = "  ".join("─" * col_widths[col] for col in sorted_cols)
    lines.append(f"{c['dim']}{sep}{c['reset']}")

    # Rows
    for record in records:
        cells: list[str] = []
        for col in sorted_cols:
            val = record.get(col, "")
            val_str = _value_to_str(val)
            if truncate:
                val_str = truncate_value(val_str, col_widths[col])
            cells.append(f"{val_str:<{col_widths[col]}}")
        lines.append("  ".join(cells))

    return "\n".join(lines)


def _value_to_str(value: Any) -> str:
    """Convert a value to string for table display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_compact(records: list[dict[str, Any]]) -> str:
    """Format records as one JSON object per line.

    Args:
        records: List of record dictionaries

    Returns:
        Newline-separated JSON strings
    """
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)


def dump_table(
    db_path: str,
    table_name: str,
    selectors: list[str] | None = None,
    limit: int = 20,
    offset: int | None = None,
    one: bool = False,
    count_only: bool = False,
    output_format: str = "json",
    use_color: bool = True,
    truncate: bool = True,
) -> None:
    """Dump records from a table with optional filtering.

    Args:
        db_path: Path to database
        table_name: Table to query
        selectors: List of selector strings
        limit: Max records to return
        offset: Records to skip
        one: Show only first record
        count_only: Only show count
        output_format: json, table, or compact
        use_color: Use ANSI colors
        truncate: Truncate long values
    """
    check_database_exists(db_path)

    # Verify table exists
    all_tables = get_all_tables(db_path)
    if table_name not in all_tables:
        print(f"Error: Table '{table_name}' not found", file=sys.stderr)
        print(f"Available tables: {', '.join(all_tables)}", file=sys.stderr)
        sys.exit(1)

    # Parse selectors
    parsed_selectors: list[Selector] = []
    if selectors:
        for s in selectors:
            try:
                parsed_selectors.append(parse_selector(s))
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

    # Handle --one flag
    if one:
        limit = 1

    # Build and execute query
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if count_only:
        query, params = build_query(table_name, parsed_selectors, count_only=True)
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()
        print(f"{count} records")
        return

    query, params = build_query(table_name, parsed_selectors, limit, offset)
    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Also get total count for header
    count_query, count_params = build_query(table_name, parsed_selectors, count_only=True)
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]
    conn.close()

    if not rows:
        print("(no matching records)")
        return

    # Parse records
    records: list[dict[str, Any]] = []
    for row_id, data_json in rows:
        try:
            data = json.loads(data_json)
            data["_id"] = row_id
            records.append(data)
        except json.JSONDecodeError:
            records.append({"_id": row_id, "_raw": data_json})

    # Output header
    c = COLORS if use_color else {k: "" for k in COLORS}
    shown = len(records)
    if output_format == "json":
        print(f"{c['dim']}[{shown}/{total_count} records]{c['reset']}")
        print()

    # Format output
    if output_format == "json":
        for i, record in enumerate(records):
            if i > 0:
                print(f"{c['separator']}---{c['reset']}")
            print(colorize_json(record, use_color))
    elif output_format == "table":
        print(f"{c['dim']}[{shown}/{total_count} records]{c['reset']}")
        print()
        print(format_table(records, use_color, truncate))
    elif output_format == "compact":
        print(format_compact(records))
    else:
        print(f"Error: Unknown format '{output_format}'", file=sys.stderr)
        sys.exit(1)


def cmd_dump(args: argparse.Namespace) -> None:
    """Handle the dump command."""
    db_path = resolve_database(args)

    # Check if table is specified
    table_name: str | None = getattr(args, "table", None)
    if not table_name:
        print("Error: Table name required. Use -t TABLE", file=sys.stderr)
        sys.exit(1)

    # Detect if stdout is a TTY for color default
    use_color = sys.stdout.isatty() and not getattr(args, "no_color", False)

    # table_name is guaranteed to be str after the check above
    dump_table(
        db_path,
        str(table_name),
        selectors=getattr(args, "selectors", None),
        limit=getattr(args, "limit", 20),
        offset=getattr(args, "offset", None),
        one=getattr(args, "one", False),
        count_only=getattr(args, "count", False),
        output_format=getattr(args, "format", "json"),
        use_color=use_color,
        truncate=not getattr(args, "no_truncate", False),
    )


def add_dump_command(
    subparsers: Any, parent_parser: argparse.ArgumentParser
) -> None:
    """Add the dump subcommand."""
    parser = subparsers.add_parser(
        "dump",
        help="Inspect table data (human-readable)",
        description="""Inspect and filter table data for human consumption.

Unlike 'export' (for data transfer), 'dump' is optimized for terminal
viewing with filtering, pagination, and colored output.

Selector syntax:
  field=value      Equals
  field!=value     Not equals
  field>value      Greater than
  field>=value     Greater or equal
  field<value      Less than
  field<=value     Less or equal
  field~pattern    LIKE pattern (use % as wildcard)
  field=null       IS NULL
  field!=null      IS NOT NULL
  field=true       Boolean true
  field=false      Boolean false

Nested fields use dot notation: address.city=Paris

Examples:
    # Show first 20 users
    kenobix dump -d mydb.db -t users

    # Filter by field
    kenobix dump -d mydb.db -t users name=John

    # Multiple conditions (AND)
    kenobix dump -d mydb.db -t users active=true age>25

    # Nested field filter
    kenobix dump -d mydb.db -t users address.city=Paris

    # Pattern matching
    kenobix dump -d mydb.db -t users email~%@gmail.com

    # Count matching records
    kenobix dump -d mydb.db -t orders status=pending --count

    # Show single record
    kenobix dump -d mydb.db -t users -1

    # Table format
    kenobix dump -d mydb.db -t users -f table

    # Grep-friendly output
    kenobix dump -d mydb.db -t users -f compact | grep admin
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )
    parser.add_argument(
        "-t",
        "--table",
        metavar="TABLE",
        required=True,
        help="Table to query (required)",
    )
    parser.add_argument(
        "selectors",
        nargs="*",
        metavar="SELECTOR",
        help="Filter conditions (e.g., name=John age>25)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="Maximum records to show (default: 20)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        metavar="N",
        help="Skip first N records",
    )
    parser.add_argument(
        "-1",
        "--one",
        action="store_true",
        help="Show only first matching record",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Only show count of matching records",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "table", "compact"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Don't truncate long values",
    )
    parser.set_defaults(func=cmd_dump)
