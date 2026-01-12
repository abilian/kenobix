"""
KenobiX Database Migration Utilities

Functions for migrating data between SQLite and PostgreSQL databases.

Examples:
    # SQLite to PostgreSQL
    migrate("mydb.db", "postgresql://user:pass@localhost/newdb")

    # PostgreSQL to SQLite
    migrate("postgresql://user:pass@localhost/db", "backup.db")

    # With progress callback
    migrate(source, dest, on_progress=lambda msg: print(msg))
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def get_backend_type(connection: str) -> str:
    """
    Determine backend type from connection string.

    Args:
        connection: Connection string or file path

    Returns:
        'postgresql' or 'sqlite'
    """
    if connection.startswith(("postgresql://", "postgres://")):
        return "postgresql"
    return "sqlite"


def migrate(
    source: str,
    dest: str,
    *,
    on_progress: Callable[[str], None] | None = None,
    batch_size: int = 1000,
) -> dict[str, Any]:
    """
    Migrate data from one KenobiX database to another.

    Copies all collections and their data from source to destination.
    The destination database will be created if it doesn't exist.

    Args:
        source: Source database connection string (file path or PostgreSQL URL)
        dest: Destination database connection string (file path or PostgreSQL URL)
        on_progress: Optional callback for progress messages
        batch_size: Number of documents to copy per batch (default: 1000)

    Returns:
        Dict with migration statistics:
        - collections: Number of collections migrated
        - documents: Total number of documents migrated
        - source_type: Source backend type
        - dest_type: Destination backend type

    Raises:
        ValueError: If source and destination are the same
        ImportError: If PostgreSQL is used but psycopg2 is not installed

    Examples:
        # SQLite to PostgreSQL
        stats = migrate("mydb.db", "postgresql://user:pass@localhost/newdb")
        print(f"Migrated {stats['documents']} documents")

        # With progress output
        migrate(source, dest, on_progress=print)
    """
    from .kenobix import KenobiX  # noqa: PLC0415

    # Validate inputs
    if source == dest:
        msg = "Source and destination cannot be the same"
        raise ValueError(msg)

    source_type = get_backend_type(source)
    dest_type = get_backend_type(dest)

    def log(message: str) -> None:
        if on_progress:
            on_progress(message)

    log(f"Migrating from {source_type} to {dest_type}")

    # Open source database
    log(f"Opening source: {source}")
    source_db = KenobiX(source)

    try:
        # Get all collections from source
        collections = source_db.collections()
        log(f"Found {len(collections)} collection(s): {', '.join(collections)}")

        # Open destination database (will be created if needed)
        log(f"Opening destination: {dest}")
        dest_db = KenobiX(dest)

        try:
            total_docs = 0

            for collection_name in collections:
                source_coll = source_db.collection(collection_name)
                indexed_fields = list(source_coll.get_indexed_fields())

                log(f"Migrating collection '{collection_name}'...")
                if indexed_fields:
                    log(f"  Indexed fields: {', '.join(indexed_fields)}")

                # Create destination collection with same indexed fields
                dest_coll = dest_db.collection(collection_name, indexed_fields=indexed_fields)

                # Count documents in source
                stats = source_coll.stats()
                doc_count = stats["document_count"]
                log(f"  Documents to migrate: {doc_count}")

                if doc_count == 0:
                    continue

                # Migrate in batches using cursor pagination
                migrated = 0
                cursor = None

                while True:
                    # Fetch batch from source
                    result = source_coll.all_cursor(after_id=cursor, limit=batch_size)
                    documents = result["documents"]

                    if not documents:
                        break

                    # Insert batch into destination
                    dest_coll.insert_many(documents)
                    migrated += len(documents)

                    log(f"  Progress: {migrated}/{doc_count} ({100 * migrated // doc_count}%)")

                    if not result["has_more"]:
                        break

                    cursor = result["next_cursor"]

                total_docs += migrated
                log(f"  Completed: {migrated} documents")

            log(f"Migration complete: {len(collections)} collections, {total_docs} documents")

            return {
                "collections": len(collections),
                "documents": total_docs,
                "source_type": source_type,
                "dest_type": dest_type,
            }

        finally:
            dest_db.close()

    finally:
        source_db.close()


def migrate_collection(
    source: str,
    dest: str,
    collection_name: str,
    *,
    indexed_fields: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
    batch_size: int = 1000,
) -> dict[str, Any]:
    """
    Migrate a single collection from one database to another.

    Args:
        source: Source database connection string
        dest: Destination database connection string
        collection_name: Name of the collection to migrate
        indexed_fields: Override indexed fields for destination (optional)
        on_progress: Optional callback for progress messages
        batch_size: Number of documents to copy per batch

    Returns:
        Dict with migration statistics

    Example:
        stats = migrate_collection(
            "mydb.db",
            "postgresql://localhost/newdb",
            "users",
            indexed_fields=["email", "user_id"]
        )
    """
    from .kenobix import KenobiX  # noqa: PLC0415

    source_type = get_backend_type(source)
    dest_type = get_backend_type(dest)

    def log(message: str) -> None:
        if on_progress:
            on_progress(message)

    log(f"Migrating collection '{collection_name}' from {source_type} to {dest_type}")

    source_db = KenobiX(source)

    try:
        source_coll = source_db.collection(collection_name)

        # Use source indexed fields if not overridden
        if indexed_fields is None:
            indexed_fields = list(source_coll.get_indexed_fields())

        dest_db = KenobiX(dest)

        try:
            dest_coll = dest_db.collection(collection_name, indexed_fields=indexed_fields)

            stats = source_coll.stats()
            doc_count = stats["document_count"]
            log(f"Documents to migrate: {doc_count}")

            if doc_count == 0:
                return {
                    "collection": collection_name,
                    "documents": 0,
                    "source_type": source_type,
                    "dest_type": dest_type,
                }

            migrated = 0
            cursor = None

            while True:
                result = source_coll.all_cursor(after_id=cursor, limit=batch_size)
                documents = result["documents"]

                if not documents:
                    break

                dest_coll.insert_many(documents)
                migrated += len(documents)

                log(f"Progress: {migrated}/{doc_count}")

                if not result["has_more"]:
                    break

                cursor = result["next_cursor"]

            log(f"Completed: {migrated} documents")

            return {
                "collection": collection_name,
                "documents": migrated,
                "source_type": source_type,
                "dest_type": dest_type,
            }

        finally:
            dest_db.close()

    finally:
        source_db.close()


def export_to_json(
    source: str,
    output_path: str,
    *,
    collection: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Export database to JSON file.

    Args:
        source: Source database connection string
        output_path: Path to output JSON file
        collection: Specific collection to export (optional, exports all if None)
        on_progress: Optional callback for progress messages

    Returns:
        Dict with export statistics
    """
    from .kenobix import KenobiX  # noqa: PLC0415

    def log(message: str) -> None:
        if on_progress:
            on_progress(message)

    source_db = KenobiX(source)

    try:
        if collection:
            collections = [collection]
        else:
            collections = source_db.collections()

        export_data: dict[str, list[dict]] = {}
        total_docs = 0

        for coll_name in collections:
            log(f"Exporting '{coll_name}'...")
            coll = source_db.collection(coll_name)

            # Get all documents (no limit)
            documents = []
            cursor = None

            while True:
                result = coll.all_cursor(after_id=cursor, limit=1000)
                documents.extend(result["documents"])

                if not result["has_more"]:
                    break

                cursor = result["next_cursor"]

            export_data[coll_name] = documents
            total_docs += len(documents)
            log(f"  Exported {len(documents)} documents")

        with Path(output_path).open("w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)

        log(f"Exported to {output_path}")

        return {
            "collections": len(collections),
            "documents": total_docs,
            "output_path": output_path,
        }

    finally:
        source_db.close()


def import_from_json(
    json_path: str,
    dest: str,
    *,
    indexed_fields: dict[str, list[str]] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Import database from JSON file.

    Args:
        json_path: Path to JSON file
        dest: Destination database connection string
        indexed_fields: Dict mapping collection names to indexed fields
        on_progress: Optional callback for progress messages

    Returns:
        Dict with import statistics
    """
    from .kenobix import KenobiX  # noqa: PLC0415

    def log(message: str) -> None:
        if on_progress:
            on_progress(message)

    indexed_fields = indexed_fields or {}

    with Path(json_path).open(encoding="utf-8") as f:
        import_data = json.load(f)

    dest_db = KenobiX(dest)

    try:
        total_docs = 0

        for coll_name, documents in import_data.items():
            log(f"Importing '{coll_name}'...")

            fields = indexed_fields.get(coll_name, [])
            coll = dest_db.collection(coll_name, indexed_fields=fields)

            if documents:
                # Insert in batches
                batch_size = 1000
                for i in range(0, len(documents), batch_size):
                    batch = documents[i : i + batch_size]
                    coll.insert_many(batch)

            total_docs += len(documents)
            log(f"  Imported {len(documents)} documents")

        log(f"Import complete: {len(import_data)} collections, {total_docs} documents")

        return {
            "collections": len(import_data),
            "documents": total_docs,
        }

    finally:
        dest_db.close()
