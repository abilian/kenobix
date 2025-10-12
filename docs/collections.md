# Collections in KenobiX

## Overview

KenobiX supports **multi-collection databases**, allowing you to organize your data into separate, isolated collections within a single database file. Each collection has its own table, indexes, and schema, similar to MongoDB collections or SQL tables.

Collections provide better organization, performance, and type safety compared to storing all documents in a single table with a "type" field.

## Why Use Collections?

### Benefits

1. **Better Organization**: Each entity type has its own collection
2. **Improved Performance**: Smaller tables with focused indexes
3. **Type Safety**: No mixing of different document types
4. **Cleaner Queries**: No need to filter by type field
5. **Independent Indexes**: Each collection can have different indexed fields
6. **Isolation**: Data is completely separated between collections

### When to Use Collections

Use collections when you have:
- Multiple distinct entity types (users, orders, products, etc.)
- Different schemas for different types of data
- Need for different indexes per entity type
- Want to migrate from type-based single-table design

## Quick Start

### Creating Collections

```python
from kenobix import KenobiX

# Open database
db = KenobiX('myapp.db')

# Create collections with indexed fields
users = db.collection('users', indexed_fields=['user_id', 'email'])
orders = db.collection('orders', indexed_fields=['order_id', 'user_id'])
products = db.collection('products', indexed_fields=['product_id', 'category'])

# Dictionary-style access (alternative syntax)
db['users'].insert({'user_id': 1, 'name': 'Alice', 'email': 'alice@example.com'})
db['orders'].insert({'order_id': 101, 'user_id': 1, 'amount': 99.99})
```

### Basic CRUD Operations

```python
# Insert
user_id = users.insert({
    'user_id': 1,
    'name': 'Alice',
    'email': 'alice@example.com',
    'role': 'admin'
})

# Search
results = users.search('user_id', 1)
user = results[0]

# Update
users.update('user_id', 1, {'role': 'superadmin'})

# Get all
all_users = users.all(limit=100)

# Remove
users.remove('user_id', 1)
```

## Collection API

### Creating and Accessing Collections

#### `db.collection(name, indexed_fields=None)`

Creates or retrieves a collection.

```python
# Create with indexes
users = db.collection('users', indexed_fields=['user_id', 'email'])

# Create without indexes (indexes can be added later)
logs = db.collection('logs')

# Subsequent calls return the same collection instance (cached)
users2 = db.collection('users')  # Same as users
assert users is users2  # True
```

#### Dictionary-Style Access

```python
# More concise syntax
db['users'].insert({'user_id': 1, 'name': 'Alice'})
db['orders'].search('order_id', 101)

# Equivalent to
db.collection('users').insert({'user_id': 1, 'name': 'Alice'})
db.collection('orders').search('order_id', 101)
```

### Listing Collections

```python
# Get list of all collections in database
collections = db.collections()
print(collections)  # ['users', 'orders', 'products']

# Check if collection exists
if 'users' in db.collections():
    print("Users collection exists")
```

### Collection Operations

All standard KenobiX operations work on collections:

```python
users = db['users']

# Insert single
user_id = users.insert({'user_id': 1, 'name': 'Alice'})

# Insert many
user_ids = users.insert_many([
    {'user_id': 2, 'name': 'Bob'},
    {'user_id': 3, 'name': 'Carol'}
])

# Search
results = users.search('name', 'Alice')

# Search with pattern (regex)
results = users.search_pattern('email', r'.*@example\.com')

# Find any
results = users.find_any('user_id', [1, 2, 3])

# Update
users.update('user_id', 1, {'email': 'alice@newdomain.com'})

# Remove
users.remove('user_id', 1)

# Purge (delete all)
users.purge()

# Get all with pagination
results = users.all(limit=50, offset=0)

# Cursor-based pagination (more efficient)
cursor = users.all_cursor(limit=50)
for doc in cursor:
    print(doc)
```

### Collection Metadata

```python
users = db['users']

# Get indexed fields
indexed = users.get_indexed_fields()
print(indexed)  # ['user_id', 'email']

# Get statistics
stats = users.stats()
print(f"Total users: {stats['count']}")
print(f"Database size: {stats['database_size']} bytes")

# Query plan analysis
plan = users.explain('search', 'user_id', 1)
print(plan)  # Shows if indexes are being used
```

## Transactions Across Collections

Transactions work seamlessly across multiple collections since they all share the same SQLite connection.

### Context Manager (Recommended)

```python
# Atomic operations across collections
with db.transaction():
    user_id = db['users'].insert({
        'user_id': 1,
        'name': 'Alice',
        'email': 'alice@example.com'
    })

    db['orders'].insert({
        'order_id': 101,
        'user_id': 1,
        'amount': 99.99
    })

    db['audit_log'].insert({
        'action': 'user_created',
        'user_id': 1
    })
# All committed together, or all rolled back on error
```

### Rollback on Error

