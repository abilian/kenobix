"""Table schema inference for KenobiX Web UI.

This module provides functions for inferring table columns from documents
and formatting cell values for display.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import CollectionConfig, format_column_name
from .formatters import format_value


@dataclass
class TableColumn:
    """Represents a column in the document table."""

    name: str
    display_name: str
    is_indexed: bool = False


def _collect_field_stats(documents: list[dict]) -> dict[str, dict[str, int]]:
    """Collect statistics about fields across documents."""
    field_stats: dict[str, dict[str, int]] = {}

    for doc in documents:
        for key, value in doc.items():
            if key == "_id":
                continue

            if key not in field_stats:
                field_stats[key] = {"count": 0, "simple_count": 0}

            field_stats[key]["count"] += 1
            if _is_simple_value(value):
                field_stats[key]["simple_count"] += 1

    return field_stats


def _score_field(
    field: str, stats: dict[str, int], doc_count: int
) -> tuple[float, int, str]:
    """Score a field for column priority (higher score = lower priority for sorting)."""
    presence = stats["count"] / doc_count
    simple_ratio = stats["simple_count"] / stats["count"] if stats["count"] else 0
    score = presence * 0.4 + simple_ratio * 0.6
    return (-score, -stats["count"], field)


def _is_simple_value(value: Any) -> bool:
    """Check if a value is simple enough to display in a table cell."""
    if value is None:
        return True
    if isinstance(value, bool | int | float):
        return True
    if isinstance(value, str):
        return len(value) <= 100  # Short strings are simple
    return False  # Objects, arrays, long strings are complex


def _format_column_name(field: str) -> str:
    """Format a field name for display as column header."""
    # Convert snake_case or camelCase to Title Case
    # user_id -> User Id, userId -> User Id
    # Insert space before caps in camelCase
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", field)
    # Replace underscores with spaces
    name = name.replace("_", " ")
    # Title case
    return name.title()


def infer_table_schema(
    documents: list[dict],
    indexed_fields: list[str],
    collection_name: str | None = None,
    max_columns: int | None = None,
    config: Any = None,
) -> list[TableColumn]:
    """
    Infer table columns from documents using heuristics.

    If a collection config exists with explicit columns, use those.
    Otherwise, use heuristics:
    1. Always include _id as first column
    2. Prioritize indexed fields (they're likely important)
    3. Then add most common fields across documents
    4. Prefer simple types (string, number, bool) over complex (object, array)
    5. Limit total columns to max_columns

    Args:
        documents: List of document dicts to analyze
        indexed_fields: List of indexed field names
        collection_name: Optional collection name to look up config
        max_columns: Max columns (defaults to config or 6)
        config: WebUIConfig instance (if None, uses default from state)
    """
    # Get config from state if not provided
    if config is None:
        from .state import get_config  # noqa: PLC0415

        config = get_config()

    # Get collection config if name provided
    coll_config: CollectionConfig | None = None
    if collection_name:
        coll_config = config.get_collection(collection_name)

    # Check if collection has explicit columns configured
    if coll_config and coll_config.columns:
        return [
            TableColumn(
                name=col_name,
                display_name=coll_config.get_label(col_name),
                is_indexed=col_name in indexed_fields,
            )
            for col_name in coll_config.columns
        ]

    # Use auto-inference
    effective_max = max_columns or config.max_columns

    if not documents:
        return [TableColumn("_id", "ID")]

    field_stats = _collect_field_stats(documents)
    columns = [TableColumn("_id", "ID")]

    # Add indexed fields first
    for fld in indexed_fields:
        if fld in field_stats and len(columns) < effective_max:
            label = coll_config.get_label(fld) if coll_config else format_column_name(fld)
            columns.append(TableColumn(fld, label, is_indexed=True))

    # Score and sort remaining fields
    remaining = [f for f in field_stats if f not in indexed_fields]
    remaining.sort(key=lambda f: _score_field(f, field_stats[f], len(documents)))

    # Add top remaining fields
    for fld in remaining:
        if len(columns) >= effective_max:
            break
        label = coll_config.get_label(fld) if coll_config else format_column_name(fld)
        columns.append(TableColumn(fld, label))

    return columns


def format_cell_value(
    value: Any,
    max_length: int = 50,
    formatter: str = "auto",
    column_name: str | None = None,
    collection_name: str | None = None,
    config: Any = None,
) -> dict[str, Any]:
    """
    Format a value for display in a table cell.

    Args:
        value: The value to format
        max_length: Maximum display length for strings
        formatter: Formatter name (e.g., "auto", "currency:USD", "badge")
        column_name: Optional column name for config lookup
        collection_name: Optional collection name for config lookup
        config: WebUIConfig instance (if None, uses default from state)

    Returns:
        Dict with 'display' (string to show), 'type' (css class), 'full' (full value if truncated)
    """
    # Get config from state if not provided
    if config is None:
        from .state import get_config  # noqa: PLC0415

        config = get_config()

    # If column and collection provided, look up configured formatter
    if column_name and collection_name and formatter == "auto":
        coll_config = config.get_collection(collection_name)
        formatter = coll_config.get_formatter(column_name)

    # Use the formatters module
    return format_value(value, formatter, config, max_length)
