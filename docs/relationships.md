# Relationships in KenobiX

## Overview

KenobiX ODM provides **relationship support** through descriptor-based fields that enable you to model connections between documents. The relationship system provides transparent lazy loading with caching to minimize database queries while maintaining a clean, Pythonic API.

Relationships work seamlessly with collections, allowing you to build normalized data models with foreign key relationships similar to SQL databases.

## Why Use Relationships?

### Benefits

1. **Transparent Loading**: Access related objects naturally via attributes
2. **Lazy Evaluation**: Related objects load only when accessed
3. **Automatic Caching**: Loaded objects cached to avoid redundant queries
4. **Type Safety**: Full type hints for IDE autocomplete support
5. **Optional Relationships**: Built-in support for nullable foreign keys
6. **Clean API**: No manual joins or complex queries needed

### When to Use Relationships

Use relationships when you have:
- Normalized data across multiple collections
- Foreign key references between documents
- One-to-many or many-to-one relationships
- Need to avoid data duplication
- Want to maintain referential structure

## Quick Start

### Basic Foreign Key Relationship

```python
from dataclasses import dataclass, field
from kenobix import KenobiX, ForeignKey
from kenobix.odm import Document

# Set up database
db = KenobiX('myapp.db')
Document.set_database(db)

# Define models
@dataclass
class User(Document):
    class Meta:
        collection_name = "users"
        indexed_fields = ["user_id"]

    user_id: int
    name: str
    email: str

@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]

    order_id: int
    user_id: int  # Foreign key field
    amount: float

    # Relationship declaration
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),
        init=False,
        repr=False,
        compare=False
    )

# Usage - transparent lazy loading
user = User(user_id=1, name="Alice", email="alice@example.com")
user.save()

order = Order(order_id=101, user_id=1, amount=99.99)
order.save()

# Access related object
order_loaded = Order.get(order_id=101)
print(order_loaded.user.name)  # "Alice" - lazy loads User when accessed
print(order_loaded.user.email)  # "alice@example.com" - uses cached value
```

## ForeignKey Relationships

### Basic Declaration

A `ForeignKey` establishes a many-to-one relationship between two models.

```python
from dataclasses import dataclass, field
from kenobix import ForeignKey
from kenobix.odm import Document

@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]

    order_id: int
    user_id: int  # The foreign key field
    amount: float

    # Relationship declaration
    # Syntax: ForeignKey(foreign_key_field, target_model)
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),
        init=False,    # Don't include in __init__
        repr=False,    # Don't include in __repr__
        compare=False  # Don't include in comparisons
    )
```

### Parameters

**`ForeignKey(foreign_key_field, model, optional=False, related_field=None)`**

- **`foreign_key_field`** (str, required): Name of the field in this model storing the foreign key value
- **`model`** (type[T], required): Target Document model class
- **`optional`** (bool, default=False): If True, allow None values; if False, raise error on None
- **`related_field`** (str, default=None): Field name in related model to query by. If None, uses `foreign_key_field`

### Lazy Loading

Related objects are loaded from the database only when accessed:

```python
order = Order.get(order_id=101)
# No query to User table yet

print(order.user.name)  # NOW the User is loaded
# SELECT id, data FROM users WHERE user_id = 1
```

### Caching

Loaded objects are cached to avoid redundant database queries:

```python
order = Order.get(order_id=101)

# First access - loads from database
user1 = order.user  # Query: SELECT ... FROM users ...

# Second access - returns cached object
user2 = order.user  # No query! Uses cached value

# Same object reference
assert user1 is user2  # True
```

### Optional Relationships

Use `optional=True` to allow None values:

```python
@dataclass
class Profile(Document):
    class Meta:
        collection_name = "profiles"
        indexed_fields = ["profile_id", "user_id"]

    profile_id: int
    user_id: int | None  # Nullable field
    bio: str

    # Optional relationship
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User, optional=True),
        init=False,
        repr=False,
        compare=False
    )

# Create profile without user
profile = Profile(profile_id=1, user_id=None, bio="Anonymous")
profile.save()

# Access returns None (no error)
profile_loaded = Profile.get(profile_id=1)
print(profile_loaded.user)  # None
```

### Multiple Foreign Keys to Same Model

When a model has multiple foreign keys to the same target model, use the `related_field` parameter:

