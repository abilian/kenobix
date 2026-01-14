"""
KenobiX Web UI - Bottle Application and Routes.

Read-only web interface for exploring KenobiX databases.

This module serves as the main entry point, re-exporting components
from the split modules for backward compatibility.
"""

from __future__ import annotations

from typing import Any

# Import routes to register them with the app
from . import (
    api,  # noqa: F401
    routes,  # noqa: F401
)

# Import config utilities (for backward compatibility)
from .config import reset_config

# Import database helpers
from .db_helpers import (
    get_collection_info,
    get_document_by_id,
    get_documents_paginated,
    get_indexed_fields,
)

# Import pagination
from .pagination import Pagination

# Import schema helpers
from .schema import (
    TableColumn,
    format_cell_value,
    infer_table_schema,
)

# Import search functionality
from .search import (
    SearchResult,
    _create_snippet,
    search_all_collections,
    search_collection,
)

# Import state management (must be first to create app and env)
from .state import (
    _get_query_param,
    app,
    env,
    get_config,
    get_db,
    get_state,
    init_app,
    render,
    reset_app,
)

# =============================================================================
# Jinja2 Filter Registration
# =============================================================================


def _jinja_format_cell(
    value: Any, column_name: str = "", collection_name: str = ""
) -> dict[str, Any]:
    """Jinja2 filter wrapper for format_cell_value."""
    return format_cell_value(
        value,
        column_name=column_name or None,
        collection_name=collection_name or None,
    )


# Register Jinja2 filters
env.filters["format_cell"] = _jinja_format_cell


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "Pagination",
    "SearchResult",
    "TableColumn",
    "_create_snippet",
    "_get_query_param",
    "app",
    "env",
    "format_cell_value",
    "get_collection_info",
    "get_config",
    "get_db",
    "get_document_by_id",
    "get_documents_paginated",
    "get_indexed_fields",
    "get_state",
    "infer_table_schema",
    "init_app",
    "render",
    "reset_app",
    "reset_config",
    "search_all_collections",
    "search_collection",
]
