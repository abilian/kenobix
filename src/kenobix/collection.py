"""
Collection - A single collection (table) within a KenobiX database.

Each collection operates on its own table with its own schema and indexes.
"""

from __future__ import annotations

import json
import sqlite3
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

        # Share connection and locks from parent database
        self._connection = db._connection
        self._write_lock = db._write_lock

        # Initialize table
        self._initialize_table()

    def _initialize_table(self) -> None:
        """Create table with generated columns for indexed fields."""
        with self._write_lock:
            # Build CREATE TABLE with generated columns
            columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "data TEXT NOT NULL"]

            # Add generated columns for indexed fields
            # Skip "id" and "_id" as they're reserved for the primary key
            for field in self._indexed_fields:
                if field in ("id", "_id"):
                    continue  # Skip reserved column names
                safe_field = self._sanitize_field_name(field)
                columns.append(
                    f"{safe_field} TEXT GENERATED ALWAYS AS "
                    f"(json_extract(data, '$.{field}')) VIRTUAL"
                )

            create_table = (
                f"CREATE TABLE IF NOT EXISTS {self.name} (\n    {', '.join(columns)}\n)"
            )
            self._connection.execute(create_table)

            # Create indexes on generated columns
            # Skip "id" and "_id" as they're reserved for the primary key
            for field in self._indexed_fields:
                if field in ("id", "_id"):
                    continue  # Skip reserved column names
                safe_field = self._sanitize_field_name(field)
                self._connection.execute(
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
        if not self.db._in_transaction:
            self._connection.commit()

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
            cursor = self._connection.execute(
                f"INSERT INTO {self.name} (data) VALUES (?)",
                (json.dumps(document),),
            )
            self._maybe_commit()
            assert cursor.lastrowid is not None
            return cursor.lastrowid

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
            cursor = self._connection.execute(f"SELECT MAX(id) FROM {self.name}")
            last_id = cursor.fetchone()[0] or 0

            self._connection.executemany(
                f"INSERT INTO {self.name} (data) VALUES (?)",
                [(json.dumps(doc),) for doc in document_list],
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

        with self._write_lock:
            if key in self._indexed_fields:
                safe_field = self._sanitize_field_name(key)
                query = f"DELETE FROM {self.name} WHERE {safe_field} = ?"
                result = self._connection.execute(query, (value,))
            else:
                query = (
                    f"DELETE FROM {self.name} WHERE json_extract(data, '$.' || ?) = ?"
                )
                result = self._connection.execute(query, (key, value))
            self._maybe_commit()
            return result.rowcount

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

        with self._write_lock:
            if id_key in self._indexed_fields:
                safe_field = self._sanitize_field_name(id_key)
                select_query = f"SELECT data FROM {self.name} WHERE {safe_field} = ?"
                update_query = f"UPDATE {self.name} SET data = ? WHERE {safe_field} = ?"
                cursor = self._connection.execute(select_query, (id_value,))
            else:
                select_query = (
                    f"SELECT data FROM {self.name} "
                    "WHERE json_extract(data, '$.' || ?) = ?"
                )
                update_query = (
                    f"UPDATE {self.name} SET data = ? "
                    "WHERE json_extract(data, '$.' || ?) = ?"
                )
                cursor = self._connection.execute(select_query, (id_key, id_value))

            documents = cursor.fetchall()
            if not documents:
                return False

            for row in documents:
                document = json.loads(row[0])
                if not isinstance(document, dict):
                    continue
                document.update(new_dict)

                if id_key in self._indexed_fields:
                    self._connection.execute(
                        update_query, (json.dumps(document), id_value)
                    )
                else:
                    self._connection.execute(
                        update_query, (json.dumps(document), id_key, id_value)
                    )

            self._maybe_commit()
            return True

    def purge(self) -> bool:
        """
        Remove all documents from this collection.

        Returns:
            True upon successful purge
        """
        with self._write_lock:
            self._connection.execute(f"DELETE FROM {self.name}")
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

        # Check if field is indexed - if so, use direct column query
        if key in self._indexed_fields:
            safe_field = self._sanitize_field_name(key)
            query = (
                f"SELECT data FROM {self.name} WHERE {safe_field} = ? LIMIT ? OFFSET ?"
            )
            cursor = self._connection.execute(query, (value, limit, offset))
        else:
            # Fall back to json_extract (no index)
            query = (
                f"SELECT data FROM {self.name} "
                "WHERE json_extract(data, '$.' || ?) = ? "
                "LIMIT ? OFFSET ?"
            )
            cursor = self._connection.execute(query, (key, value, limit, offset))

        return [json.loads(row[0]) for row in cursor.fetchall()]

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

        # Build WHERE clause using indexed columns when possible
        where_parts: list[str] = []
        params: list[Any] = []

        for key, value in filters.items():
            if key in self._indexed_fields:
                safe_field = self._sanitize_field_name(key)
                where_parts.append(f"{safe_field} = ?")
            else:
                where_parts.append(f"json_extract(data, '$.{key}') = ?")
            params.append(value)

        where_clause = " AND ".join(where_parts)
        query = f"SELECT data FROM {self.name} WHERE {where_clause}"

        cursor = self._connection.execute(query, params)
        return [json.loads(row[0]) for row in cursor.fetchall()]

    def all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all documents from this collection."""
        query = f"SELECT data FROM {self.name} LIMIT ? OFFSET ?"
        cursor = self._connection.execute(query, (limit, offset))
        return [json.loads(row[0]) for row in cursor.fetchall()]

    def all_cursor(self, after_id: int | None = None, limit: int = 100) -> dict:
        """
        Cursor-based pagination for better performance on large datasets.

        Args:
            after_id: Continue from this document ID
            limit: Max results to return

        Returns:
            Dict with 'documents', 'next_cursor', 'has_more'
        """
        if after_id:
            query = f"SELECT id, data FROM {self.name} WHERE id > ? ORDER BY id LIMIT ?"
            cursor = self._connection.execute(query, (after_id, limit + 1))
        else:
            query = f"SELECT id, data FROM {self.name} ORDER BY id LIMIT ?"
            cursor = self._connection.execute(query, (limit + 1,))

        rows = cursor.fetchall()
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

        query = f"""
            SELECT data FROM {self.name}
            WHERE json_extract(data, '$.' || ?) REGEXP ?
            LIMIT ? OFFSET ?
        """
        cursor = self._connection.execute(query, (key, pattern, limit, offset))
        return [json.loads(row[0]) for row in cursor.fetchall()]

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

        placeholders = ", ".join(["?"] * len(value_list))

        if key in self._indexed_fields:
            safe_field = self._sanitize_field_name(key)
            query = f"""
                SELECT DISTINCT data
                FROM {self.name}
                WHERE {safe_field} IN ({placeholders})
            """
            cursor = self._connection.execute(query, value_list)
        else:
            query = f"""
                SELECT DISTINCT {self.name}.data
                FROM {self.name}, json_each({self.name}.data, '$.' || ?)
                WHERE json_each.value IN ({placeholders})
            """
            cursor = self._connection.execute(query, [key] + value_list)

        return [json.loads(row[0]) for row in cursor.fetchall()]

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

        placeholders = ", ".join(["?"] * len(value_list))

        query = f"""
            SELECT {self.name}.data
            FROM {self.name}
            WHERE (
                SELECT COUNT(DISTINCT value)
                FROM json_each({self.name}.data, '$.' || ?)
                WHERE value IN ({placeholders})
            ) = ?
        """
        cursor = self._connection.execute(query, [key] + value_list + [len(value_list)])
        return [json.loads(row[0]) for row in cursor.fetchall()]

    def explain(self, operation: str, *args) -> list[tuple]:
        """
        Show query execution plan for optimization.

        Args:
            operation: Method name ('search', 'all', etc.)
            *args: Arguments to the method

        Returns:
            List of query plan tuples from EXPLAIN QUERY PLAN
        """
        if operation == "search":
            key, value = args[0], args[1]
            if key in self._indexed_fields:
                safe_field = self._sanitize_field_name(key)
                query = (
                    f"EXPLAIN QUERY PLAN SELECT data FROM {self.name} "
                    f"WHERE {safe_field} = ?"
                )
                cursor = self._connection.execute(query, (value,))
            else:
                query = (
                    f"EXPLAIN QUERY PLAN SELECT data FROM {self.name} "
                    "WHERE json_extract(data, '$.' || ?) = ?"
                )
                cursor = self._connection.execute(query, (key, value))
        elif operation == "all":
            query = f"EXPLAIN QUERY PLAN SELECT data FROM {self.name}"
            cursor = self._connection.execute(query)
        else:
            msg = f"Unknown operation: {operation}"
            raise ValueError(msg)

        return cursor.fetchall()

    def get_indexed_fields(self) -> set[str]:
        """Return set of fields that have indexes."""
        return self._indexed_fields.copy()

    def stats(self) -> dict[str, Any]:
        """
        Get collection statistics.

        Returns:
            Dict with document count, etc.
        """
        cursor = self._connection.execute(f"SELECT COUNT(*) FROM {self.name}")
        doc_count = cursor.fetchone()[0]

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

            try:
                self._connection.execute(
                    f"ALTER TABLE {self.name} ADD COLUMN {safe_field} TEXT "
                    f"GENERATED ALWAYS AS (json_extract(data, '$.{field}')) VIRTUAL"
                )
                self._connection.execute(
                    f"CREATE INDEX {self.name}_idx_{safe_field} "
                    f"ON {self.name}({safe_field})"
                )
                self._maybe_commit()
                return True
            except sqlite3.OperationalError:
                # Column already exists or can't be added
                return False
