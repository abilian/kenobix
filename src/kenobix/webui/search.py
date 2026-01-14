"""Search functionality for KenobiX Web UI.

This module provides functions for searching documents across collections.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kenobix import KenobiX


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
