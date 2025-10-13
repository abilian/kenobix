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
import re
from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Self, TypeVar

import cattrs

from .kenobix import KenobiX  # noqa: TC001 - Used at runtime for db._connection, etc.

if TYPE_CHECKING:
    from .collection import Collection

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
        _collection_name: Collection name (auto-derived from class name or from Meta)
        _indexed_fields: Fields to index (from Meta.indexed_fields)

    Example with Meta:
        @dataclass
        class User(Document):
            class Meta:
                collection_name = "users"  # Optional, defaults to "users"
                indexed_fields = ["email", "user_id"]

            name: str
            email: str

    Note:
        _id is NOT a dataclass field to avoid conflicts with subclass fields.
        It's stored in __dict__ and accessed via property.
    """

    # Class-level database connection (shared across all models)
    _db: ClassVar[KenobiX | None] = None
    _converter: ClassVar[Any] = None

    # Per-class configuration (set via __init_subclass__)
    _collection_name: ClassVar[str] = "documents"  # Default for backward compatibility
    _indexed_fields_list: ClassVar[list[str]] = []  # From Meta.indexed_fields

    # Configuration via inner Meta class
    class Meta:
        """Override in subclasses to configure ODM behavior."""

        collection_name: str | None = None  # If None, auto-derived from class name
        indexed_fields: list[str] = []

    def __init_subclass__(cls, **kwargs):
        """
        Called when a subclass is created. Process Meta class configuration.

        This method extracts configuration from the subclass's Meta class
        and sets up collection name and indexed fields.
        """
        super().__init_subclass__(**kwargs)

        # Process Meta class if present
        if hasattr(cls, "Meta"):
            meta = cls.Meta
            # Get collection name from Meta or derive from class name
            if hasattr(meta, "collection_name") and meta.collection_name:
                cls._collection_name = meta.collection_name
            else:
                # Auto-derive: User → users, Order → orders
                cls._collection_name = cls._pluralize(cls.__name__)

            # Get indexed fields from Meta
            if hasattr(meta, "indexed_fields"):
                cls._indexed_fields_list = list(meta.indexed_fields)
            else:
                cls._indexed_fields_list = []
        else:
            # No Meta class: use defaults
            # Base Document class uses "documents" for backward compatibility
            # Subclasses without Meta get auto-derived names
            if cls.__name__ != "Document":
                cls._collection_name = cls._pluralize(cls.__name__)
                cls._indexed_fields_list = []

    @staticmethod
    def _pluralize(word: str) -> str:
        """
        Convert singular class name to plural collection name.

        Examples:
            User → users
            Order → orders
            Category → categories
            Address → addresses
            Person → persons (simple rules, not perfect English)

        Args:
            word: Singular word (class name)

        Returns:
            Plural form
        """
        word_lower = word.lower()

        # Special cases
        if word_lower.endswith("y"):
            # Category → categories
            return word_lower[:-1] + "ies"
        if word_lower.endswith(("s", "x", "z", "ch", "sh")):
            # Address → addresses, Box → boxes
            return word_lower + "es"
        # User → users, Order → orders
        return word_lower + "s"

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
    def _get_collection(cls) -> Collection:
        """
        Get the collection for this model class.

        Each model class gets its own collection based on _collection_name.
        The collection is created with indexed fields from Meta.indexed_fields.

        Returns:
            Collection instance for this model

        Example:
            User._get_collection()  # Returns "users" collection
            Order._get_collection()  # Returns "orders" collection
        """
        db = cls._get_db()
        # Get or create collection with this model's indexed fields
        return db.collection(
            cls._collection_name, indexed_fields=cls._indexed_fields_list
        )

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
        from .fields import (  # Import here to avoid circular import  # noqa: PLC0415
            ForeignKey,
            RelatedSet,
        )

        # Get all dataclass fields except private ones
        data = {}
        for field in fields(self):  # type: ignore[arg-type]  # self is a dataclass instance
            if not field.name.startswith("_"):
                # Check if field's default is a descriptor (ForeignKey, RelatedSet, etc.)
                # If so, skip it - descriptors are not data fields
                class_attr = getattr(self.__class__, field.name, None)
                if isinstance(class_attr, (ForeignKey, RelatedSet)):
                    # Skip descriptor fields
                    continue

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
        from .fields import (  # Import here to avoid circular import  # noqa: PLC0415
            ForeignKey,
            RelatedSet,
        )

        # Use cattrs to structure the data into the dataclass
        try:
            # Remove _id from data if present (it's stored separately)
            data_copy = data.copy()
            data_copy.pop("_id", None)

            # Get descriptor fields (ForeignKey, RelatedSet, etc.) to skip during deserialization
            descriptor_fields = set()
            for field_name in dir(cls):
                if not field_name.startswith("_"):
                    class_attr = getattr(cls, field_name, None)
                    if isinstance(class_attr, (ForeignKey, RelatedSet)):
                        descriptor_fields.add(field_name)

            # Filter out descriptor fields from data
            data_filtered = {
                k: v for k, v in data_copy.items() if k not in descriptor_fields
            }

            instance = cls._converter.structure(data_filtered, cls)
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
        collection = self._get_collection()
        data = self._to_dict()

        if self._id is None:
            # Insert new document
            self._id = collection.insert(data)
        else:
            # Update existing document by database row ID
            # We need to update directly using the rowid, not a field search
            db = self._get_db()
            with db._write_lock:
                db._connection.execute(
                    f"UPDATE {collection.name} SET data = ? WHERE id = ?",
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
        collection = cls._get_collection()
        db = cls._get_db()

        # Query by rowid directly
        cursor = db._connection.execute(
            f"SELECT id, data FROM {collection.name} WHERE id = ?", (doc_id,)
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
        collection = cls._get_collection()
        db = cls._get_db()

        if not filters:
            # Get all documents
            cursor = db._connection.execute(
                f"SELECT id, data FROM {collection.name} LIMIT ? OFFSET ?",
                (limit, offset),
            )
        else:
            # Build query manually to get both id and data
            where_parts: list[str] = []
            params: list[Any] = []

            # Use collection's indexed fields
            indexed_fields = collection.get_indexed_fields()

            for key, value in filters.items():
                if key in indexed_fields:
                    safe_field = db._sanitize_field_name(key)
                    where_parts.append(f"{safe_field} = ?")
                else:
                    where_parts.append(f"json_extract(data, '$.{key}') = ?")
                params.append(value)

            where_clause = " AND ".join(where_parts)
            query = f"SELECT id, data FROM {collection.name} WHERE {where_clause} LIMIT ? OFFSET ?"
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

        collection = self._get_collection()
        db = self._get_db()

        with db._write_lock:
            cursor = db._connection.execute(
                f"DELETE FROM {collection.name} WHERE id = ?", (self._id,)
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
        collection = cls._get_collection()
        db = cls._get_db()

        if not filters:
            msg = "delete_many requires at least one filter"
            raise ValueError(msg)

        # Build WHERE clause
        where_parts: list[str] = []
        params: list[Any] = []

        # Use collection's indexed fields
        indexed_fields = collection.get_indexed_fields()

        for key, value in filters.items():
            if key in indexed_fields:
                safe_field = db._sanitize_field_name(key)
                where_parts.append(f"{safe_field} = ?")
            else:
                where_parts.append(f"json_extract(data, '$.{key}') = ?")
            params.append(value)

        where_clause = " AND ".join(where_parts)

        with db._write_lock:
            cursor = db._connection.execute(
                f"DELETE FROM {collection.name} WHERE {where_clause}", params
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

        collection = cls._get_collection()

        # Convert instances to dicts
        documents = [inst._to_dict() for inst in instances]

        # Insert and get IDs
        ids = collection.insert_many(documents)

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
        collection = cls._get_collection()
        db = cls._get_db()

        if not filters:
            cursor = db._connection.execute(f"SELECT COUNT(*) FROM {collection.name}")
        else:
            where_parts: list[str] = []
            params: list[Any] = []

            # Use collection's indexed fields
            indexed_fields = collection.get_indexed_fields()

            for key, value in filters.items():
                if key in indexed_fields:
                    safe_field = db._sanitize_field_name(key)
                    where_parts.append(f"{safe_field} = ?")
                else:
                    where_parts.append(f"json_extract(data, '$.{key}') = ?")
                params.append(value)

            where_clause = " AND ".join(where_parts)
            cursor = db._connection.execute(
                f"SELECT COUNT(*) FROM {collection.name} WHERE {where_clause}", params
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
