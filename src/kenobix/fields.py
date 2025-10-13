"""
KenobiX ODM Relationship Fields

Provides descriptor-based relationship fields for ODM models:
- ForeignKey: Many-to-one relationships
- OneToOne: One-to-one relationships (future)
- RelatedSet: One-to-many relationships (future)
- ManyToMany: Many-to-many relationships (future)

Example:
    from dataclasses import dataclass
    from kenobix.odm import Document
    from kenobix.fields import ForeignKey

    @dataclass
    class User(Document):
        class Meta:
            collection_name = "users"
            indexed_fields = ["user_id"]

        user_id: int
        name: str

    @dataclass
    class Order(Document):
        class Meta:
            collection_name = "orders"
            indexed_fields = ["order_id", "user_id"]

        order_id: int
        user_id: int  # Foreign key field
        amount: float

        # Relationship declaration
        user: ForeignKey[User] = ForeignKey("user_id", User)

    # Usage - transparent lazy loading
    order = Order.get(order_id=101)
    print(order.user.name)  # Lazy loads User when accessed
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from typing import Any

    from .odm import Document

T = TypeVar("T", bound="Document")


class ForeignKey(Generic[T]):
    """
    Descriptor for many-to-one relationships.

    Implements lazy loading with caching to minimize database queries.

    Attributes:
        foreign_key_field: Name of the field containing the foreign key value
        model: Target model class
        optional: If True, None values are allowed; if False, raises error
        cache_attr: Internal cache attribute name

    Example:
        @dataclass
        class Order(Document):
            order_id: int
            user_id: int
            amount: float

            user: ForeignKey[User] = ForeignKey("user_id", User)

        order = Order.get(order_id=101)
        user = order.user  # Lazy loads User from database
        user_again = order.user  # Returns cached value
    """

    def __init__(
        self,
        foreign_key_field: str,
        model: type[T],
        optional: bool = False,
        related_field: str | None = None,
    ):
        """
        Initialize ForeignKey descriptor.

        Args:
            foreign_key_field: Name of the field storing the foreign key value
            model: Target Document model class
            optional: If True, allow None values; if False, raise error on None
            related_field: Field name in related model to query by.
                          If None, uses foreign_key_field (assumes same name)
        """
        self.foreign_key_field = foreign_key_field
        self.model = model
        self.optional = optional
        self.related_field = related_field or foreign_key_field
        self.cache_attr: str | None = None

    def __set_name__(self, owner: type, name: str):
        """
        Called when descriptor is assigned to class attribute.

        Stores the cache attribute name for this relationship.

        Args:
            owner: Owner class (Document subclass)
            name: Attribute name
        """
        # Cache attribute name: _cache_user for "user" relationship
        self.cache_attr = f"_cache_{name}"

    def __get__(self, instance: Document | None, owner: type) -> T | ForeignKey | None:
        """
        Get related object, loading from database if needed.

        Args:
            instance: Document instance (None when accessed on class)
            owner: Owner class

        Returns:
            Related object, None (if optional), or descriptor itself (class access)

        Raises:
            ValueError: If foreign key is None and optional=False
        """
        # Class access: return descriptor itself
        if instance is None:
            return self

        # Check cache first
        cached = getattr(instance, self.cache_attr, None)
        if cached is not None:
            return cached

        # Get foreign key value from instance
        fk_value = getattr(instance, self.foreign_key_field)

        # Handle None values
        if fk_value is None:
            if self.optional:
                return None
            msg = (
                f"Foreign key '{self.foreign_key_field}' is None. "
                f"Use optional=True if this is valid."
            )
            raise ValueError(msg)

        # Load related object from database
        # Query by the related field in the target model
        related = self.model.get(**{self.related_field: fk_value})

        if related is None and not self.optional:
            msg = (
                f"Related {self.model.__name__} with "
                f"{self.related_field}={fk_value} not found"
            )
            raise ValueError(msg)

        # Cache the result
        setattr(instance, self.cache_attr, related)
        return related

    def __set__(self, instance: Document, value: T | None):
        """
        Set related object and update foreign key field.

        Args:
            instance: Document instance
            value: Related object or None

        Raises:
            ValueError: If value is None and optional=False
        """
        # Skip if value is a ForeignKey descriptor (happens during dataclass __init__)
        if isinstance(value, ForeignKey):
            return

        # Handle None assignment
        if value is None:
            if not self.optional:
                msg = f"Cannot set {self.model.__name__} to None (not optional)"
                raise ValueError(msg)
            setattr(instance, self.foreign_key_field, None)
            setattr(instance, self.cache_attr, None)
            return

        # Extract foreign key value from related object
        fk_value = getattr(value, self.foreign_key_field)

        # Update foreign key field
        setattr(instance, self.foreign_key_field, fk_value)

        # Cache the related object
        setattr(instance, self.cache_attr, value)
