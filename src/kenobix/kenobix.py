"""
KenobiX - High-Performance Document Database

A SQLite3-backed document database with proper indexing for 15-665x faster operations.

Based on KenobiDB by Harrison Erd (https://github.com/patx/kenobi)
Enhanced with SQLite3 JSON optimizations and generated column indexes.

Key features:
1. Generated columns with indexes for specified fields (15-53x faster searches)
2. Automatic index usage in queries
3. Better concurrency model (no RLock for reads)
4. Cursor-based pagination option
5. Query plan analysis tools
6. 80-665x faster update operations
7. Multiple collections (MongoDB-style)
8. Full ACID transactions

Copyright (c) 2025 KenobiX Contributors
Original KenobiDB Copyright (c) Harrison Erd
Licensed under BSD-3-Clause
"""

from __future__ import annotations

import contextlib
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from typing import Any

from .collection import Collection


class KenobiX:
    """
    KenobiX - High-performance document database with SQLite3 JSON optimization.

    Performance improvements over basic document stores:
    - 15-53x faster searches on indexed fields
    - 80-665x faster update operations
    - Minimal storage overhead (VIRTUAL generated columns)
    - Automatic index usage with fallback to json_extract
    - Multi-collection support (MongoDB-style)

    Example:
        # Single collection (backward compatible)
        db = KenobiX('test.db', indexed_fields=['name', 'age'])
        db.insert({'name': 'Alice', 'age': 30})

        # Multiple collections
        users = db.collection('users', indexed_fields=['user_id', 'email'])
        orders = db.collection('orders', indexed_fields=['order_id', 'user_id'])
        users.insert({'user_id': 1, 'email': 'alice@example.com'})

        # Dict-style access
        db['users'].insert({'user_id': 2, 'email': 'bob@example.com'})

        # Transactions work across collections
        with db.transaction():
            db['users'].insert({'user_id': 3})
            db['orders'].insert({'order_id': 101, 'user_id': 3})
    """

    def __init__(self, file: str, indexed_fields: list[str] | None = None):
        """
        Initialize the database with optional field indexing.

        Args:
            file: Path to SQLite database file
            indexed_fields: List of document fields to create indexes for
                          (applies to default 'documents' collection)
                          Example: ['name', 'age', 'email']
        """
        self.file = file
        self._write_lock = RLock()  # Shared across all collections
        self._connection = sqlite3.connect(self.file, check_same_thread=False)
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Transaction state (shared across all collections)
        self._in_transaction = False
        self._savepoint_counter = 0

        # Collection management
        self._collections: dict[str, Collection] = {}
        self._default_collection_name = "documents"

        # Add REGEXP support
        self._add_regexp_support(self._connection)

        # Enable WAL mode
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.commit()

        # Always create default collection eagerly (backward compatibility)
        # This prevents table creation from happening inside transactions
        self._default_collection = self.collection(
            self._default_collection_name, indexed_fields=indexed_fields or []
        )
        # For backward compatibility: expose _indexed_fields from default collection
        self._indexed_fields = self._default_collection._indexed_fields

    @staticmethod
    def _add_regexp_support(conn):
        """Add REGEXP function support."""

        def regexp(pattern, value):
            return re.search(pattern, value) is not None

        conn.create_function("REGEXP", 2, regexp)

    @staticmethod
    def _sanitize_field_name(field: str) -> str:
        """
        Convert field name to valid SQL identifier.

        For backward compatibility with ODM code that accesses this method.
        """
        return "".join(c if c.isalnum() else "_" for c in field)

    def _maybe_commit(self):
        """
        Commit if not in a transaction.

        For backward compatibility with ODM code that accesses this method.
        """
        if not self._in_transaction:
            self._connection.commit()

    # ==================================================================================
    # Collection Management
    # ==================================================================================

    def collection(
        self, name: str, indexed_fields: list[str] | None = None
    ) -> Collection:
        """
        Get or create a collection (table).

        Collections are cached - calling this multiple times with the same name
        returns the same Collection instance.

        Args:
            name: Collection name (becomes table name)
            indexed_fields: Fields to create indexes for (only used on creation)

        Returns:
            Collection instance

        Example:
            users = db.collection('users', indexed_fields=['user_id', 'email'])
            users.insert({'user_id': 1, 'email': 'alice@example.com'})
        """
        if name not in self._collections:
            self._collections[name] = Collection(
                self, name, indexed_fields=indexed_fields
            )
        return self._collections[name]

    def __getitem__(self, name: str) -> Collection:
        """
        Dict-style collection access.

        Example:
            db['users'].insert({'name': 'Alice'})
            users = db['users'].all()
        """
        return self.collection(name)

    def collections(self) -> list[str]:
        """
        List all collections (tables) in the database.

        Returns:
            List of collection names
        """
        cursor = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
        return [row[0] for row in cursor.fetchall()]

    def _get_default_collection(self) -> Collection:
        """
        Get the default collection.

        This is used for backward compatibility when methods are called
        directly on KenobiX without specifying a collection.
        The default collection is always created eagerly in __init__.
        """
        assert self._default_collection is not None
        return self._default_collection

    # ==================================================================================
    # Backward Compatibility - Delegate to Default Collection
    # ==================================================================================

    def insert(self, document: dict[str, Any]) -> int:
        """
        Insert a document into the default collection.

        For backward compatibility. New code should use:
            db.collection('name').insert(...)

        Args:
            document: Dictionary to insert

        Returns:
            The ID of the inserted document
        """
        return self._get_default_collection().insert(document)

    def insert_many(self, document_list: list[dict[str, Any]]) -> list[int]:
        """
        Insert multiple documents into the default collection.

        For backward compatibility. New code should use:
            db.collection('name').insert_many(...)

        Args:
            document_list: List of documents to insert

        Returns:
            List of IDs of the inserted documents
        """
        return self._get_default_collection().insert_many(document_list)

    def remove(self, key: str, value: Any) -> int:
        """
        Remove documents from the default collection.

        For backward compatibility. New code should use:
            db.collection('name').remove(...)

        Args:
            key: The field name to match
            value: The value to match

        Returns:
            Number of documents removed
        """
        return self._get_default_collection().remove(key, value)

    def update(self, id_key: str, id_value: Any, new_dict: dict[str, Any]) -> bool:
        """
        Update documents in the default collection.

        For backward compatibility. New code should use:
            db.collection('name').update(...)

        Args:
            id_key: The field name to match
            id_value: The value to match
            new_dict: A dictionary of changes to apply

        Returns:
            True if at least one document was updated
        """
        return self._get_default_collection().update(id_key, id_value, new_dict)

    def purge(self) -> bool:
        """
        Remove all documents from the default collection.

        For backward compatibility. New code should use:
            db.collection('name').purge()

        Returns:
            True upon successful purge
        """
        return self._get_default_collection().purge()

    def search(
        self, key: str, value: Any, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """
        Search documents in the default collection.

        For backward compatibility. New code should use:
            db.collection('name').search(...)

        Args:
            key: Field name to search
            value: Value to match
            limit: Max results to return
            offset: Skip this many results

        Returns:
            List of matching documents
        """
        return self._get_default_collection().search(key, value, limit, offset)

    def search_optimized(self, **filters) -> list[dict]:
        """
        Multi-field search in the default collection.

        For backward compatibility. New code should use:
            db.collection('name').search_optimized(...)

        Args:
            **filters: field=value pairs to search

        Returns:
            List of matching documents
        """
        return self._get_default_collection().search_optimized(**filters)

    def all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """
        Get all documents from the default collection.

        For backward compatibility. New code should use:
            db.collection('name').all(...)

        Args:
            limit: Max results to return
            offset: Skip this many results

        Returns:
            List of documents
        """
        return self._get_default_collection().all(limit, offset)

    def all_cursor(self, after_id: int | None = None, limit: int = 100) -> dict:
        """
        Cursor-based pagination for the default collection.

        For backward compatibility. New code should use:
            db.collection('name').all_cursor(...)

        Args:
            after_id: Continue from this document ID
            limit: Max results to return

        Returns:
            Dict with 'documents', 'next_cursor', 'has_more'
        """
        return self._get_default_collection().all_cursor(after_id, limit)

    def search_pattern(
        self, key: str, pattern: str, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """
        Search documents matching a regex pattern in the default collection.

        For backward compatibility. New code should use:
            db.collection('name').search_pattern(...)

        Args:
            key: The document field to match on
            pattern: The regex pattern to match
            limit: The maximum number of documents to return
            offset: The starting point for retrieval

        Returns:
            List of matching documents
        """
        return self._get_default_collection().search_pattern(
            key, pattern, limit, offset
        )

    def find_any(self, key: str, value_list: list[Any]) -> list[dict]:
        """
        Return documents where key matches any value in value_list.

        For backward compatibility. New code should use:
            db.collection('name').find_any(...)

        Args:
            key: The document field to match on
            value_list: A list of possible values

        Returns:
            A list of matching documents
        """
        return self._get_default_collection().find_any(key, value_list)

    def find_all(self, key: str, value_list: list[Any]) -> list[dict]:
        """
        Return documents where the key contains all values in value_list.

        For backward compatibility. New code should use:
            db.collection('name').find_all(...)

        Args:
            key: The field to match
            value_list: The required values to match

        Returns:
            A list of matching documents
        """
        return self._get_default_collection().find_all(key, value_list)

    def execute_async(self, func, *args, **kwargs):
        """
        Execute a function asynchronously using a thread pool.

        Args:
            func: The function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            concurrent.futures.Future: A Future object representing the execution
        """
        return self.executor.submit(func, *args, **kwargs)

    def explain(self, operation: str, *args) -> list[tuple]:
        """
        Show query execution plan for the default collection.

        For backward compatibility. New code should use:
            db.collection('name').explain(...)

        Args:
            operation: Method name ('search', 'all', etc.)
            *args: Arguments to the method

        Returns:
            List of query plan tuples from EXPLAIN QUERY PLAN
        """
        return self._get_default_collection().explain(operation, *args)

    def get_indexed_fields(self) -> set[str]:
        """
        Return set of fields that have indexes in the default collection.

        For backward compatibility. New code should use:
            db.collection('name').get_indexed_fields()

        Returns:
            Set of indexed field names
        """
        return self._get_default_collection().get_indexed_fields()

    def stats(self) -> dict[str, Any]:
        """
        Get database statistics.

        For backward compatibility, includes document_count from default collection.

        Returns:
            Dict with database size, collection count, document count, etc.
        """
        cursor = self._connection.execute(
            "SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()"
        )
        db_size = cursor.fetchone()[0]

        collections = self.collections()

        # For backward compatibility: get document count and indexed fields from default collection
        cursor = self._connection.execute(
            f"SELECT COUNT(*) FROM {self._default_collection_name}"
        )
        doc_count = cursor.fetchone()[0]
        indexed_fields = list(self._default_collection.get_indexed_fields())

        return {
            "document_count": doc_count,  # Backward compat: count from default collection
            "database_size_bytes": db_size,
            "indexed_fields": indexed_fields,  # Backward compat
            "collection_count": len(collections),
            "collections": collections,
            "wal_mode": True,
        }

    def create_index(self, field: str) -> bool:
        """
        Dynamically create an index on the default collection.

        For backward compatibility. New code should use:
            db.collection('name').create_index(...)

        Args:
            field: Document field to index

        Returns:
            True if index was created
        """
        return self._get_default_collection().create_index(field)

    # ==================================================================================
    # Transaction Methods (Shared Across All Collections)
    # ==================================================================================

    def begin(self):
        """
        Begin a new transaction.

        Transactions work across all collections.

        Example:
            db.begin()
            try:
                db['users'].insert({'name': 'Alice'})
                db['orders'].insert({'order_id': 101})
                db.commit()
            except:
                db.rollback()

        Raises:
            RuntimeError: If already in a transaction
        """
        if self._in_transaction:
            msg = "Already in a transaction. Use savepoint() for nested transactions."
            raise RuntimeError(msg)

        with self._write_lock:
            self._connection.execute("BEGIN")
            self._in_transaction = True

    def commit(self):
        """
        Commit the current transaction.

        Makes all changes since begin() permanent across all collections.

        Raises:
            RuntimeError: If not in a transaction
        """
        if not self._in_transaction:
            msg = "Not in a transaction"
            raise RuntimeError(msg)

        with self._write_lock:
            self._connection.commit()
            self._in_transaction = False
            self._savepoint_counter = 0

    def rollback(self):
        """
        Rollback the current transaction.

        Discards all changes since begin() across all collections.

        Raises:
            RuntimeError: If not in a transaction
        """
        if not self._in_transaction:
            msg = "Not in a transaction"
            raise RuntimeError(msg)

        with self._write_lock:
            self._connection.rollback()
            self._in_transaction = False
            self._savepoint_counter = 0

    def savepoint(self, name: str | None = None) -> str:
        """
        Create a savepoint within a transaction.

        Savepoints allow partial rollback within a transaction.

        Args:
            name: Optional savepoint name (auto-generated if not provided)

        Returns:
            Savepoint name

        Example:
            db.begin()
            db['users'].insert({'name': 'Alice'})
            sp = db.savepoint()
            db['users'].insert({'name': 'Bob'})
            db.rollback_to(sp)  # Rolls back Bob, keeps Alice
            db.commit()

        Raises:
            RuntimeError: If not in a transaction
        """
        if not self._in_transaction:
            msg = "Must be in a transaction to create savepoint"
            raise RuntimeError(msg)

        if name is None:
            self._savepoint_counter += 1
            name = f"sp_{self._savepoint_counter}"

        with self._write_lock:
            self._connection.execute(f"SAVEPOINT {name}")

        return name

    def rollback_to(self, savepoint: str):
        """
        Rollback to a specific savepoint.

        Args:
            savepoint: Savepoint name (from savepoint() method)

        Raises:
            RuntimeError: If not in a transaction
        """
        if not self._in_transaction:
            msg = "Not in a transaction"
            raise RuntimeError(msg)

        with self._write_lock:
            self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")

    def release_savepoint(self, savepoint: str):
        """
        Release a savepoint (commit it within the transaction).

        Args:
            savepoint: Savepoint name

        Raises:
            RuntimeError: If not in a transaction
        """
        if not self._in_transaction:
            msg = "Not in a transaction"
            raise RuntimeError(msg)

        with self._write_lock:
            self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")

    def transaction(self):
        """
        Context manager for transactions.

        Automatically begins transaction on enter and commits on exit.
        Rolls back on exception. Works across all collections.

        Example:
            with db.transaction():
                db['users'].insert({'name': 'Alice'})
                db['orders'].insert({'order_id': 101})
                # Both committed together, or both rolled back on error

        Returns:
            Transaction context manager
        """
        return Transaction(self)

    # ==================================================================================
    # Database Management
    # ==================================================================================

    def close(self):
        """Shutdown executor and close connection."""
        self.executor.shutdown()
        with self._write_lock:
            self._connection.close()


class Transaction:
    """
    Context manager for database transactions.

    Provides automatic transaction management with commit/rollback.
    """

    def __init__(self, db: KenobiX):
        """
        Initialize transaction context manager.

        Args:
            db: KenobiX database instance
        """
        self.db = db
        self._savepoint: str | None = None

    def __enter__(self):
        """Begin transaction or create savepoint if nested."""
        if self.db._in_transaction:
            # Nested transaction - use savepoint
            self._savepoint = self.db.savepoint()
        else:
            # Top-level transaction
            self.db.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Commit on success, rollback on exception."""
        try:
            if exc_type is not None:
                # Exception occurred - rollback
                if self._savepoint:
                    self.db.rollback_to(self._savepoint)
                else:
                    self.db.rollback()
                return False  # Re-raise exception
            # Success - commit
            if self._savepoint:
                self.db.release_savepoint(self._savepoint)
            else:
                self.db.commit()
            return True
        except sqlite3.Error:
            # Error during commit/rollback - ensure we rollback
            if not self._savepoint and self.db._in_transaction:
                with contextlib.suppress(sqlite3.Error):
                    self.db.rollback()
            raise
