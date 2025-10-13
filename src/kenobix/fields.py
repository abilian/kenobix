"""
KenobiX ODM Relationship Fields

Provides descriptor-based relationship fields for ODM models:
- ForeignKey: Many-to-one relationships
- RelatedSet: One-to-many relationships
- OneToOne: One-to-one relationships (future)
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
        # Will be set by __set_name__ when descriptor is attached to class
        self.cache_attr: str = ""

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
        cached: T | None = getattr(instance, self.cache_attr, None)
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
            model_name = self.model.__name__  # type: ignore[misc]
            msg = f"Related {model_name} with {self.related_field}={fk_value} not found"
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
                model_name = self.model.__name__  # type: ignore[misc]
                msg = f"Cannot set {model_name} to None (not optional)"
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


class RelatedSetManager(Generic[T]):
    """
    Manager for one-to-many relationships.

    Provides methods to query, filter, and manage the related object collection.

    Attributes:
        instance: Parent document instance
        related_model: Related model class
        foreign_key_field: Field in related model that points to parent
        local_field: Field in parent model that foreign key references
    """

    def __init__(
        self,
        instance: Document,
        related_model: type[T],
        foreign_key_field: str,
        local_field: str,
    ):
        """
        Initialize RelatedSetManager.

        Args:
            instance: Parent document instance
            related_model: Related model class
            foreign_key_field: Field in related model storing the foreign key
            local_field: Field in parent model that foreign key references
        """
        self.instance = instance
        self.related_model = related_model
        self.foreign_key_field = foreign_key_field
        self.local_field = local_field
        self._cache: list[T] | None = None

    def all(self, limit: int = 100) -> list[T]:
        """
        Get all related objects.

        Args:
            limit: Maximum number of objects to return

        Returns:
            List of related objects
        """
        # Get the value of the local field (e.g., user_id)
        local_value = getattr(self.instance, self.local_field)

        if local_value is None:
            return []

        # Query related model by foreign key field
        return self.related_model.filter(
            **{self.foreign_key_field: local_value}, limit=limit
        )

    def filter(self, limit: int = 100, **filters) -> list[T]:
        """
        Filter related objects by additional criteria.

        Args:
            limit: Maximum number of objects to return
            **filters: Additional filter criteria

        Returns:
            List of filtered related objects
        """
        # Get the value of the local field
        local_value = getattr(self.instance, self.local_field)

        if local_value is None:
            return []

        # Combine foreign key filter with additional filters
        all_filters = {self.foreign_key_field: local_value, **filters}

        return self.related_model.filter(**all_filters, limit=limit)

    def count(self) -> int:
        """
        Count related objects.

        Returns:
            Number of related objects
        """
        local_value = getattr(self.instance, self.local_field)

        if local_value is None:
            return 0

        return self.related_model.count(**{self.foreign_key_field: local_value})

    def add(self, obj: T) -> None:
        """
        Add an object to the related set.

        Updates the foreign key field of the object and saves it.

        Args:
            obj: Related object to add
        """
        # Get the local field value
        local_value = getattr(self.instance, self.local_field)

        # Set the foreign key field on the related object
        setattr(obj, self.foreign_key_field, local_value)

        # Save the related object
        obj.save()

        # Invalidate cache
        self._cache = None

    def remove(self, obj: T) -> None:
        """
        Remove an object from the related set.

        Sets the foreign key field to None and saves the object.

        Args:
            obj: Related object to remove
        """
        # Set foreign key to None
        setattr(obj, self.foreign_key_field, None)

        # Save the related object
        obj.save()

        # Invalidate cache
        self._cache = None

    def clear(self) -> None:
        """
        Remove all objects from the related set.

        Sets all foreign key fields to None.
        """
        # Get all related objects
        related_objects = self.all(limit=10000)

        # Update each one
        for obj in related_objects:
            setattr(obj, self.foreign_key_field, None)
            obj.save()

        # Invalidate cache
        self._cache = None

    def __iter__(self):
        """Iterate over related objects."""
        return iter(self.all())

    def __len__(self) -> int:
        """Get count of related objects."""
        return self.count()


class RelatedSet(Generic[T]):
    """
    Descriptor for one-to-many relationships.

    Represents the "many" side of a one-to-many relationship,
    providing access to a collection of related objects.

    Attributes:
        related_model: Related model class
        foreign_key_field: Field in related model that points to parent
        local_field: Field in parent model that foreign key references

    Example:
        @dataclass
        class User(Document):
            user_id: int
            name: str

            # One user has many orders
            orders: RelatedSet[Order] = field(
                default=RelatedSet(Order, "user_id"),
                init=False,
                repr=False,
                compare=False
            )

        @dataclass
        class Order(Document):
            order_id: int
            user_id: int
            amount: float

            # Many orders belong to one user
            user: ForeignKey[User] = field(
                default=ForeignKey("user_id", User),
                init=False,
                repr=False,
                compare=False
            )

        user = User.get(user_id=1)
        orders = user.orders.all()  # Get all orders
        count = user.orders.count()  # Count orders
        user.orders.add(new_order)  # Add an order
    """

    def __init__(
        self,
        related_model: type[T],
        foreign_key_field: str,
        local_field: str | None = None,
    ):
        """
        Initialize RelatedSet descriptor.

        Args:
            related_model: Related model class
            foreign_key_field: Field in related model storing the foreign key
            local_field: Field in parent model that foreign key references.
                        If None, will be inferred from foreign_key_field
        """
        self.related_model = related_model
        self.foreign_key_field = foreign_key_field
        self.local_field = local_field or foreign_key_field
        self.cache_attr: str = ""

    def __set_name__(self, owner: type, name: str):
        """
        Called when descriptor is assigned to class attribute.

        Args:
            owner: Owner class (Document subclass)
            name: Attribute name
        """
        # Cache attribute name for manager instances
        self.cache_attr = f"_cache_{name}_manager"

    def __get__(
        self, instance: Document | None, owner: type
    ) -> RelatedSetManager[T] | RelatedSet:
        """
        Get related set manager.

        Args:
            instance: Document instance (None when accessed on class)
            owner: Owner class

        Returns:
            RelatedSetManager for instance access, descriptor for class access
        """
        # Class access: return descriptor itself
        if instance is None:
            return self

        # Check cache first
        cached: RelatedSetManager[T] | None = getattr(instance, self.cache_attr, None)
        if cached is not None:
            return cached

        # Create manager
        manager = RelatedSetManager(
            instance, self.related_model, self.foreign_key_field, self.local_field
        )

        # Cache the manager
        setattr(instance, self.cache_attr, manager)

        return manager

    def __set__(self, instance: Document, value: Any):
        """
        Prevent direct assignment to RelatedSet.

        Args:
            instance: Document instance
            value: Value being assigned

        Raises:
            AttributeError: Always, as RelatedSet cannot be directly assigned
        """
        # Skip if value is a RelatedSet descriptor (happens during dataclass __init__)
        if isinstance(value, RelatedSet):
            return

        msg = "Cannot directly assign to RelatedSet. Use add() or remove() methods."
        raise AttributeError(msg)