```python
@dataclass
class Transaction(Document):
    class Meta:
        collection_name = "transactions"
        indexed_fields = ["from_user_id", "to_user_id"]

    from_user_id: int
    to_user_id: int
    amount: float

    # Both reference User, but query by different fields
    from_user: ForeignKey[User] = field(
        default=ForeignKey("from_user_id", User, related_field="user_id"),
        init=False,
        repr=False,
        compare=False
    )
    to_user: ForeignKey[User] = field(
        default=ForeignKey("to_user_id", User, related_field="user_id"),
        init=False,
        repr=False,
        compare=False
    )

# Usage
txn = Transaction.get(from_user_id=1)
print(txn.from_user.name)  # Loads User where user_id=1
print(txn.to_user.name)    # Loads User where user_id=2
```

## Assignment and Updates

### Assigning Related Objects

You can assign related objects directly, and the foreign key field updates automatically:

```python
user1 = User(user_id=1, name="Alice", email="alice@example.com")
user1.save()

user2 = User(user_id=2, name="Bob", email="bob@example.com")
user2.save()

order = Order(order_id=101, user_id=1, amount=99.99)
order.save()

# Load and reassign
order_loaded = Order.get(order_id=101)
print(order_loaded.user.name)  # "Alice"

# Assign different user
order_loaded.user = user2
print(order_loaded.user_id)  # 2 (automatically updated)
print(order_loaded.user.name)  # "Bob"

# Save to persist
order_loaded.save()
```

### Assigning None to Optional Relationships

```python
profile = Profile.get(profile_id=1)
print(profile.user.name)  # "Alice"

# Set to None
profile.user = None
print(profile.user_id)  # None
print(profile.user)  # None

profile.save()  # Persist the change
```

### Validation on Assignment

Required relationships (optional=False) cannot be set to None:

```python
order = Order.get(order_id=101)

# This raises ValueError
order.user = None  # ValueError: Cannot set User to None (not optional)
```

## Error Handling

### Missing Related Objects

If a foreign key references a non-existent object:

```python
# Create order with invalid user_id
order = Order(order_id=101, user_id=999, amount=99.99)
order.save()

# Accessing user raises ValueError
order_loaded = Order.get(order_id=101)
try:
    user = order_loaded.user
except ValueError as e:
    print(e)  # "Related User with user_id=999 not found"
```

### Optional Relationships with Missing Objects

Optional relationships return None instead of raising an error:

```python
# Profile with non-existent user
profile = Profile(profile_id=1, user_id=999, bio="Test")
profile.save()

profile_loaded = Profile.get(profile_id=1)
print(profile_loaded.user)  # None (no error)
```

### None Values in Required Relationships

Required relationships with None values raise an error:

```python
# Manually insert invalid data
collection = db.collection("orders", indexed_fields=["order_id", "user_id"])
collection.insert({"order_id": 101, "user_id": None, "amount": 99.99})

# This would fail during loading because user_id: int can't be None
# Use optional=True and Optional[int] for nullable foreign keys
```

## Transactions

Relationships work seamlessly with transactions:

```python
# Atomic creation of related objects
with db.transaction():
    user = User(user_id=1, name="Alice", email="alice@example.com")
    user.save()

    order = Order(order_id=101, user_id=1, amount=99.99)
    order.save()

    # Both committed together

# Load and verify
order_loaded = Order.get(order_id=101)
print(order_loaded.user.name)  # "Alice"
```

### Rollback Behavior

If a transaction fails, all changes are rolled back:

```python
user = User(user_id=1, name="Alice", email="alice@example.com")
user.save()

try:
    with db.transaction():
        order = Order(order_id=101, user_id=1, amount=99.99)
        order.save()
        raise ValueError("Simulated error")
except ValueError:
    pass

# Order not saved due to rollback
order_loaded = Order.get(order_id=101)
print(order_loaded)  # None
```

## Persistence

Relationships persist across database sessions:

```python
# First session
db1 = KenobiX('myapp.db')
Document.set_database(db1)

user = User(user_id=1, name="Alice", email="alice@example.com")
user.save()

order = Order(order_id=101, user_id=1, amount=99.99)
order.save()

db1.close()

# Second session
db2 = KenobiX('myapp.db')
Document.set_database(db2)

order_loaded = Order.get(order_id=101)
print(order_loaded.user.name)  # "Alice" - loads from database

db2.close()
```

## Performance Considerations

### Lazy Loading Benefits

Lazy loading prevents unnecessary queries:

```python
# Get all orders
orders = Order.filter(amount=99.99, limit=100)  # 1 query

# Only load users when needed
for order in orders:
    if order.amount > 50:
        print(order.user.name)  # Query per order (as needed)
```

