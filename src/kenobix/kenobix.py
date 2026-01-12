"""
KenobiX - High-Performance Document Database

A document database with proper indexing supporting SQLite and PostgreSQL backends.

Based on KenobiDB by Harrison Erd (https://github.com/patx/kenobi)
Enhanced with JSON optimizations and generated column indexes.

Key features:
1. Generated columns with indexes for specified fields (15-53x faster searches)
2. Automatic index usage in queries
3. Better concurrency model (no RLock for reads)
4. Cursor-based pagination option
5. Query plan analysis tools
6. 80-665x faster update operations
7. Multiple collections (MongoDB-style)
8. Full ACID transactions
9. Multiple database backends (SQLite, PostgreSQL)

Copyright (c) 2025 KenobiX Contributors
Original KenobiDB Copyright (c) Harrison Erd
Licensed under BSD-3-Clause
"""

from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from .backends import SQLiteBackend
from .collection import Collection

if TYPE_CHECKING:
    from .backends.base import DatabaseBackend


def _create_backend(connection_string: str) -> DatabaseBackend:
    """
    Create appropriate backend based on connection string.

    Args:
        connection_string: Database connection string or file path

    Returns:
        DatabaseBackend instance

    Examples:
        _create_backend("mydb.db")  # SQLite file
        _create_backend(":memory:")  # SQLite in-memory
        _create_backend("postgresql://user:pass@host/db")  # PostgreSQL
    """
    # Convert Path objects to string
    if isinstance(connection_string, Path):
        connection_string = str(connection_string)

    # Check for PostgreSQL URL
    if connection_string.startswith(("postgresql://", "postgres://")):
        try:
            # Import locally to allow using SQLite without psycopg2 installed
            from .backends.postgres import (  # noqa: PLC0415
                PostgreSQLBackend,
                parse_postgres_url,
            )
        except ImportError as e:
            msg = (
                "PostgreSQL support requires psycopg2. "
                "Install with: uv add kenobix[postgres]"
            )
            raise ImportError(msg) from e

        params = parse_postgres_url(connection_string)
        return PostgreSQLBackend(**params)

    # Default to SQLite
    return SQLiteBackend(connection_string)


