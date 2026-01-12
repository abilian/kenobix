"""
Collection - A single collection (table) within a KenobiX database.

Each collection operates on its own table with its own schema and indexes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .kenobix import KenobiX


class Collection:
    """
    A single collection (table) in the database.

    Each collection has its own table with its own schema and indexes.
    Similar to a MongoDB collection.
    """

    def __init__(
        self,
        db: KenobiX,
        name: str,
        indexed_fields: list[str] | None = None,
    ) -> None:
        """
        Initialize a collection.

        Args:
            db: Parent KenobiX database instance
            name: Collection name (becomes table name)
            indexed_fields: Fields to create indexes for
        """
        self.db = db
        self.name = name
        self._indexed_fields: set[str] = set(indexed_fields or [])

        # Access backend through parent database
        self._backend = db._backend
        self._write_lock = db._write_lock

        # Initialize table
        self._initialize_table()

    @property
    def _dialect(self):
        """Get SQL dialect from backend."""
        return self._backend.dialect

    def _initialize_table(self) -> None:
        """Create table with generated columns for indexed fields."""
        with self._write_lock:
            # Build CREATE TABLE with generated columns
            pk_col = self._dialect.auto_increment_pk()
            columns = [pk_col, "data TEXT NOT NULL"]

            # Add generated columns for indexed fields
            # Skip "id" and "_id" as they're reserved for the primary key
            for field in self._indexed_fields:
                if field in ("id", "_id"):
                    continue  # Skip reserved column names
                safe_field = self._sanitize_field_name(field)
                json_expr = self._dialect.json_extract("data", field)
                gen_col = self._dialect.generated_column(safe_field, json_expr)
                columns.append(gen_col)

            create_table = (
                f"CREATE TABLE IF NOT EXISTS {self.name} (\n    {', '.join(columns)}\n)"
            )
            self._backend.execute(create_table)

            # Create indexes on generated columns
            # Skip "id" and "_id" as they're reserved for the primary key
            for field in self._indexed_fields:
                if field in ("id", "_id"):
                    continue  # Skip reserved column names
                safe_field = self._sanitize_field_name(field)
                self._backend.execute(
                    f"CREATE INDEX IF NOT EXISTS {self.name}_idx_{safe_field} "
                    f"ON {self.name}({safe_field})"
                )

            # Use _maybe_commit to respect transaction state
            self._maybe_commit()

    @staticmethod
    def _sanitize_field_name(field: str) -> str:
        """Convert field name to valid SQL identifier."""
        return "".join(c if c.isalnum() else "_" for c in field)

    def _maybe_commit(self) -> None:
        """Commit if not in a transaction (delegates to parent database)."""
        self._backend.maybe_commit()

    def _placeholder(self) -> str:
        """Get parameter placeholder for current dialect."""
        return self._dialect.placeholder

    def insert(self, document: dict[str, Any]) -> int:
        """
        Insert a document into this collection.

        Args:
            document: Dictionary to insert

        Returns:
            The ID of the inserted document

        Raises:
            TypeError: If document is not a dict
        """
        if not isinstance(document, dict):
            msg = "Must insert a dict"
            raise TypeError(msg)

        with self._write_lock:
            query = self._dialect.insert_returning_id(self.name)
            cursor = self._backend.execute(query, (json.dumps(document),))

            # Get the inserted ID
            doc_id = self._backend.get_last_insert_id(cursor)

            self._maybe_commit()
            return doc_id

    def insert_many(self, document_list: list[dict[str, Any]]) -> list[int]:
        """
        Insert multiple documents into this collection.

        Args:
            document_list: List of documents to insert

        Returns:
            List of IDs of the inserted documents

        Raises:
            TypeError: If not a list of dicts
        """
        if not isinstance(document_list, list) or not all(
            isinstance(doc, dict) for doc in document_list
        ):
            msg = "Must insert a list of dicts"
            raise TypeError(msg)

        with self._write_lock:
            # Get current max ID
            cursor = self._backend.execute(f"SELECT MAX(id) FROM {self.name}")
            row = self._backend.fetchone(cursor)
            last_id = row[0] if row and row[0] else 0

            # Insert all documents
            ph = self._placeholder()
            query = f"INSERT INTO {self.name} (data) VALUES ({ph})"
            self._backend.executemany(
                query, [(json.dumps(doc),) for doc in document_list]
            )
            self._maybe_commit()

            return list(range(last_id + 1, last_id + 1 + len(document_list)))

    def remove(self, key: str, value: Any) -> int:
        """
        Remove all documents where the given key matches the specified value.

        Args:
            key: The field name to match
            value: The value to match

        Returns:
            Number of documents removed

        Raises:
            ValueError: If key is empty or value is None
        """
        if not key or not isinstance(key, str):
            msg = "key must be a non-empty string"
            raise ValueError(msg)
        if value is None:
            msg = "value cannot be None"
            raise ValueError(msg)

        ph = self._placeholder()

        with self._write_lock:
            if key in self._indexed_fields:
                safe_field = self._sanitize_field_name(key)
                query = f"DELETE FROM {self.name} WHERE {safe_field} = {ph}"
                cursor = self._backend.execute(query, (value,))
            else:
                json_expr = self._dialect.json_extract("data", key)
                query = f"DELETE FROM {self.name} WHERE {json_expr} = {ph}"
                cursor = self._backend.execute(query, (value,))
            self._maybe_commit()
            return self._backend.get_rowcount(cursor)

    def update(self, id_key: str, id_value: Any, new_dict: dict[str, Any]) -> bool:
        """
        Update documents that match (id_key == id_value) by merging new_dict.

        Args:
            id_key: The field name to match
            id_value: The value to match
            new_dict: A dictionary of changes to apply

        Returns:
            True if at least one document was updated, False otherwise

        Raises:
            TypeError: If new_dict is not a dict
            ValueError: If id_key is invalid or id_value is None
        """
        if not isinstance(new_dict, dict):
            msg = "new_dict must be a dictionary"
            raise TypeError(msg)
        if not id_key or not isinstance(id_key, str):
            msg = "id_key must be a non-empty string"
            raise ValueError(msg)
        if id_value is None:
            msg = "id_value cannot be None"
            raise ValueError(msg)

        ph = self._placeholder()

        with self._write_lock:
            if id_key in self._indexed_fields:
                safe_field = self._sanitize_field_name(id_key)
                select_query = (
                    f"SELECT data FROM {self.name} WHERE {safe_field} = {ph}"
                )
                update_query = (
                    f"UPDATE {self.name} SET data = {ph} WHERE {safe_field} = {ph}"
                )
                cursor = self._backend.execute(select_query, (id_value,))
            else:
                json_expr = self._dialect.json_extract("data", id_key)
                select_query = f"SELECT data FROM {self.name} WHERE {json_expr} = {ph}"
                update_query = (
                    f"UPDATE {self.name} SET data = {ph} WHERE {json_expr} = {ph}"
                )
                cursor = self._backend.execute(select_query, (id_value,))

            documents = self._backend.fetchall(cursor)
            if not documents:
                return False

            for row in documents:
                document = json.loads(row[0])
                if not isinstance(document, dict):
                    continue
                document.update(new_dict)
                self._backend.execute(update_query, (json.dumps(document), id_value))

            self._maybe_commit()
            return True

    def purge(self) -> bool:
        """
        Remove all documents from this collection.

        Returns:
            True upon successful purge
        """
        with self._write_lock:
            self._backend.execute(f"DELETE FROM {self.name}")
            self._maybe_commit()
            return True

    def search(
        self, key: str, value: Any, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """
        Search documents in this collection.

        Args:
            key: Field name to search
            value: Value to match
            limit: Max results to return
            offset: Skip this many results

        Returns:
            List of matching documents
        """
        if not key or not isinstance(key, str):
            msg = "Key must be a non-empty string"
            raise ValueError(msg)

        ph = self._placeholder()

        # Check if field is indexed - if so, use direct column query
        if key in self._indexed_fields:
            safe_field = self._sanitize_field_name(key)
            query = (
                f"SELECT data FROM {self.name} WHERE {safe_field} = {ph} "
                f"LIMIT {ph} OFFSET {ph}"
            )
            cursor = self._backend.execute(query, (value, limit, offset))
        else:
            # Fall back to json_extract (no index)
            json_expr = self._dialect.json_extract("data", key)
            query = (
                f"SELECT data FROM {self.name} WHERE {json_expr} = {ph} "
                f"LIMIT {ph} OFFSET {ph}"
            )
            cursor = self._backend.execute(query, (value, limit, offset))

        return [json.loads(row[0]) for row in self._backend.fetchall(cursor)]

    def search_optimized(self, **filters) -> list[dict]:
        """
        Multi-field search with automatic index usage.

        Args:
            **filters: field=value pairs to search

        Returns:
            List of matching documents
        """
        if not filters:
            return self.all()

        ph = self._placeholder()

        # Build WHERE clause using indexed columns when possible
        where_parts: list[str] = []
        params: list[Any] = []

        for key, value in filters.items():
            if key in self._indexed_fields:
                safe_field = self._sanitize_field_name(key)
                where_parts.append(f"{safe_field} = {ph}")
            else:
                json_expr = self._dialect.json_extract("data", key)
                where_parts.append(f"{json_expr} = {ph}")
            params.append(value)

        where_clause = " AND ".join(where_parts)
        query = f"SELECT data FROM {self.name} WHERE {where_clause}"

        cursor = self._backend.execute(query, params)
        return [json.loads(row[0]) for row in self._backend.fetchall(cursor)]

    def all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all documents from this collection."""
        ph = self._placeholder()
        query = f"SELECT data FROM {self.name} LIMIT {ph} OFFSET {ph}"
        cursor = self._backend.execute(query, (limit, offset))
        return [json.loads(row[0]) for row in self._backend.fetchall(cursor)]

    def all_cursor(self, after_id: int | None = None, limit: int = 100) -> dict:
        """
        Cursor-based pagination for better performance on large datasets.

        Args:
            after_id: Continue from this document ID
            limit: Max results to return

        Returns:
            Dict with 'documents', 'next_cursor', 'has_more'
        """
        ph = self._placeholder()

        if after_id:
            query = (
                f"SELECT id, data FROM {self.name} WHERE id > {ph} "
                f"ORDER BY id LIMIT {ph}"
            )
            cursor = self._backend.execute(query, (after_id, limit + 1))
        else:
            query = f"SELECT id, data FROM {self.name} ORDER BY id LIMIT {ph}"
            cursor = self._backend.execute(query, (limit + 1,))

        rows = self._backend.fetchall(cursor)
        has_more = len(rows) > limit

        if has_more:
            rows = rows[:limit]

        documents = [json.loads(row[1]) for row in rows]
        next_cursor = rows[-1][0] if rows else None

        return {
            "documents": documents,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def search_pattern(
        self, key: str, pattern: str, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """
        Search documents matching a regex pattern.

        Args:
            key: The document field to match on
            pattern: The regex pattern to match
            limit: The maximum number of documents to return
            offset: The starting point for retrieval

        Returns:
            List of matching documents (dicts)

        Raises:
            ValueError: If the key or pattern is invalid
        """
        if not key or not isinstance(key, str):
            msg = "key must be a non-empty string"
            raise ValueError(msg)
        if not pattern or not isinstance(pattern, str):
            msg = "pattern must be a non-empty string"
            raise ValueError(msg)

        ph = self._placeholder()
        json_expr = self._dialect.json_extract("data", key)
        regex_expr = self._dialect.regex_match(json_expr)

        query = f"""
            SELECT data FROM {self.name}
            WHERE {regex_expr}
            LIMIT {ph} OFFSET {ph}
        """
        cursor = self._backend.execute(query, (pattern, limit, offset))
        return [json.loads(row[0]) for row in self._backend.fetchall(cursor)]

    def find_any(self, key: str, value_list: list[Any]) -> list[dict]:
        """
        Return documents where key matches any value in value_list.

        Args:
            key: The document field to match on
            value_list: A list of possible values

        Returns:
            A list of matching documents
        """
        if not value_list:
            return []

        ph = self._placeholder()
        placeholders = ", ".join([ph] * len(value_list))

        if key in self._indexed_fields:
            safe_field = self._sanitize_field_name(key)
            query = f"""
                SELECT DISTINCT data
                FROM {self.name}
                WHERE {safe_field} IN ({placeholders})
            """
            cursor = self._backend.execute(query, value_list)
        else:
            # For non-indexed fields, use json_each for array values
            # or direct json_extract for simple values
            json_expr = self._dialect.json_extract("data", key)
            query = f"""
                SELECT DISTINCT data
                FROM {self.name}
                WHERE {json_expr} IN ({placeholders})
            """
            cursor = self._backend.execute(query, value_list)

        return [json.loads(row[0]) for row in self._backend.fetchall(cursor)]

    def find_all(self, key: str, value_list: list[Any]) -> list[dict]:
        """
        Return documents where the key contains all values in value_list.

        Args:
            key: The field to match
            value_list: The required values to match

        Returns:
            A list of matching documents
        """
        if not value_list:
            return []

        ph = self._placeholder()
        placeholders = ", ".join([ph] * len(value_list))

        # This query works with JSON arrays in the data
        json_each_expr = self._dialect.json_array_each("data", f"$.{key}")

        query = f"""
            SELECT {self.name}.data
            FROM {self.name}, {json_each_expr} AS elems
            GROUP BY {self.name}.id
            HAVING COUNT(DISTINCT CASE WHEN elems.value IN ({placeholders}) THEN elems.value END) = {ph}
        """
        cursor = self._backend.execute(query, value_list + [len(value_list)])
        return [json.loads(row[0]) for row in self._backend.fetchall(cursor)]

    def explain(self, operation: str, *args) -> list[tuple]:
        """
        Show query execution plan for optimization.

        Args:
            operation: Method name ('search', 'all', etc.)
            *args: Arguments to the method

        Returns:
            List of query plan tuples from EXPLAIN QUERY PLAN
        """
        ph = self._placeholder()

        if operation == "search":
            key, value = args[0], args[1]
            if key in self._indexed_fields:
                safe_field = self._sanitize_field_name(key)
                query = (
                    f"EXPLAIN QUERY PLAN SELECT data FROM {self.name} "
                    f"WHERE {safe_field} = {ph}"
                )
                cursor = self._backend.execute(query, (value,))
            else:
                json_expr = self._dialect.json_extract("data", key)
                query = (
                    f"EXPLAIN QUERY PLAN SELECT data FROM {self.name} "
                    f"WHERE {json_expr} = {ph}"
                )
                cursor = self._backend.execute(query, (value,))
        elif operation == "all":
            query = f"EXPLAIN QUERY PLAN SELECT data FROM {self.name}"
            cursor = self._backend.execute(query)
        else:
            msg = f"Unknown operation: {operation}"
            raise ValueError(msg)

        return self._backend.fetchall(cursor)

    def get_indexed_fields(self) -> set[str]:
        """Return set of fields that have indexes."""
        return self._indexed_fields.copy()

    def stats(self) -> dict[str, Any]:
        """
        Get collection statistics.

        Returns:
            Dict with document count, etc.
        """
        cursor = self._backend.execute(f"SELECT COUNT(*) FROM {self.name}")
        row = self._backend.fetchone(cursor)
        doc_count = row[0] if row else 0

        return {
            "collection": self.name,
            "document_count": doc_count,
            "indexed_fields": list(self._indexed_fields),
        }

    def create_index(self, field: str) -> bool:
        """
        Dynamically create an index on a field.

        Args:
            field: Document field to index

        Returns:
            True if index was created
        """
        # Skip reserved column names
        if field in ("id", "_id"):
            return False  # Cannot index reserved column names

        if field in self._indexed_fields:
            return False  # Already indexed

        with self._write_lock:
            self._indexed_fields.add(field)
            safe_field = self._sanitize_field_name(field)
            json_expr = self._dialect.json_extract("data", field)
            gen_col = self._dialect.generated_column(safe_field, json_expr)

            try:
                self._backend.execute(
                    f"ALTER TABLE {self.name} ADD COLUMN {gen_col}"
                )
                self._backend.execute(
                    f"CREATE INDEX {self.name}_idx_{safe_field} "
                    f"ON {self.name}({safe_field})"
                )
                self._maybe_commit()
                return True
            except Exception:  # noqa: BLE001
                # Column already exists or can't be added
                # Must catch broad exception to handle different database backends
                self._indexed_fields.discard(field)
                return False