```python
try:
    with db.transaction():
        db['users'].insert({'user_id': 1, 'name': 'Alice'})
        db['orders'].insert({'order_id': 101, 'user_id': 1})
        raise ValueError("Simulated error")
except ValueError:
    pass

# Both inserts are rolled back - nothing is committed
assert len(db['users'].all(limit=10)) == 0
assert len(db['orders'].all(limit=10)) == 0
```

### Savepoints for Partial Rollback

```python
with db.transaction():
    db['users'].insert({'user_id': 1, 'name': 'Alice'})

    sp = db.savepoint('before_orders')

    try:
        db['orders'].insert({'order_id': 101, 'user_id': 1})
        db['orders'].insert({'order_id': 102, 'user_id': 999})  # Invalid user_id
    except Exception:
        db.rollback_to(sp)  # Rollback only orders

    # User is still inserted
```

## Collection Isolation

Collections are completely isolated from each other:

```python
# Same field names in different collections - no conflict
db['users'].insert({'id': 1, 'name': 'Alice'})
db['products'].insert({'id': 1, 'name': 'Widget'})

# Different indexes per collection
users = db.collection('users', indexed_fields=['user_id', 'email'])
orders = db.collection('orders', indexed_fields=['order_id', 'user_id'])

# Queries are scoped to individual collections
users_with_id_1 = db['users'].search('id', 1)
products_with_id_1 = db['products'].search('id', 1)
# Returns different documents
```

## ODM with Collections

The ODM layer supports collections through the `Meta` class.

### Explicit Collection Names

```python
from dataclasses import dataclass
from kenobix.odm import Document

@dataclass
class User(Document):
    class Meta:
        collection_name = "users"
        indexed_fields = ["user_id", "email"]

    user_id: int
    name: str
    email: str

# Set database
db = KenobiX('myapp.db')
Document.set_database(db)

# Save automatically uses "users" collection
user = User(user_id=1, name='Alice', email='alice@example.com')
user.save()

# Query from "users" collection
alice = User.get(user_id=1)
```

### Auto-Derived Collection Names

If you don't specify `collection_name`, it's derived from the class name with pluralization:

```python
@dataclass
class User(Document):
    # No Meta - auto-derives "users"
    user_id: int
    name: str

@dataclass
class Category(Document):
    # No Meta - auto-derives "categories"
    category_id: int
    name: str

@dataclass
class Address(Document):
    # No Meta - auto-derives "addresses"
    address_id: int
    street: str

@dataclass
class Box(Document):
    # No Meta - auto-derives "boxes"
    box_id: int
    size: str
```

### Per-Model Collections

Each ODM model automatically uses its own collection:

```python
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
    user_id: int
    amount: float

# Models are completely isolated
user = User(user_id=1, name='Alice')
user.save()  # -> users collection

order = Order(order_id=101, user_id=1, amount=99.99)
order.save()  # -> orders collection

# Queries are scoped to model's collection
users = User.filter(name='Alice')  # Only queries users collection
orders = Order.filter(user_id=1)   # Only queries orders collection
```

### Transactions with ODM

```python
with db.transaction():
    user = User(user_id=1, name='Alice', email='alice@example.com')
    user.save()

    order = Order(order_id=101, user_id=1, amount=99.99)
    order.save()

# Both committed atomically
```

## Backward Compatibility

### Default Collection

If you don't use collections explicitly, KenobiX uses a default collection called "documents" - maintaining full backward compatibility:

```python
# Old code (still works)
db = KenobiX('app.db', indexed_fields=['name', 'email'])
db.insert({'name': 'Alice', 'email': 'alice@example.com'})
users = db.search('name', 'Alice')

# Uses "documents" collection under the hood
assert 'documents' in db.collections()
```

### Mixing Old and New Code

```python
# Old API (uses default "documents" collection)
db = KenobiX('app.db', indexed_fields=['name'])
db.insert({'name': 'Alice'})

# New API (explicit collections)
db['users'].insert({'name': 'Bob'})

# Both work simultaneously - no conflicts
```

## Performance Considerations

### Indexes Per Collection

Each collection has its own indexes, which improves query performance:

```python
# Users collection indexes user_id and email
users = db.collection('users', indexed_fields=['user_id', 'email'])

# Orders collection indexes order_id and user_id
orders = db.collection('orders', indexed_fields=['order_id', 'user_id'])

# Queries use appropriate indexes
users.search('email', 'alice@example.com')  # Uses idx_email on users table
orders.search('user_id', 1)  # Uses idx_user_id on orders table
```

### Smaller Tables = Faster Scans

```python
# With collections: Small focused tables
users = db['users'].all(limit=1000)        # Fast - only user records
orders = db['orders'].all(limit=1000)      # Fast - only order records

# Without collections: Large mixed table
all_docs = db.all(limit=10000)             # Slower - scans all types
users = [d for d in all_docs if d.get('type') == 'user']
```

### No Type Field Filtering

```python
# With collections: Direct query
users = db['users'].search('name', 'Alice')

# Without collections: Type filtering required
all = db.search('name', 'Alice')
users = [d for d in all if d.get('type') == 'user']
```

## Best Practices

### 1. Name Collections Consistently

