"""
KenobiX Web UI - Bottle Application and Routes.

Read-only web interface for exploring KenobiX databases.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bottle import Bottle, request, response
from jinja2 import Environment, PackageLoader, select_autoescape

from .config import (
    CollectionConfig,
    WebUIConfig,
    format_column_name,
    load_config,
    reset_config,
)
from .formatters import format_value

if TYPE_CHECKING:
    from kenobix import KenobiX


def _get_query_param(name: str, default: str = "") -> str:
    """Get a query string parameter with type-safe access."""
    # request.query is a FormsDict; access via __getitem__ with fallback
    query = request.query
    try:
        value = query[name]  # pyrefly: ignore[bad-index]
        return value or default
    except KeyError:
        return default


@dataclass
class _AppState:
    """Module-level state container."""

    db_path: str | None = None
    db_name: str | None = None
    config: WebUIConfig = field(default_factory=WebUIConfig)


# Module state (avoids global statement warnings)
_state = _AppState()

# Create Bottle app
app = Bottle()

# Setup Jinja2 environment
env = Environment(
    loader=PackageLoader("kenobix.webui", "templates"),
    autoescape=select_autoescape(["html"]),
)


def init_app(db_path: str, *, ignore_config: bool = False) -> None:
    """
    Initialize the app with database path.

    Args:
        db_path: Path to the KenobiX database file
        ignore_config: If True, skip loading kenobix.toml config file
    """
    _state.db_path = db_path
    _state.db_name = Path(db_path).name
    _state.config = load_config(db_path, ignore_config=ignore_config)


@contextmanager
def get_db():
    """
    Get a database connection.

    Yields:
        KenobiX database instance
    """
    from kenobix import KenobiX  # noqa: PLC0415

    if _state.db_path is None:
        msg = "Database not initialized. Call init_app() first."
        raise RuntimeError(msg)

    db = KenobiX(_state.db_path)
    try:
        yield db
    finally:
        db.close()


def render(template_name: str, **context: Any) -> str:
    """
    Render a Jinja2 template.

    Args:
        template_name: Name of the template file
        **context: Variables to pass to the template

    Returns:
        Rendered HTML string
    """
    tmpl = env.get_template(template_name)
    # Add common context
    context.setdefault("db_name", _state.db_name)
    return tmpl.render(**context)


@dataclass
class Pagination:
    """Pagination helper."""

    page: int
    per_page: int
    total: int

    @property
    def total_pages(self) -> int:
        """Total number of pages."""
        if self.total == 0:
            return 1
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.per_page


def get_collection_info(db: KenobiX, name: str) -> dict[str, Any]:
    """
    Get information about a collection.

    Args:
        db: Database instance
        name: Collection name

    Returns:
        Dict with count and indexed fields
    """
    # Get document count
    cursor = db._backend.execute(f"SELECT COUNT(*) FROM {name}")
    row = db._backend.fetchone(cursor)
    count = row[0] if row else 0

    # Get indexed fields from index names
    indexed = get_indexed_fields(db, name)

    return {"name": name, "count": count, "indexed": indexed}


def get_indexed_fields(db: KenobiX, collection_name: str) -> list[str]:
    """
    Get list of indexed fields for a collection.

    Args:
        db: Database instance
        collection_name: Name of the collection

    Returns:
        List of indexed field names
    """
    # KenobiX creates indexes with naming pattern: {table_name}_idx_{field_name}
    cursor = db._backend.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
        (collection_name,),
    )

    prefix = f"{collection_name}_idx_"
    indexed = []
    for row in db._backend.fetchall(cursor):
        index_name = row[0]
        if index_name.startswith(prefix):
            field_name = index_name[len(prefix) :]
            indexed.append(field_name)

    return sorted(indexed)


def get_document_by_id(db: KenobiX, collection_name: str, doc_id: int) -> dict | None:
    """
    Get a single document by ID.

    Args:
        db: Database instance
        collection_name: Name of the collection
        doc_id: Document ID

    Returns:
        Document dict with _id, or None if not found
    """
    cursor = db._backend.execute(
        f"SELECT id, data FROM {collection_name} WHERE id = ?", (doc_id,)
    )
    row = db._backend.fetchone(cursor)
    if row is None:
        return None

    doc_id, data_json = row
    try:
        data = json.loads(data_json)
        return {"_id": doc_id, **data}
    except json.JSONDecodeError:
        return {"_id": doc_id, "_raw_data": data_json}


def get_documents_paginated(
    db: KenobiX, collection_name: str, limit: int, offset: int
) -> list[dict]:
    """
    Get documents from a collection with pagination.

    Args:
        db: Database instance
        collection_name: Name of the collection
        limit: Maximum number of documents
        offset: Number of documents to skip

    Returns:
        List of document dicts with _id
    """
    cursor = db._backend.execute(
        f"SELECT id, data FROM {collection_name} ORDER BY id LIMIT ? OFFSET ?",
        (limit, offset),
    )

    documents = []
    for row in db._backend.fetchall(cursor):
        doc_id, data_json = row
        try:
            data = json.loads(data_json)
            documents.append({"_id": doc_id, **data})
        except json.JSONDecodeError:
            documents.append({"_id": doc_id, "_raw_data": data_json})

    return documents


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


def infer_table_schema(
    documents: list[dict],
    indexed_fields: list[str],
    collection_name: str | None = None,
    max_columns: int | None = None,
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
    """
    config = _state.config

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


