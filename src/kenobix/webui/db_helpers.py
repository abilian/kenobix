"""Database helper functions for KenobiX Web UI.

This module provides functions for querying the database,
fetching documents, and getting collection metadata.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kenobix import KenobiX


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
