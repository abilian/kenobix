"""
KenobiX ODM (Object Document Mapper)

A lightweight ODM layer for KenobiX using dataclasses and cattrs.

Example:
    from dataclasses import dataclass
    from kenobix import KenobiX
    from kenobix.odm import Document

    @dataclass
    class User(Document):
        name: str
        email: str
        age: int
        active: bool = True

    # Setup
    db = KenobiX('app.db', indexed_fields=['email', 'name'])
    Document.set_database(db)

    # Create
    user = User(name="Alice", email="alice@example.com", age=30)
    user.save()

    # Read
    alice = User.get(email="alice@example.com")
    users = User.filter(age=30)

    # Update
    alice.age = 31
    alice.save()

    # Delete
    alice.delete()
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from typing import Any, ClassVar, Self, TypeVar

import cattrs

from .kenobix import KenobiX  # noqa: TC001 - Used at runtime for db._connection, etc.

T = TypeVar("T", bound="Document")


class Document:
    """
    Base class for ODM models.

    All models must be dataclasses that inherit from Document.

    Attributes:
        _id: Primary key (auto-assigned after save)
        _db: Database instance (class variable)
        _converter: cattrs converter instance (class variable)

    Class Variables:
        _indexed_fields: Set via Meta class
        _primary_key: Primary key field name (default: '_id')

    Note:
        _id is NOT a dataclass field to avoid conflicts with subclass fields.
        It's stored in __dict__ and accessed via property.
    """

    # Class-level database connection
    _db: ClassVar[KenobiX | None] = None
    _converter: ClassVar[Any] = None

    # Configuration via inner Meta class
    class Meta:
        """Override in subclasses to configure ODM behavior."""

        indexed_fields: list[str] = []
        table_name: str | None = None  # Future: support multiple tables

    def __init__(self, **kwargs):
        """
        Initialize document.

        Note: Subclasses using @dataclass will have their __init__ generated,
        so they need to call super().__init__() in __post_init__.
        """
        # Store _id in instance dict (not as dataclass field)
        self._id: int | None = None

        if self._converter is None:
            self.__class__._converter = cattrs.Converter()

    def __post_init__(self):
        """Called by dataclass after __init__. Initialize ODM state."""
        # Initialize _id if not already set
        if not hasattr(self, "_id"):
            self._id: int | None = None

        if self._converter is None:
            self.__class__._converter = cattrs.Converter()

    @classmethod
    def set_database(cls, db: KenobiX):
        """
        Set the database instance for all Document models.

        Args:
            db: KenobiX database instance
        """
        cls._db = db

    @classmethod
    def _get_db(cls) -> KenobiX:
        """Get database instance, raising error if not set."""
        if cls._db is None:
            msg = "Database not initialized. Call Document.set_database(db) first."
            raise RuntimeError(msg)
        return cls._db

    @classmethod
    def transaction(cls):
        """
        Get transaction context manager from database.

        Example:
            with User.transaction():
                user1.save()
                user2.save()
                # Both committed together

        Returns:
            Transaction context manager
        """
        db = cls._get_db()
        return db.transaction()

    @classmethod
    def begin(cls):
        """Begin a transaction. Delegate to database."""
        db = cls._get_db()
        db.begin()

    @classmethod
    def commit(cls):
        """Commit current transaction. Delegate to database."""
        db = cls._get_db()
        db.commit()

    @classmethod
    def rollback(cls):
        """Rollback current transaction. Delegate to database."""
        db = cls._get_db()
        db.rollback()

    def _to_dict(self) -> dict[str, Any]:
        """
        Convert dataclass instance to dict for storage.

        Returns:
            Dictionary representation, excluding _id and other private fields
        """
        # Get all dataclass fields except private ones
        data = {}
        for field in fields(self):  # type: ignore[arg-type]  # self is a dataclass instance
            if not field.name.startswith("_"):
                value = getattr(self, field.name)
                data[field.name] = value

        return data

    @classmethod
    def _from_dict(cls, data: dict[str, Any], doc_id: int | None = None) -> Self:
        """
        Create instance from dictionary.

        Args:
            data: Dictionary data from database
            doc_id: Document ID

        Returns:
            Instance of the model class
        """
        # Use cattrs to structure the data into the dataclass
        try:
            # Remove _id from data if present (it's stored separately)
            data_copy = data.copy()
            data_copy.pop("_id", None)

            instance = cls._converter.structure(data_copy, cls)
            instance._id = doc_id
            return instance
        except Exception as e:
            msg = f"Failed to deserialize document: {e}"
            raise ValueError(msg) from e

    def save(self) -> Self:
        """
        Save the document to the database.

        If _id is None, performs insert. Otherwise, performs update.

        Returns:
            Self with _id set after insert
        """
        db = self._get_db()
        data = self._to_dict()

        if self._id is None:
            # Insert new document
            self._id = db.insert(data)
        else:
            # Update existing document by database row ID
            # We need to update directly using the rowid, not a field search
            with db._write_lock:
                db._connection.execute(
                    "UPDATE documents SET data = ? WHERE id = ?",
                    (json.dumps(data), self._id),
                )
                db._maybe_commit()

        return self

    @classmethod
    def get(cls, **filters) -> Self | None:
        """
        Get a single document matching the filters.

        Args:
            **filters: Field=value pairs to search

        Returns:
            Instance of the model or None if not found

        Example:
            user = User.get(email="alice@example.com")
        """
        results = cls.filter(**filters, limit=1)
        return results[0] if results else None

    @classmethod
    def get_by_id(cls, doc_id: int) -> Self | None:
        """
        Get document by primary key ID.

        Args:
            doc_id: Document ID

        Returns:
            Instance or None
        """
        db = cls._get_db()

        # Query by rowid directly
        cursor = db._connection.execute(
            "SELECT id, data FROM documents WHERE id = ?", (doc_id,)
        )
        row = cursor.fetchone()

        if row:
            data = json.loads(row[1])
            return cls._from_dict(data, doc_id=row[0])
        return None

    @classmethod
    def filter(cls, limit: int = 100, offset: int = 0, **filters) -> list[Self]:
        """
        Get all documents matching the filters.

        Args:
            limit: Maximum results to return
            offset: Number of results to skip
            **filters: Field=value pairs to search

        Returns:
            List of model instances

        Example:
            users = User.filter(age=30, active=True)
        """
        db = cls._get_db()

        if not filters:
            # Get all documents
            cursor = db._connection.execute(
                "SELECT id, data FROM documents LIMIT ? OFFSET ?", (limit, offset)
            )
        else:
            # Use search_optimized if available
            # Build query manually to get both id and data
            where_parts: list[str] = []
            params: list[Any] = []

            for key, value in filters.items():
                if key in db._indexed_fields:
                    safe_field = db._sanitize_field_name(key)
                    where_parts.append(f"{safe_field} = ?")
                else:
                    where_parts.append(f"json_extract(data, '$.{key}') = ?")
                params.append(value)

            where_clause = " AND ".join(where_parts)
            query = (
                f"SELECT id, data FROM documents WHERE {where_clause} LIMIT ? OFFSET ?"
            )
            params.extend([limit, offset])

            cursor = db._connection.execute(query, params)

        # Convert rows to instances
        instances = []
        for row in cursor.fetchall():
            doc_id, data_json = row
            data = json.loads(data_json)
            instance = cls._from_dict(data, doc_id=doc_id)
            instances.append(instance)

        return instances

    @classmethod
    def all(cls, limit: int = 100, offset: int = 0) -> list[Self]:
        """
        Get all documents.

        Args:
            limit: Maximum results
            offset: Number to skip

        Returns:
            List of model instances
        """
        return cls.filter(limit=limit, offset=offset)

    def delete(self) -> bool:
        """
        Delete this document from the database.

        Returns:
            True if deleted, False if not found

        Raises:
            RuntimeError: If document has no _id (not saved yet)
        """
        if self._id is None:
            msg = "Cannot delete unsaved document"
            raise RuntimeError(msg)

        db = self._get_db()

        with db._write_lock:
            cursor = db._connection.execute(
                "DELETE FROM documents WHERE id = ?", (self._id,)
            )
            db._maybe_commit()

        return cursor.rowcount > 0

    @classmethod
    def delete_many(cls, **filters) -> int:
        """
        Delete all documents matching the filters.

        Args:
            **filters: Field=value pairs to match

        Returns:
            Number of documents deleted

        Example:
            deleted = User.delete_many(active=False)
        """
        db = cls._get_db()

        if not filters:
            msg = "delete_many requires at least one filter"
            raise ValueError(msg)

        # Build WHERE clause
        where_parts: list[str] = []
        params: list[Any] = []

        for key, value in filters.items():
            if key in db._indexed_fields:
                safe_field = db._sanitize_field_name(key)
                where_parts.append(f"{safe_field} = ?")
            else:
                where_parts.append(f"json_extract(data, '$.{key}') = ?")
            params.append(value)

        where_clause = " AND ".join(where_parts)

        with db._write_lock:
            cursor = db._connection.execute(
                f"DELETE FROM documents WHERE {where_clause}", params
            )
            db._maybe_commit()

        return cursor.rowcount

    @classmethod
    def insert_many(cls, instances: list[Self]) -> list[Self]:
        """
        Insert multiple documents in a single transaction.

        Args:
            instances: List of model instances

        Returns:
            List of instances with _id set

        Example:
            users = [
                User(name="Alice", email="alice@example.com", age=30),
                User(name="Bob", email="bob@example.com", age=25),
            ]
            User.insert_many(users)
        """
        if not instances:
            return []

        db = cls._get_db()

        # Convert instances to dicts
        documents = [inst._to_dict() for inst in instances]

        # Insert and get IDs
        ids = db.insert_many(documents)

        # Update instances with IDs
        for inst, doc_id in zip(instances, ids, strict=False):
            inst._id = doc_id

        return instances

    @classmethod
    def count(cls, **filters) -> int:
        """
        Count documents matching the filters.

        Args:
            **filters: Field=value pairs

        Returns:
            Number of matching documents

        Example:
            active_users = User.count(active=True)
        """
        db = cls._get_db()

        if not filters:
            cursor = db._connection.execute("SELECT COUNT(*) FROM documents")
        else:
            where_parts: list[str] = []
            params: list[Any] = []

            for key, value in filters.items():
                if key in db._indexed_fields:
                    safe_field = db._sanitize_field_name(key)
                    where_parts.append(f"{safe_field} = ?")
                else:
                    where_parts.append(f"json_extract(data, '$.{key}') = ?")
                params.append(value)

            where_clause = " AND ".join(where_parts)
            cursor = db._connection.execute(
                f"SELECT COUNT(*) FROM documents WHERE {where_clause}", params
            )

        return cursor.fetchone()[0]

    def __repr__(self) -> str:
        """String representation of the document."""
        class_name = self.__class__.__name__

        # Get all dataclass fields
        if is_dataclass(self):
            fields_str = ", ".join(
                f"{f.name}={getattr(self, f.name)!r}"
                for f in fields(self)
                if not f.name.startswith("_")
            )
            return f"{class_name}(_id={self._id}, {fields_str})"
        # Fallback for non-dataclass subclasses
        return f"{class_name}(_id={self._id})"
