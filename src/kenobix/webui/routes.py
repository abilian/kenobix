"""HTML routes for KenobiX Web UI.

This module provides the HTML page routes for the web interface.
"""

from __future__ import annotations

import json

from bottle import response

from .db_helpers import get_collection_info, get_document_by_id, get_documents_paginated
from .pagination import Pagination
from .schema import infer_table_schema
from .search import search_all_collections, search_collection
from .state import _get_query_param, app, get_config, get_db, get_state, render


@app.route("/")
def index():
    """Database overview page."""
    config = get_config()
    state = get_state()

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
            db_path=state.db_path,
            theme=config.theme,
        )


@app.route("/collection/<name>")
def collection_view(name: str):
    """Collection view with paginated documents."""
    config = get_config()
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