def format_cell_value(
    value: Any,
    max_length: int = 50,
    formatter: str = "auto",
    column_name: str | None = None,
    collection_name: str | None = None,
) -> dict[str, Any]:
    """
    Format a value for display in a table cell.

    Args:
        value: The value to format
        max_length: Maximum display length for strings
        formatter: Formatter name (e.g., "auto", "currency:USD", "badge")
        column_name: Optional column name for config lookup
        collection_name: Optional collection name for config lookup

    Returns:
        Dict with 'display' (string to show), 'type' (css class), 'full' (full value if truncated)
    """
    config = _state.config

    # If column and collection provided, look up configured formatter
    if column_name and collection_name and formatter == "auto":
        coll_config = config.get_collection(collection_name)
        formatter = coll_config.get_formatter(column_name)

    # Use the formatters module
    return format_value(value, formatter, config, max_length)


# =============================================================================
# Search Functions
# =============================================================================


@dataclass
class SearchResult:
    """A single search result."""

    collection: str
    doc_id: int
    doc: dict
    snippet: str


def search_collection(
    db: KenobiX,
    collection_name: str,
    query: str,
    limit: int = 50,
) -> list[SearchResult]:
    """
    Search documents in a collection using substring matching.

    Args:
        db: Database instance
        collection_name: Name of the collection
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    # Escape special characters for LIKE
    escaped_query = query.replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped_query}%"

    cursor = db._backend.execute(
        f"SELECT id, data FROM {collection_name} WHERE data LIKE ? ESCAPE '\\' LIMIT ?",
        (pattern, limit),
    )

    results = []
    for row in db._backend.fetchall(cursor):
        doc_id, data_json = row
        try:
            data = json.loads(data_json)
            doc = {"_id": doc_id, **data}
        except json.JSONDecodeError:
            doc = {"_id": doc_id, "_raw_data": data_json}

        # Create a snippet showing context around the match
        snippet = _create_snippet(data_json, query)
        results.append(SearchResult(collection_name, doc_id, doc, snippet))

    return results


def search_all_collections(
    db: KenobiX,
    query: str,
    limit_per_collection: int = 20,
) -> dict[str, list[SearchResult]]:
    """
    Search across all collections.

    Args:
        db: Database instance
        query: Search query string
        limit_per_collection: Maximum results per collection

    Returns:
        Dict mapping collection names to search results
    """
    results: dict[str, list[SearchResult]] = {}

    for collection_name in db.collections():
        collection_results = search_collection(
            db, collection_name, query, limit_per_collection
        )
        if collection_results:
            results[collection_name] = collection_results

    return results


def _create_snippet(data_json: str, query: str, context_chars: int = 50) -> str:
    """
    Create a text snippet showing the query in context.

    Args:
        data_json: The JSON data string
        query: The search query
        context_chars: Characters of context on each side

    Returns:
        Snippet string with match highlighted
    """
    query_lower = query.lower()
    data_lower = data_json.lower()

    pos = data_lower.find(query_lower)
    if pos == -1:
        # No match found (shouldn't happen), return truncated data
        return data_json[:100] + "..." if len(data_json) > 100 else data_json

    # Calculate snippet boundaries
    start = max(0, pos - context_chars)
    end = min(len(data_json), pos + len(query) + context_chars)

    # Build snippet
    snippet = ""
    if start > 0:
        snippet += "..."
    snippet += data_json[start:end]
    if end < len(data_json):
        snippet += "..."

    return snippet


# =============================================================================
# HTML Routes
# =============================================================================


@app.route("/")
def index():
    """Database overview page."""
    config = _state.config

    with get_db() as db:
        # Get all collections, filtering out hidden ones
        collection_names = [
            name for name in db.collections()
            if not config.is_collection_hidden(name)
        ]

        # Get info for each collection
        collections = []
        for name in collection_names:
            info = get_collection_info(db, name)
            # Add display_name from config if available
            coll_config = config.get_collection(name)
            if coll_config.display_name:
                info["display_name"] = coll_config.display_name
            else:
                info["display_name"] = name
            collections.append(info)

        # Calculate totals
        total_docs = sum(c["count"] for c in collections)

        # Get database size
        stats = db.stats()
        db_size = stats.get("database_size_bytes", 0)

        return render(
            "index.html",
            collections=collections,
            total_docs=total_docs,
            db_size=db_size,
            db_path=_state.db_path,
            theme=config.theme,
        )


@app.route("/collection/<name>")
def collection_view(name: str):
    """Collection view with paginated documents."""
    config = _state.config
    coll_config = config.get_collection(name)

    # Get pagination params
    try:
        page = int(_get_query_param("page", "1"))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    per_page = config.per_page

    with get_db() as db:
        # Check collection exists
        if name not in db.collections():
            response.status = 404
            return render("error.html", message=f"Collection '{name}' not found")

        # Get collection info
        info = get_collection_info(db, name)
        total = info["count"]
        indexed = info["indexed"]

        # Create pagination
        pagination = Pagination(page=page, per_page=per_page, total=total)

        # Get documents for this page
        documents = get_documents_paginated(db, name, per_page, pagination.offset)

        # Infer table schema from documents (uses config if columns specified)
        columns = infer_table_schema(documents, indexed, collection_name=name)

        # Get display name
        display_name = coll_config.display_name or name

        return render(
            "collection.html",
            collection=name,
            display_name=display_name,
            documents=documents,
            columns=columns,
            pagination=pagination,
            total=total,
            indexed=indexed,
            collection_config=coll_config,
        )


@app.route("/collection/<name>/doc/<doc_id:int>")
def document_view(name: str, doc_id: int):
    """Single document detail view."""
    with get_db() as db:
        # Check collection exists
        if name not in db.collections():
            response.status = 404
            return render("error.html", message=f"Collection '{name}' not found")

        # Get document
        doc = get_document_by_id(db, name, doc_id)
        if doc is None:
            response.status = 404
            return render(
                "error.html", message=f"Document #{doc_id} not found in '{name}'"
            )

        return render(
            "document.html",
            collection=name,
            doc=doc,
            doc_json=json.dumps(doc, indent=2, ensure_ascii=False),
        )


@app.route("/search")
def search_view():
    """Search page - search across all collections or within a specific one."""
    query = _get_query_param("q").strip()
    collection_filter = _get_query_param("collection").strip()

    if not query:
        # Show empty search page
        with get_db() as db:
            collections = db.collections()
        return render(
            "search.html",
            query="",
            results={},
            total_results=0,
            collections=collections,
            selected_collection=collection_filter,
        )

    with get_db() as db:
        collections = db.collections()

        if collection_filter and collection_filter in collections:
            # Search in specific collection
            collection_results = search_collection(db, collection_filter, query, 50)
            results = (
                {collection_filter: collection_results} if collection_results else {}
            )
        else:
            # Search all collections
            results = search_all_collections(db, query, 20)

        total_results = sum(len(r) for r in results.values())

        return render(
            "search.html",
            query=query,
            results=results,
            total_results=total_results,
            collections=collections,
            selected_collection=collection_filter,
        )


# =============================================================================
# API Routes (JSON)
# =============================================================================


@app.route("/api/stats")
def api_stats():
    """Database statistics JSON."""
    response.content_type = "application/json"
    with get_db() as db:
        stats = db.stats()
        return json.dumps(stats)


@app.route("/api/collection/<name>")
def api_collection(name: str):
    """Collection documents JSON (paginated)."""
    response.content_type = "application/json"

    # Get pagination params
    try:
        page = int(_get_query_param("page", "1"))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    try:
        per_page = int(_get_query_param("per_page", "20"))
        per_page = min(max(per_page, 1), 100)  # Clamp to 1-100
    except ValueError:
        per_page = 20

    with get_db() as db:
        # Check collection exists
        if name not in db.collections():
            response.status = 404
            return json.dumps({"error": f"Collection '{name}' not found"})

        info = get_collection_info(db, name)
        total = info["count"]

        pagination = Pagination(page=page, per_page=per_page, total=total)
        documents = get_documents_paginated(db, name, per_page, pagination.offset)

        return json.dumps({
            "collection": name,
            "documents": documents,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.total_pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        })


@app.route("/api/collection/<name>/doc/<doc_id:int>")
def api_document(name: str, doc_id: int):
    """Single document JSON."""
    response.content_type = "application/json"

    with get_db() as db:
        # Check collection exists
        if name not in db.collections():
            response.status = 404
            return json.dumps({"error": f"Collection '{name}' not found"})

        doc = get_document_by_id(db, name, doc_id)
        if doc is None:
            response.status = 404
            return json.dumps({"error": f"Document #{doc_id} not found"})

        return json.dumps(doc)


@app.route("/api/search")
def api_search():
    """Search API endpoint."""
    response.content_type = "application/json"

    query = _get_query_param("q").strip()
    collection_filter = _get_query_param("collection").strip()

    if not query:
        return json.dumps({"error": "Query parameter 'q' is required"})

    with get_db() as db:
        collections = db.collections()

        if collection_filter and collection_filter in collections:
            collection_results = search_collection(db, collection_filter, query, 50)
            results = (
                {collection_filter: collection_results} if collection_results else {}
            )
        else:
            results = search_all_collections(db, query, 20)

        # Convert SearchResult objects to dicts
        serialized = {}
        for coll_name, coll_results in results.items():
            serialized[coll_name] = [
                {
                    "id": r.doc_id,
                    "document": r.doc,
                    "snippet": r.snippet,
                }
                for r in coll_results
            ]

        return json.dumps({
            "query": query,
            "collection": collection_filter or None,
            "results": serialized,
            "total": sum(len(r) for r in results.values()),
        })


# =============================================================================
# Module Initialization
# =============================================================================


def _jinja_format_cell(value: Any, column_name: str = "", collection_name: str = "") -> dict[str, Any]:
    """Jinja2 filter wrapper for format_cell_value."""
    return format_cell_value(
        value,
        column_name=column_name or None,
        collection_name=collection_name or None,
    )


# Register Jinja2 filters (must be after function definitions)
env.filters["format_cell"] = _jinja_format_cell


# Re-export for testing
__all__ = [
    "Pagination",
    "SearchResult",
    "TableColumn",
    "_create_snippet",
    "app",
    "format_cell_value",
    "get_collection_info",
    "get_db",
    "get_documents_paginated",
    "get_indexed_fields",
    "infer_table_schema",
    "init_app",
    "render",
    "reset_app",
    "reset_config",
    "search_all_collections",
    "search_collection",
]


def reset_app() -> None:
    """Reset app state (useful for testing)."""
    global _state  # noqa: PLW0603
    _state = _AppState()
    reset_config()
