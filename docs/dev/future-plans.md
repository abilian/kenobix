# KenobiX Future Plans

This document outlines planned features for future versions of KenobiX.

## Advanced Relationship Features

### Eager Loading / Prefetch

**Priority**: HIGH (solves N+1 query problem)

**Goal**: Batch-load relationships to avoid N+1 queries

```python
# Avoid N+1 queries
orders = Order.filter(amount__gt=100).prefetch_related("user")

for order in orders:
    print(order.user.name)  # No additional query - all users preloaded
```

**Implementation Approach:**

```python
class PrefetchDescriptor:
    """Marks a field for prefetching."""
    def __init__(self, relationship_name: str):
        self.relationship_name = relationship_name

# Add prefetch_related to ODM query methods
@classmethod
def filter(cls, prefetch: list[str] | None = None, **filters):
    instances = cls._raw_filter(**filters)

    if prefetch:
        for field_name in prefetch:
            # Batch load all related objects
            _prefetch_related(instances, field_name)

    return instances

def _prefetch_related(instances, field_name):
    """Batch load related objects for all instances."""
    descriptor = getattr(type(instances[0]), field_name)

    if isinstance(descriptor, ForeignKey):
        # Collect all foreign key values
        fk_values = [getattr(inst, descriptor.foreign_key_field)
                     for inst in instances]

        # Batch load all related objects
        related_objs = descriptor.model.filter(
            **{f"{descriptor.foreign_key_field}__in": fk_values}
        )

        # Build lookup map
        lookup = {getattr(obj, descriptor.foreign_key_field): obj
                  for obj in related_objs}

        # Populate caches
        for inst in instances:
            fk_value = getattr(inst, descriptor.foreign_key_field)
            related = lookup.get(fk_value)
            setattr(inst, descriptor.cache_attr, related)
```

**Tasks:**
1. Implement `prefetch_related()` method on Document
2. Support ForeignKey prefetching
3. Support RelatedSet prefetching
4. Support ManyToMany prefetching
5. Handle nested prefetching (e.g., `order.user.profile`)
6. Write performance benchmarks
7. Add 15+ tests
8. Document with examples

---

### Select Related (Join-like Queries)

**Priority**: MEDIUM (alternative to prefetch)

**Goal**: Load related objects in single query (simulated joins)

```python
# Single query loads both Order and User
orders = Order.filter(amount__gt=100).select_related("user")

for order in orders:
    print(order.user.name)  # Already loaded, no query
```

**Implementation Approach:**
- Similar to prefetch but more optimized
- Pre-populate caches during initial query
- Works best for ForeignKey relationships

---

### Cascade Delete

**Priority**: MEDIUM (data integrity)

**Goal**: Automatically delete related objects

```python
@dataclass
class User(Document):
    user_id: int
    name: str

@dataclass
class Order(Document):
    order_id: int
    user_id: int

    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User, on_delete="CASCADE"),
        init=False,
        repr=False,
        compare=False
    )

# Delete user and all their orders
user.delete()  # Automatically deletes related orders
```

**Implementation Approach:**

```python
class ForeignKey:
    def __init__(self, foreign_key_field, model, optional=False,
                 on_delete="DO_NOTHING"):
        self.on_delete = on_delete  # CASCADE, SET_NULL, DO_NOTHING

# Modify Document.delete()
def delete(self):
    # Find all ForeignKey descriptors pointing to this model
    for model_class in all_document_models():
        for field_name, descriptor in get_foreign_keys(model_class):
            if descriptor.model == self.__class__:
                if descriptor.on_delete == "CASCADE":
                    # Delete related objects
                    related_objs = model_class.filter(
                        **{descriptor.foreign_key_field: self._id}
                    )
                    for obj in related_objs:
                        obj.delete()
                elif descriptor.on_delete == "SET_NULL":
                    # Set foreign key to None
                    related_objs = model_class.filter(
                        **{descriptor.foreign_key_field: self._id}
                    )
                    for obj in related_objs:
                        setattr(obj, descriptor.foreign_key_field, None)
                        obj.save()

    # Delete self
    super().delete()
```

**Options:**
- `CASCADE` - Delete related objects
- `SET_NULL` - Set foreign key to None (requires optional=True)
- `DO_NOTHING` - No action (default, current behavior)

**Tasks:**
1. Add `on_delete` parameter to ForeignKey
2. Implement CASCADE logic in Document.delete()
3. Implement SET_NULL logic
4. Add recursive cascade handling
5. Write 10+ tests
6. Document with examples

---

### Query Filtering by Related Fields

**Priority**: LOW (nice to have)

**Goal**: Filter by related object attributes

```python
# Filter orders by user attributes
high_value_orders = Order.filter(
    user__status="premium",
    amount__gt=1000
)

# Translated to:
# 1. Query Users where status="premium"
# 2. Get user IDs
# 3. Query Orders where user_id in [ids] AND amount > 1000
```

**Implementation**: Complex, requires query planning

---

### 1-to-1 Relationships (OneToOne)

**Priority**: LOW (can be achieved with ForeignKey + unique)

**Goal**: Enforce one-to-one relationships

```python
@dataclass
class User(Document):
    user_id: int
    name: str

@dataclass
class Profile(Document):
    user_id: int  # Unique
    bio: str

    user: OneToOne[User] = field(
        default=OneToOne("user_id", User),
        init=False,
        repr=False,
        compare=False
    )

# Usage
user = User.get(user_id=1)
profile = user.profile  # Returns single Profile or None
```

**Current Workaround:**
```python
# Use ForeignKey + manual uniqueness enforcement
user: ForeignKey[User] = ForeignKey("user_id", User)

# Get reverse relationship
profile = Profile.get(user_id=user.user_id)  # Manual query
```

**Implementation**: Similar to ForeignKey but enforces uniqueness

---

## Migration Tools

**Goal**: Easy migration from single-table to collections.

### Tools:
```python
from kenobix.migrate import migrate_to_collections

# Migrate from type field pattern to collections
migrate_to_collections(
    db_path='app.db',
    type_field='type',
    mappings={
        'user': ('users', ['user_id', 'email']),
        'order': ('orders', ['order_id', 'user_id']),
    }
)

# Schema inspection
db.collections()  # List all collections
db['users'].stats()  # Collection statistics
```

**Files:**
- `src/kenobix/migrate.py` - Migration utilities
- `scripts/migrate_to_collections.py` - CLI tool
- `docs/migrations.md` - Migration guide

---

## Performance Considerations

1. **Lazy Loading**: Default to avoid unnecessary queries ✅ (implemented)
2. **Caching**: Cache loaded objects per instance ✅ (implemented)
3. **Eager Loading**: Support prefetch_related for N+1 prevention (planned)
4. **Indexing**: Ensure foreign key fields are indexed ✅ (implemented)
5. **Batch Operations**: Load multiple related objects efficiently (planned)
6. **Junction Table Indexes**: Index both foreign keys for many-to-many ✅ (implemented)

---

## Priority Summary

| Feature | Priority | Complexity | User Value |
|---------|----------|------------|------------|
| Eager Loading (Prefetch) | HIGH | Medium | High (N+1 fix) |
| Select Related | MEDIUM | Medium | Medium |
| Cascade Delete | MEDIUM | Low | Medium |
| Query by Related Fields | LOW | High | Medium |
| OneToOne | LOW | Low | Low |
| Migration Tools | LOW | Medium | Medium |

---

*Last updated: January 2025*