### Caching Benefits

Caching prevents duplicate queries:

```python
order = Order.get(order_id=101)

# Multiple accesses = single query
print(order.user.name)   # Query 1: Load user
print(order.user.email)  # No query: Use cached user
print(order.user.name)   # No query: Use cached user
```

### N+1 Query Problem

Be aware of the N+1 query problem when loading relationships in loops:

```python
# This generates N+1 queries: 1 for orders + N for users
orders = Order.filter(amount=99.99, limit=100)  # Query 1
for order in orders:
    print(order.user.name)  # Query 2, 3, 4, ... N+1
```

**Future optimization** (not yet implemented): Prefetch or select_related to batch-load relationships.

### Indexing Foreign Key Fields

Always index foreign key fields for performance:

```python
@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]  # ← Index foreign key!

    order_id: int
    user_id: int  # Foreign key field
    amount: float

    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),
        init=False,
        repr=False,
        compare=False
    )
```

## Best Practices

### 1. Always Index Foreign Keys

```python
# Good: Foreign key field is indexed
@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]  # ← Good!

    user_id: int
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),
        init=False,
        repr=False,
        compare=False
    )

# Bad: Foreign key not indexed
@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id"]  # ← Missing user_id!

    user_id: int
    user: ForeignKey[User] = field(...)
```

### 2. Use Optional for Nullable Relationships

```python
# Good: Nullable foreign key properly declared
@dataclass
class Profile(Document):
    user_id: int | None  # Nullable type
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User, optional=True),  # ← Good!
        init=False,
        repr=False,
        compare=False
    )

# Bad: Nullable field but not optional
@dataclass
class Profile(Document):
    user_id: int | None
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),  # ← Bad! Will raise error on None
        init=False,
        repr=False,
        compare=False
    )
```

### 3. Use field() with Proper Flags

```python
# Good: Proper field declaration
user: ForeignKey[User] = field(
    default=ForeignKey("user_id", User),
    init=False,    # Don't include in __init__
    repr=False,    # Don't include in __repr__
    compare=False  # Don't include in comparisons
)

# Bad: Missing field() wrapper
user: ForeignKey[User] = ForeignKey("user_id", User)  # May cause issues
```

### 4. Use Descriptive Field Names

```python
# Good: Clear relationship names
@dataclass
class Order(Document):
    user_id: int
    user: ForeignKey[User] = field(...)  # Clear: "user"

    product_id: int
    product: ForeignKey[Product] = field(...)  # Clear: "product"

# Acceptable: Descriptive names for clarity
@dataclass
class Transaction(Document):
    from_user_id: int
    from_user: ForeignKey[User] = field(...)  # Clear: "from_user"

    to_user_id: int
    to_user: ForeignKey[User] = field(...)  # Clear: "to_user"
```

### 5. Use Transactions for Related Changes

```python
# Good: Atomic operations
with db.transaction():
    user = User(user_id=1, name="Alice", email="alice@example.com")
    user.save()

    order = Order(order_id=101, user_id=1, amount=99.99)
    order.save()

# Bad: Non-atomic operations
user = User(user_id=1, name="Alice", email="alice@example.com")
user.save()  # If this succeeds but next fails, inconsistent state

order = Order(order_id=101, user_id=1, amount=99.99)
order.save()  # Might fail, leaving orphaned user
```

### 6. Be Mindful of Cache Invalidation

```python
# Cache persists even if foreign key field changes manually
order = Order.get(order_id=101)
print(order.user.name)  # "Alice" - loads and caches

# Manually changing foreign key doesn't clear cache
order.user_id = 2
print(order.user.name)  # Still "Alice" - cached!

# Proper way: Assign through descriptor
order.user = user2  # Updates both field AND cache
print(order.user.name)  # "Bob" - correct!
```

## Common Patterns

### E-commerce Application

