"""API routes for KenobiX Web UI.

This module provides JSON API endpoints for programmatic access.
"""

from __future__ import annotations

import json

from bottle import response

from .db_helpers import get_collection_info, get_document_by_id, get_documents_paginated
from .pagination import Pagination
from .search import search_all_collections, search_collection
from .state import _get_query_param, app, get_db


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
