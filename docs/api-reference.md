# KenobiX API Reference

Complete API documentation for KenobiX and the ODM layer.

## Table of Contents

- [KenobiX Class](#kenobix-class)
  - [Initialization](#initialization)
  - [CRUD Operations](#crud-operations)
  - [Search Operations](#search-operations)
  - [Advanced Queries](#advanced-queries)
  - [Utilities](#utilities)
- [Document Class (ODM)](#document-class-odm)
  - [Class Methods](#class-methods)
  - [Instance Methods](#instance-methods)

---

## KenobiX Class

The main database interface.

### Initialization

#### `KenobiX(file, indexed_fields=None)`

Create a new KenobiX database instance.

**Parameters:**
- `file` (str): Path to SQLite database file (created if doesn't exist)
- `indexed_fields` (List[str], optional): List of document fields to create indexes for

**Returns:**
- `KenobiX`: Database instance

**Example:**
```python
from kenobix import KenobiX

# Basic usage
db = KenobiX('app.db')

# With indexed fields for better performance
db = KenobiX('app.db', indexed_fields=['user_id', 'email', 'status'])
```

**Notes:**
- Creates SQLite database file if it doesn't exist
- Sets up VIRTUAL generated columns for indexed fields
- Creates B-tree indexes on generated columns
- Enables WAL (Write-Ahead Logging) mode for better concurrency
- Initializes ThreadPoolExecutor with 5 workers

---

### CRUD Operations

#### `insert(document)`

Insert a single document into the database.

**Parameters:**
- `document` (Dict[str, Any]): Document to insert

**Returns:**
- `int`: ID of the inserted document (SQLite rowid)

**Raises:**
- `TypeError`: If document is not a dict

**Example:**
```python
doc_id = db.insert({'name': 'Alice', 'email': 'alice@example.com'})
print(f"Inserted document with ID: {doc_id}")
```

---

#### `insert_many(document_list)`

Insert multiple documents in a single transaction.

**Parameters:**
- `document_list` (List[Dict[str, Any]]): List of documents to insert

**Returns:**
- `List[int]`: List of IDs of inserted documents

**Raises:**
- `TypeError`: If document_list is not a list of dicts

**Example:**
```python
docs = [
    {'name': 'Alice', 'email': 'alice@example.com'},
    {'name': 'Bob', 'email': 'bob@example.com'},
]
ids = db.insert_many(docs)
print(f"Inserted {len(ids)} documents")
```

**Performance:** ~10x faster than individual inserts.

---

#### `search(key, value, limit=100, offset=0)`

Search for documents where field equals value.

**Parameters:**
- `key` (str): Field name to search
- `value` (Any): Value to match
- `limit` (int, optional): Maximum results to return (default: 100)
- `offset` (int, optional): Number of results to skip (default: 0)

**Returns:**
- `List[Dict]`: List of matching documents

**Raises:**
- `ValueError`: If key is invalid

**Example:**
```python
# Search indexed field (fast)
users = db.search('email', 'alice@example.com')

# Search non-indexed field (slower but works)
posts = db.search('title', 'My Post')

# With pagination
page1 = db.search('status', 'active', limit=50, offset=0)
page2 = db.search('status', 'active', limit=50, offset=50)
```

**Performance:**
- Indexed fields: O(log n) - ~0.01ms for 10k docs
- Non-indexed fields: O(n) - ~2.5ms for 10k docs

---

#### `update(id_key, id_value, new_dict)`

Update documents matching the given key/value pair.

**Parameters:**
- `id_key` (str): Field name to match
- `id_value` (Any): Value to match
- `new_dict` (Dict[str, Any]): Changes to apply (merged into existing document)

**Returns:**
- `bool`: True if at least one document was updated, False otherwise

**Raises:**
- `TypeError`: If new_dict is not a dict
- `ValueError`: If id_key is invalid or id_value is None

**Example:**
```python
# Update single document
success = db.update('user_id', 123, {'status': 'inactive'})

# Update multiple documents
db.update('status', 'pending', {'status': 'processing'})
```

**Performance:** 80-665x faster on indexed fields.

---

#### `remove(key, value)`

Remove all documents matching the given key/value pair.

**Parameters:**
- `key` (str): Field name to match
- `value` (Any): Value to match

**Returns:**
- `int`: Number of documents removed

**Raises:**
- `ValueError`: If key is invalid or value is None

**Example:**
```python
# Remove by indexed field
count = db.remove('user_id', 123)
print(f"Removed {count} documents")

# Remove by non-indexed field
db.remove('status', 'deleted')
```

---

#### `purge()`

Remove all documents from the database.

**Returns:**
- `bool`: True upon successful purge

**Example:**
```python
db.purge()  # Deletes all documents
```

**Warning:** This operation cannot be undone.

---

#### `all(limit=100, offset=0)`

Retrieve all documents with pagination.

**Parameters:**
- `limit` (int, optional): Maximum results to return (default: 100)
- `offset` (int, optional): Number of results to skip (default: 0)

**Returns:**
- `List[Dict]`: List of documents

**Example:**
```python
# Get first 100 documents
docs = db.all()

# Paginate
page1 = db.all(limit=50, offset=0)
page2 = db.all(limit=50, offset=50)
```

---

### Search Operations

#### `search_optimized(**filters)`

Multi-field search with automatic index usage.

**Parameters:**
- `**filters`: Keyword arguments with field=value pairs

**Returns:**
- `List[Dict]`: List of matching documents

**Example:**
```python
# Single field
results = db.search_optimized(status='active')

# Multiple fields (all conditions must match)
results = db.search_optimized(
    status='active',
    role='admin',
    verified=True
)
```

**Performance:** If all fields are indexed, 70x faster than separate searches.

---

#### `search_pattern(key, pattern, limit=100, offset=0)`

Search documents using regex pattern matching.

**Parameters:**
- `key` (str): Field name to match
- `pattern` (str): Regex pattern to match
- `limit` (int, optional): Maximum results (default: 100)
- `offset` (int, optional): Results to skip (default: 0)

**Returns:**
- `List[Dict]`: List of matching documents

**Raises:**
- `ValueError`: If key or pattern is invalid

**Example:**
```python
# Find emails ending with @example.com
users = db.search_pattern('email', r'.*@example\.com$')

# Find names starting with 'A'
users = db.search_pattern('name', '^A')
```

**Note:** Pattern search cannot use indexes (always full scan).

---

#### `find_any(key, value_list)`

Find documents where field matches any value in the list.

**Parameters:**
- `key` (str): Field name to match
- `value_list` (List[Any]): List of values to match

**Returns:**
- `List[Dict]`: List of matching documents

**Example:**
```python
# Find users with specific IDs
users = db.find_any('user_id', [1, 5, 10, 20])

# Find posts with specific statuses
posts = db.find_any('status', ['draft', 'pending', 'review'])
```

**Performance:** Uses indexes if field is indexed.

---

#### `find_all(key, value_list)`

Find documents where field contains all values in the list.

**Parameters:**
- `key` (str): Field name to check
- `value_list` (List[Any]): List of required values

**Returns:**
- `List[Dict]`: List of matching documents

**Example:**
```python
# Find posts with multiple tags
posts = db.find_all('tags', ['python', 'database'])
# Returns only posts that have BOTH tags
```

**Note:** Useful for array/list fields.

---

### Advanced Queries

#### `all_cursor(after_id=None, limit=100)`

Cursor-based pagination for better performance on large datasets.

**Parameters:**
- `after_id` (int, optional): Continue from this document ID
- `limit` (int, optional): Maximum results (default: 100)

**Returns:**
- `Dict`: Dictionary with keys:
  - `documents` (List[Dict]): List of documents
  - `next_cursor` (int): ID to use for next page
  - `has_more` (bool): Whether more documents exist

**Example:**
```python
# First page
result = db.all_cursor(limit=100)
documents = result['documents']

# Next page
if result['has_more']:
    next_result = db.all_cursor(
        after_id=result['next_cursor'],
        limit=100
    )
```

**Performance:** 100x faster than offset pagination for deep pages.

---

#### `execute_async(func, *args, **kwargs)`

Execute a function asynchronously using the thread pool.

**Parameters:**
- `func`: Function to execute
- `*args`: Positional arguments
- `**kwargs`: Keyword arguments

**Returns:**
- `concurrent.futures.Future`: Future object

**Example:**
```python
# Execute search asynchronously
future = db.execute_async(db.search, 'status', 'active')

# Do other work...

# Get result when ready
results = future.result(timeout=5)
```

**Note:** ThreadPoolExecutor has max 5 workers.

---

### Utilities

#### `explain(operation, *args)`

Show query execution plan for optimization.

**Parameters:**
- `operation` (str): Method name ('search', 'all', etc.)
- `*args`: Arguments to the method

**Returns:**
- `List[tuple]`: Query plan tuples from EXPLAIN QUERY PLAN

**Example:**
```python
# Check if index is being used
plan = db.explain('search', 'email', 'test@example.com')
for row in plan:
    print(row)

# Look for "USING INDEX" in output
```

**Tip:** Use this to verify your indexes are being used.

---

#### `stats()`

Get database statistics.

**Returns:**
- `Dict[str, Any]`: Dictionary with keys:
  - `document_count` (int): Number of documents
  - `database_size_bytes` (int): Database file size
  - `indexed_fields` (List[str]): List of indexed fields
  - `wal_mode` (bool): Whether WAL mode is enabled

**Example:**
```python
stats = db.stats()
print(f"Documents: {stats['document_count']}")
print(f"Size: {stats['database_size_bytes']} bytes")
print(f"Indexed: {stats['indexed_fields']}")
```

---

#### `get_indexed_fields()`

Get set of fields that have indexes.

**Returns:**
- `Set[str]`: Set of indexed field names

**Example:**
```python
indexed = db.get_indexed_fields()
print(f"Indexed fields: {indexed}")
```

---

#### `create_index(field)`

Dynamically create an index on a field.

**Parameters:**
- `field` (str): Field name to index

**Returns:**
- `bool`: True if index was created, False if already exists

**Example:**
```python
# Add index after initialization
success = db.create_index('email')
if success:
    print("Index created")
else:
    print("Index already exists")
```

**Note:** Better to specify indexed_fields at initialization for production use.

---

#### `close()`

Shutdown executor and close database connection.

**Example:**
```python
db.close()
```

**Important:** Always call this to properly shutdown the ThreadPoolExecutor.

---

## Document Class (ODM)

Base class for ODM models using dataclasses.

### Setup

```python
from dataclasses import dataclass
from kenobix import KenobiX, Document

# Define model
@dataclass
class User(Document):
    name: str
    email: str
    age: int

# Initialize database
db = KenobiX('app.db', indexed_fields=['email'])
Document.set_database(db)
```

---

### Class Methods

#### `Document.set_database(db)`

Set the database instance for all Document models.

**Parameters:**
- `db` (KenobiX): Database instance

**Example:**
```python
db = KenobiX('app.db')
Document.set_database(db)
```

**Note:** Must be called before using any Document operations.

---

#### `Document.get(**filters)`

Get a single document matching the filters.

**Parameters:**
- `**filters`: Field=value pairs to match

**Returns:**
- `Optional[T]`: Instance of the model or None if not found

**Example:**
```python
user = User.get(email="alice@example.com")
if user:
    print(f"Found: {user.name}")
```

---

#### `Document.get_by_id(doc_id)`

Get document by primary key ID.

**Parameters:**
- `doc_id` (int): Document ID

**Returns:**
- `Optional[T]`: Instance or None

**Example:**
```python
user = User.get_by_id(123)
```

---

#### `Document.filter(limit=100, offset=0, **filters)`

Get all documents matching the filters.

**Parameters:**
- `limit` (int, optional): Maximum results (default: 100)
- `offset` (int, optional): Results to skip (default: 0)
- `**filters`: Field=value pairs to match

**Returns:**
- `List[T]`: List of model instances

**Example:**
```python
# All users age 30
users = User.filter(age=30)

# With pagination
page1 = User.filter(age=30, limit=10, offset=0)
```

---

#### `Document.all(limit=100, offset=0)`

Get all documents.

**Parameters:**
- `limit` (int, optional): Maximum results (default: 100)
- `offset` (int, optional): Results to skip (default: 0)

**Returns:**
- `List[T]`: List of model instances

**Example:**
```python
all_users = User.all()
page1 = User.all(limit=50, offset=0)
```

---

#### `Document.count(**filters)`

Count documents matching the filters.

**Parameters:**
- `**filters`: Field=value pairs to match

**Returns:**
- `int`: Number of matching documents

**Example:**
```python
total = User.count()
active = User.count(active=True)
```

---

#### `Document.insert_many(instances)`

Insert multiple documents in a single transaction.

**Parameters:**
- `instances` (List[T]): List of model instances

**Returns:**
- `List[T]`: Same instances with _id set

**Example:**
```python
users = [
    User(name="Alice", email="alice@example.com", age=30),
    User(name="Bob", email="bob@example.com", age=25),
]
User.insert_many(users)
# All users now have _id set
```

---

#### `Document.delete_many(**filters)`

Delete all documents matching the filters.

**Parameters:**
- `**filters`: Field=value pairs to match

**Returns:**
- `int`: Number of documents deleted

**Raises:**
- `ValueError`: If no filters provided

**Example:**
```python
# Delete inactive users
deleted = User.delete_many(active=False)
print(f"Deleted {deleted} users")
```

---

### Instance Methods

#### `save()`

Save the document to the database (insert or update).

**Returns:**
- `Self`: Self with _id set after insert

**Example:**
```python
user = User(name="Alice", email="alice@example.com", age=30)
user.save()  # Insert (no _id yet)

user.age = 31
user.save()  # Update (has _id)
```

---

#### `delete()`

Delete this document from the database.

**Returns:**
- `bool`: True if deleted, False if not found

**Raises:**
- `RuntimeError`: If document has no _id (not saved yet)

**Example:**
```python
user = User.get(email="alice@example.com")
user.delete()
```

---

## Type Annotations

### KenobiX Types

```python
from typing import Dict, List, Any, Optional, Set

# Document type
Document = Dict[str, Any]

# Search results
SearchResults = List[Document]

# Cursor result
CursorResult = Dict[str, Union[List[Document], Optional[int], bool]]
```

### ODM Types

```python
from typing import TypeVar, Generic

T = TypeVar('T', bound='Document')

class Document(Generic[T]):
    _id: Optional[int]
    _db: ClassVar[Optional[KenobiX]]
    _converter: ClassVar[Any]
```

---

## Error Handling

### Common Exceptions

```python
# TypeError: Invalid document type
try:
    db.insert("not a dict")
except TypeError as e:
    print("Must insert a dict")

# ValueError: Invalid field name
try:
    db.search(None, "value")
except ValueError as e:
    print("Invalid key")

# RuntimeError: Database not set (ODM)
try:
    user.save()
except RuntimeError as e:
    print("Call Document.set_database(db) first")

# RuntimeError: Delete unsaved document (ODM)
try:
    unsaved_user.delete()
except RuntimeError as e:
    print("Cannot delete unsaved document")
```

---

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| insert() | O(1) | ~0.5ms |
| insert_many() | O(n) | ~50ms for 1000 docs |
| search() indexed | O(log n) | ~0.01ms |
| search() unindexed | O(n) | ~2.5ms for 10k docs |
| update() indexed | O(log n) | 80-665x faster |
| remove() indexed | O(log n) | Fast |
| all() | O(n) | Full scan |
| all_cursor() | O(1) per page | Efficient |
| search_pattern() | O(n) | Always full scan |

---

## Best Practices

1. **Specify indexed_fields at initialization**
2. **Use search_optimized() for multi-field queries**
3. **Use cursor pagination for large datasets**
4. **Call db.close() when done**
5. **Batch operations with insert_many()**
6. **Verify index usage with explain()**
7. **Index 3-6 most queried fields**
8. **Use ODM for type safety**

---

## See Also

- [ODM Guide](odm-guide.md) - Complete ODM documentation
- [Performance Guide](performance.md) - Optimization tips
- [GitHub Repository](https://github.com/yourusername/kenobix)