```python
# Good - plural nouns
db['users']
db['orders']
db['products']

# Avoid - mixed styles
db['user']  # Inconsistent
db['Order']  # Inconsistent casing
```

### 2. Use Indexed Fields

```python
# Always specify indexed fields for better performance
users = db.collection('users', indexed_fields=['user_id', 'email'])

# Add indexes for foreign keys
orders = db.collection('orders', indexed_fields=['order_id', 'user_id'])
```

### 3. Use ODM Meta Class

```python
# Explicit configuration is better than implicit
@dataclass
class User(Document):
    class Meta:
        collection_name = "users"           # Explicit name
        indexed_fields = ["user_id", "email"]  # Define indexes upfront

    user_id: int
    name: str
    email: str
```

### 4. Use Transactions for Related Changes

```python
# Ensure consistency across collections
with db.transaction():
    user_id = db['users'].insert({'user_id': 1, 'name': 'Alice'})
    db['profiles'].insert({'user_id': 1, 'bio': 'Software Engineer'})
    db['permissions'].insert({'user_id': 1, 'role': 'admin'})
```

### 5. Use Collection Stats for Monitoring

```python
# Check collection health
for collection_name in db.collections():
    stats = db[collection_name].stats()
    print(f"{collection_name}: {stats['count']} documents")
```

## Migration from Single Table

If you have existing data in a single table with a "type" field:

### Manual Migration

```python
from kenobix import KenobiX

# Open existing database
db = KenobiX('app.db')

# Get all documents
all_docs = db.all(limit=100000)

# Create collections
users = db.collection('users', indexed_fields=['user_id'])
orders = db.collection('orders', indexed_fields=['order_id'])

# Migrate in a transaction
with db.transaction():
    for doc in all_docs:
        doc_type = doc.pop('type', None)  # Remove type field

        if doc_type == 'user':
            users.insert(doc)
        elif doc_type == 'order':
            orders.insert(doc)

# Optionally: Clear old documents table
# db.purge()
```

### Verification

```python
# Verify migration
print(f"Users: {len(db['users'].all(limit=10000))}")
print(f"Orders: {len(db['orders'].all(limit=10000))}")

# Check indexes are working
plan = db['users'].explain('search', 'user_id', 1)
assert 'INDEX' in str(plan) or 'SEARCH' in str(plan)
```

## Common Patterns

### E-commerce Application

```python
db = KenobiX('ecommerce.db')

# Setup collections
customers = db.collection('customers', indexed_fields=['customer_id', 'email'])
products = db.collection('products', indexed_fields=['product_id', 'category'])
orders = db.collection('orders', indexed_fields=['order_id', 'customer_id'])
order_items = db.collection('order_items', indexed_fields=['order_id', 'product_id'])

# Create order with items
with db.transaction():
    # Insert order
    order_id = orders.insert({
        'order_id': 1001,
        'customer_id': 42,
        'total': 149.99,
        'status': 'pending'
    })

    # Insert order items
    order_items.insert_many([
        {'order_id': 1001, 'product_id': 101, 'quantity': 2, 'price': 49.99},
        {'order_id': 1001, 'product_id': 102, 'quantity': 1, 'price': 50.01}
    ])
```

### Multi-Tenant Application

```python
# Separate collection per tenant
tenant_id = 'acme_corp'

users = db.collection(f'{tenant_id}_users', indexed_fields=['user_id'])
data = db.collection(f'{tenant_id}_data', indexed_fields=['data_id'])

# Complete isolation between tenants
users.insert({'user_id': 1, 'name': 'Alice'})
```

### Audit Logging

```python
# Dedicated collection for audit logs
audit = db.collection('audit_logs', indexed_fields=['timestamp', 'user_id', 'action'])

def log_action(user_id, action, details):
    audit.insert({
        'timestamp': time.time(),
        'user_id': user_id,
        'action': action,
        'details': details
    })

# Use alongside main operations
with db.transaction():
    user_id = db['users'].insert({'name': 'Alice'})
    log_action(user_id, 'user_created', {'name': 'Alice'})
```

## Troubleshooting

### Collection Not Found

```python
# Check if collection exists
if 'users' not in db.collections():
    users = db.collection('users', indexed_fields=['user_id'])
```

### Slow Queries

```python
# Check if indexes are being used
plan = db['users'].explain('search', 'email', 'alice@example.com')
print(plan)

# If indexes aren't used, recreate collection with proper indexes
# (Note: Can't modify indexes on existing collection - need to migrate)
```

### Transaction Conflicts

```python
# Use savepoints for complex transactions
with db.transaction():
    db['users'].insert({'user_id': 1, 'name': 'Alice'})

    sp = db.savepoint('before_risky_operation')

    try:
        # Risky operation
        db['orders'].insert({'order_id': 101, 'user_id': 999})
    except Exception:
        db.rollback_to(sp)  # Rollback only risky operation
```

## See Also

- [ODM Documentation](odm.md) - Object-Document Mapping with collections
- [Transactions Guide](transactions.md) - ACID transactions across collections
- [API Reference](api-reference.md) - Complete API documentation
- [Performance Guide](performance.md) - Optimization tips