```python
@dataclass
class Customer(Document):
    class Meta:
        collection_name = "customers"
        indexed_fields = ["customer_id", "email"]

    customer_id: int
    name: str
    email: str

@dataclass
class Product(Document):
    class Meta:
        collection_name = "products"
        indexed_fields = ["product_id", "category"]

    product_id: int
    name: str
    price: float
    category: str

@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "customer_id"]

    order_id: int
    customer_id: int
    total: float

    customer: ForeignKey[Customer] = field(
        default=ForeignKey("customer_id", Customer),
        init=False,
        repr=False,
        compare=False
    )

@dataclass
class OrderItem(Document):
    class Meta:
        collection_name = "order_items"
        indexed_fields = ["order_id", "product_id"]

    order_id: int
    product_id: int
    quantity: int
    price: float

    order: ForeignKey[Order] = field(
        default=ForeignKey("order_id", Order),
        init=False,
        repr=False,
        compare=False
    )
    product: ForeignKey[Product] = field(
        default=ForeignKey("product_id", Product),
        init=False,
        repr=False,
        compare=False
    )

# Usage
order = Order.get(order_id=1001)
print(f"Customer: {order.customer.name}")

items = OrderItem.filter(order_id=1001, limit=100)
for item in items:
    print(f"Product: {item.product.name}, Qty: {item.quantity}")
```

### Blog with Comments

```python
@dataclass
class User(Document):
    class Meta:
        collection_name = "users"
        indexed_fields = ["user_id", "username"]

    user_id: int
    username: str
    email: str

@dataclass
class Post(Document):
    class Meta:
        collection_name = "posts"
        indexed_fields = ["post_id", "author_id"]

    post_id: int
    author_id: int
    title: str
    content: str

    author: ForeignKey[User] = field(
        default=ForeignKey("author_id", User, related_field="user_id"),
        init=False,
        repr=False,
        compare=False
    )

@dataclass
class Comment(Document):
    class Meta:
        collection_name = "comments"
        indexed_fields = ["comment_id", "post_id", "author_id"]

    comment_id: int
    post_id: int
    author_id: int
    content: str

    post: ForeignKey[Post] = field(
        default=ForeignKey("post_id", Post),
        init=False,
        repr=False,
        compare=False
    )
    author: ForeignKey[User] = field(
        default=ForeignKey("author_id", User, related_field="user_id"),
        init=False,
        repr=False,
        compare=False
    )

# Usage
comments = Comment.filter(post_id=42, limit=100)
for comment in comments:
    print(f"{comment.author.username}: {comment.content}")
    print(f"On post: {comment.post.title}")
```

### Financial Transactions

```python
@dataclass
class Account(Document):
    class Meta:
        collection_name = "accounts"
        indexed_fields = ["account_id", "user_id"]

    account_id: int
    user_id: int
    balance: float

    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),
        init=False,
        repr=False,
        compare=False
    )

@dataclass
class Transaction(Document):
    class Meta:
        collection_name = "transactions"
        indexed_fields = ["transaction_id", "from_account_id", "to_account_id"]

    transaction_id: int
    from_account_id: int
    to_account_id: int
    amount: float
    timestamp: float

    from_account: ForeignKey[Account] = field(
        default=ForeignKey("from_account_id", Account, related_field="account_id"),
        init=False,
        repr=False,
        compare=False
    )
    to_account: ForeignKey[Account] = field(
        default=ForeignKey("to_account_id", Account, related_field="account_id"),
        init=False,
        repr=False,
        compare=False
    )

# Usage with transaction safety
with db.transaction():
    txn = Transaction.get(transaction_id=5001)

    from_account = txn.from_account
    to_account = txn.to_account

    print(f"Transfer: {from_account.user.name} → {to_account.user.name}")
    print(f"Amount: ${txn.amount:.2f}")
```

## Troubleshooting

### Related Object Not Found

```python
# Check foreign key value
order = Order.get(order_id=101)
print(order.user_id)  # 999 (doesn't exist)

# Verify user exists
user = User.get(user_id=999)
print(user)  # None

# Fix: Create missing user or update foreign key
user = User(user_id=999, name="Unknown", email="unknown@example.com")
user.save()
```

### Cache Stale After Manual Field Update

```python
# Don't manually update foreign key field
order.user_id = 2  # Cache still points to old user!

# Instead, assign through descriptor
order.user = user2  # Updates both field and cache correctly
```

### Circular Import Issues

If you have circular dependencies between models:

```python
# models.py
from __future__ import annotations  # Enable forward references

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .other_models import OtherModel

@dataclass
class MyModel(Document):
    other_id: int
    other: ForeignKey['OtherModel'] = field(...)  # Use string forward reference
```

### Performance Issues with Relationships

```python
# Problem: N+1 queries
orders = Order.filter(amount=99.99, limit=100)  # 1 query
for order in orders:
    print(order.user.name)  # N queries

# Temporary solution: Batch process or limit scope
# Future: Prefetch support (not yet implemented)
```

## RelatedSet Relationships (One-to-Many)