class KenobiX:
    """
    KenobiX - High-performance document database with JSON optimization.

    Performance improvements over basic document stores:
    - 15-53x faster searches on indexed fields
    - 80-665x faster update operations
    - Minimal storage overhead (VIRTUAL generated columns for SQLite)
    - Automatic index usage with fallback to json_extract
    - Multi-collection support (MongoDB-style)

    Example:
        # SQLite (default)
        db = KenobiX('test.db', indexed_fields=['name', 'age'])
        db.insert({'name': 'Alice', 'age': 30})

        # PostgreSQL
        db = KenobiX('postgresql://user:pass@localhost/mydb')

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

    def __init__(
        self,
        connection: str | None = None,
        indexed_fields: list[str] | None = None,
        *,
        backend: DatabaseBackend | None = None,
        file: str | None = None,  # Deprecated, use connection
    ) -> None:
        """
        Initialize the database with optional field indexing.

        Args:
            connection: Connection string or file path:
                - SQLite: file path like 'test.db' or ':memory:'
                - PostgreSQL: URL like 'postgresql://user:pass@host/dbname'
            indexed_fields: List of document fields to create indexes for
                          (applies to default 'documents' collection)
                          Example: ['name', 'age', 'email']
            backend: Pre-configured backend instance (advanced usage)
            file: Deprecated, use connection parameter

        Examples:
            # SQLite (file-based)
            db = KenobiX('mydb.db', indexed_fields=['name'])

            # SQLite (in-memory)
            db = KenobiX(':memory:')

            # PostgreSQL
            db = KenobiX('postgresql://user:pass@localhost/mydb')

            # Explicit backend
            from kenobix.backends import PostgreSQLBackend
            backend = PostgreSQLBackend(host='localhost', database='mydb')
            db = KenobiX(backend=backend)
        """
        # Handle deprecated 'file' parameter
        if file is not None and connection is None:
            connection = file

        # Validate parameters
        if backend is None and connection is None:
            msg = "Either 'connection' or 'backend' must be provided"
            raise ValueError(msg)

        # Create or use provided backend
        if backend is not None:
            self._backend = backend
        else:
            assert connection is not None
            self._backend = _create_backend(connection)

        # Store connection string for reference (backward compatibility)
        self.file = connection or ""

        # Connect to database
        self._backend.connect()
        self._backend.add_regexp_support()
        self._backend.enable_wal_mode()

        # Shared write lock for all collections
        self._write_lock = RLock()

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Collection management
        self._collections: dict[str, Collection] = {}
        self._default_collection_name = "documents"

        # Always create default collection eagerly (backward compatibility)
        # This prevents table creation from happening inside transactions
        self._default_collection = self.collection(
            self._default_collection_name, indexed_fields=indexed_fields or []
        )
        # For backward compatibility: expose _indexed_fields from default collection
        self._indexed_fields = self._default_collection._indexed_fields

    # ==================================================================================
    # Backend Access (for internal use and Collection)
    # ==================================================================================

    @property
    def _connection(self) -> Any:
        """
        Get underlying database connection.

        For backward compatibility with code that accesses _connection directly.
        New code should use backend methods.
        """
        return self._backend.connection

    @property
    def _in_transaction(self) -> bool:
        """Check if currently in a transaction."""
        return self._backend.in_transaction

    @_in_transaction.setter
    def _in_transaction(self, value: bool) -> None:
        """Set transaction state."""
        self._backend.in_transaction = value

    @property
    def dialect(self):
        """Get the SQL dialect for this database."""
        return self._backend.dialect

    @staticmethod
    def _sanitize_field_name(field: str) -> str:
        """
        Convert field name to valid SQL identifier.

        For backward compatibility with ODM code that accesses this method.
        """
        return "".join(c if c.isalnum() else "_" for c in field)

    def _maybe_commit(self) -> None:
        """
        Commit if not in a transaction.

        For backward compatibility with ODM code that accesses this method.
        """
        self._backend.maybe_commit()

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
        query = self._backend.dialect.list_tables_query()
        cursor = self._backend.execute(query)
        return [row[0] for row in self._backend.fetchall(cursor)]

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
        # Get database size
        size_query = self._backend.dialect.database_size_query()
        cursor = self._backend.execute(size_query)
        row = self._backend.fetchone(cursor)
        db_size = row[0] if row else 0

        collections = self.collections()

        # For backward compatibility: get document count from default collection
        count_query = f"SELECT COUNT(*) FROM {self._default_collection_name}"
        cursor = self._backend.execute(count_query)
        row = self._backend.fetchone(cursor)
        doc_count = row[0] if row else 0

        indexed_fields = list(self._default_collection.get_indexed_fields())

        return {
            "document_count": doc_count,  # Backward compat: count from default collection
            "database_size_bytes": db_size,
            "indexed_fields": indexed_fields,  # Backward compat
            "collection_count": len(collections),
            "collections": collections,
            "wal_mode": True,
            "backend": type(self._backend).__name__,
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

    def begin(self) -> None:
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
            self._backend.begin_transaction()

    def commit(self) -> None:
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
            self._backend.commit()
            self._in_transaction = False
            self._backend.reset_savepoint_counter()

    def rollback(self) -> None:
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
            self._backend.rollback()
            self._in_transaction = False
            self._backend.reset_savepoint_counter()

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
            name = self._backend.new_savepoint_name()

        with self._write_lock:
            self._backend.create_savepoint(name)

        return name

    def rollback_to(self, savepoint: str) -> None:
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
            self._backend.rollback_to_savepoint(savepoint)

    def release_savepoint(self, savepoint: str) -> None:
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
            self._backend.release_savepoint(savepoint)

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

    def close(self) -> None:
        """Shutdown executor and close connection."""
        self.executor.shutdown()
        with self._write_lock:
            self._backend.close()


class Transaction:
    """
    Context manager for database transactions.

    Provides automatic transaction management with commit/rollback.
    """

    def __init__(self, db: KenobiX) -> None:
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
        except Exception:
            # Error during commit/rollback - ensure we rollback
            if not self._savepoint and self.db._in_transaction:
                with contextlib.suppress(Exception):
                    self.db.rollback()
            raise