### Overview

`RelatedSet` provides access to the reverse side of a `ForeignKey` relationship, allowing you to query all related objects from the "one" side of a one-to-many relationship.

### Basic Declaration

```python
from dataclasses import dataclass, field
from kenobix import ForeignKey, RelatedSet
from kenobix.odm import Document

@dataclass
class User(Document):
    class Meta:
        collection_name = "users"
        indexed_fields = ["user_id"]

    user_id: int
    name: str

    # One-to-many: one user has many orders
    orders: RelatedSet[Order] = field(
        default=RelatedSet(Order, "user_id"),
        init=False,
        repr=False,
        compare=False
    )

@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]

    order_id: int
    user_id: int
    amount: float

    # Many-to-one: many orders belong to one user
    user: ForeignKey[User] = field(
        default=ForeignKey("user_id", User),
        init=False,
        repr=False,
        compare=False
    )

# Usage
user = User.get(user_id=1)
orders = user.orders.all()  # Get all orders for this user
count = user.orders.count()  # Count orders
```

### Parameters

**`RelatedSet(related_model, foreign_key_field, local_field=None)`**

- **`related_model`** (type[T], required): Related model class (the "many" side)
- **`foreign_key_field`** (str, required): Field in related model storing the foreign key
- **`local_field`** (str, optional): Field in this model that foreign key references. Defaults to `foreign_key_field`

### RelatedSetManager Methods

When you access a `RelatedSet`, you get a `RelatedSetManager` that provides these methods:

#### `all(limit=100)`

Get all related objects:

```python
user = User.get(user_id=1)
all_orders = user.orders.all()
all_orders_limited = user.orders.all(limit=50)
```

#### `filter(**filters, limit=100)`

Filter related objects by additional criteria:

```python
# Get orders with specific amount
expensive_orders = user.orders.filter(amount=99.99)

# Combine multiple filters
recent_large_orders = user.orders.filter(amount=99.99, status="completed")
```

#### `count()`

Count related objects:

```python
order_count = user.orders.count()
print(f"User has {order_count} orders")
```

#### `add(obj)`

Add an object to the related set:

```python
# Create a new order
new_order = Order(order_id=104, user_id=0, amount=199.99)

# Add it to user's orders (automatically sets user_id and saves)
user.orders.add(new_order)

# Order is now saved with user_id=1
```

#### `remove(obj)`

Remove an object from the related set:

```python
# Remove an order from user
order = user.orders.all()[0]
user.orders.remove(order)

# Order still exists but user_id is set to None
```

#### `clear()`

Remove all objects from the related set:

```python
# Remove all orders from user
user.orders.clear()

# All orders still exist but their user_id is set to None
```

### Iteration and Length

`RelatedSet` supports Python iteration and length operations:

```python
user = User.get(user_id=1)

# Iterate over related objects
for order in user.orders:
    print(f"Order {order.order_id}: ${order.amount}")

# Get count using len()
num_orders = len(user.orders)
print(f"User has {num_orders} orders")
```

### Bidirectional Relationships

`ForeignKey` and `RelatedSet` work together to provide bidirectional navigation:

```python
# Navigate from order to user (ForeignKey)
order = Order.get(order_id=101)
user = order.user
print(f"Order belongs to: {user.name}")

# Navigate from user to orders (RelatedSet)
user = User.get(user_id=1)
orders = user.orders.all()
print(f"User has {len(orders)} orders")
```

### Manager Caching

The `RelatedSetManager` is cached per instance:

```python
user = User.get(user_id=1)

# First access creates manager
manager1 = user.orders

# Second access returns same manager
manager2 = user.orders

assert manager1 is manager2  # True - same object
```

### Performance Considerations

#### Query Efficiency

Each call to `all()` or `filter()` executes a database query:

```python
user = User.get(user_id=1)

# Each of these executes a query
orders1 = user.orders.all()  # Query 1
orders2 = user.orders.all()  # Query 2 (not cached!)

# Store results if needed multiple times
orders = user.orders.all()
for order in orders:  # No additional queries
    print(order.amount)
```

#### Limiting Results

Always use `limit` for large collections:

```python
# Good: Limit results
recent_orders = user.orders.all(limit=10)

# Bad: Load all orders (could be thousands)
all_orders = user.orders.all(limit=100000)
```

#### Index Foreign Keys

Ensure foreign key fields are indexed for fast queries:

```python
@dataclass
class Order(Document):
    class Meta:
        collection_name = "orders"
        indexed_fields = ["order_id", "user_id"]  # ← Index foreign key!

    order_id: int
    user_id: int  # Foreign key - must be indexed
    amount: float
```

### Transactions with RelatedSet

```python
with db.transaction():
    user = User(user_id=1, name="Alice")
    user.save()

    # Create multiple orders
    order1 = Order(order_id=101, user_id=0, amount=99.99)
    order2 = Order(order_id=102, user_id=0, amount=149.99)

    user.orders.add(order1)
    user.orders.add(order2)

# All changes committed together
```

### Best Practices for RelatedSet

#### 1. Make Foreign Key Fields Nullable

If you plan to use `remove()` or `clear()`, make the foreign key field nullable:

```python
@dataclass
class Order(Document):
    order_id: int
    user_id: int | None  # ← Nullable for remove/clear
    amount: float
```

#### 2. Use Descriptive Names

```python
# Good: Plural noun for collections
orders: RelatedSet[Order] = field(...)
comments: RelatedSet[Comment] = field(...)

# Avoid: Singular or unclear names
order_list: RelatedSet[Order] = field(...)  # Unclear
order: RelatedSet[Order] = field(...)  # Confusing
```

#### 3. Limit Query Results

```python
# Good: Always specify reasonable limits
user.orders.all(limit=100)
user.orders.filter(status="active", limit=50)

# Bad: Unbounded queries
user.orders.all(limit=999999)  # Could load entire table
```

#### 4. Don't Modify Foreign Keys Manually

```python
# Bad: Manual foreign key modification
order.user_id = 2
order.save()

# Good: Use RelatedSet methods
old_user.orders.remove(order)
new_user.orders.add(order)
```

#### 5. Bidirectional Setup

Always define both sides of the relationship:

```python
# Good: Both sides defined
@dataclass
class User(Document):
    orders: RelatedSet[Order] = field(...)  # ← One side

@dataclass
class Order(Document):
    user: ForeignKey[User] = field(...)  # ← Many side

# This allows navigation in both directions
```

### Common Patterns with RelatedSet

#### Get All Items from Parent

```python
user = User.get(user_id=1)

# Get all orders
all_orders = user.orders.all()

# Filter orders
active_orders = user.orders.filter(status="active")
expensive_orders = user.orders.filter(amount=999.99)
```

#### Aggregate Over Related Items

```python
user = User.get(user_id=1)

# Calculate total spending
orders = user.orders.all(limit=1000)
total = sum(order.amount for order in orders)
print(f"Total spent: ${total:.2f}")

# Find max/min
amounts = [order.amount for order in orders]
if amounts:
    print(f"Largest order: ${max(amounts):.2f}")
    print(f"Smallest order: ${min(amounts):.2f}")
```

#### Bulk Operations

```python
user = User.get(user_id=1)

# Mark all orders as processed
with db.transaction():
    orders = user.orders.all(limit=1000)
    for order in orders:
        order.status = "processed"
        order.save()
```

#### Reassign Related Objects

```python
old_user = User.get(user_id=1)
new_user = User.get(user_id=2)

# Move all orders from old_user to new_user
with db.transaction():
    orders = old_user.orders.all(limit=1000)
    for order in orders:
        old_user.orders.remove(order)
        new_user.orders.add(order)
```

### Error Handling

#### Prevent Direct Assignment

```python
user = User.get(user_id=1)

# This raises AttributeError
try:
    user.orders = []  # Error! Cannot assign to RelatedSet
except AttributeError as e:
    print(e)  # "Cannot directly assign to RelatedSet..."

# Use add/remove/clear methods instead
user.orders.clear()
```

#### Handle Empty Results

```python
user = User.get(user_id=1)

orders = user.orders.all()
if not orders:
    print("User has no orders")
else:
    print(f"User has {len(orders)} orders")
```

## Future Features

The following features are planned for future releases:

- **Many-to-Many**: Junction table support
- **Prefetch**: Batch-load relationships to avoid N+1 queries
- **Select Related**: Join-like queries for performance
- **Cascade Delete**: Automatically delete related objects
- **On Delete/Update Actions**: Configurable FK constraints

## See Also

- [ODM Documentation](odm.md) - Object-Document Mapping basics
- [Collections Guide](collections.md) - Multi-collection databases
- [Transactions Guide](transactions.md) - ACID transactions
- [API Reference](api-reference.md) - Complete API documentation
- [Performance Guide](performance.md) - Optimization tips
