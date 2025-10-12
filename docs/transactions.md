# KenobiX Transaction API

## Overview

KenobiX provides full ACID-compliant transactions, allowing you to group multiple operations together atomically. All operations in a transaction either succeed together or fail together.

## Quick Start

### Context Manager (Recommended)

```python
from kenobix import KenobiX

db = KenobiX('app.db')

# Automatic transaction management
with db.transaction():
    db.insert({"user": "Alice", "balance": 100})
    db.insert({"user": "Bob", "balance": 50})
    # Both committed together
```

### Manual Control

```python
# Explicit begin/commit/rollback
db.begin()
try:
    db.insert({"user": "Alice"})
    db.insert({"user": "Bob"})
    db.commit()
except Exception:
    db.rollback()
    raise
```

## ACID Properties

KenobiX transactions provide full ACID guarantees:

| Property | Description | Support |
|----------|-------------|---------|
| **Atomicity** | All-or-nothing execution | ✅ Full |
| **Consistency** | Valid state transitions | ✅ Full |
| **Isolation** | Concurrent transaction safety | ✅ Read Committed |
| **Durability** | Committed data persists | ✅ Full |

## Transaction Methods

### `db.begin()`

Begin a new transaction.

```python
db.begin()
# All subsequent operations are part of transaction
db.insert({"data": "value"})
# Not committed yet...
```

**Raises**: `RuntimeError` if already in a transaction.

### `db.commit()`

Commit the current transaction, making all changes permanent.

```python
db.begin()
db.insert({"data": "value"})
db.commit()  # Now permanent
```

**Raises**: `RuntimeError` if not in a transaction.

### `db.rollback()`

Rollback the current transaction, discarding all changes.

```python
db.begin()
db.insert({"data": "value"})
db.rollback()  # Changes discarded
```

**Raises**: `RuntimeError` if not in a transaction.

### `db.transaction()`

Return a context manager for automatic transaction management.

```python
with db.transaction():
    # Operations here...
    pass  # Auto-commits on success

# Or with exception handling
try:
    with db.transaction():
        db.insert({"data": "value"})
        raise ValueError()  # Auto-rolls back
except ValueError:
    pass
```

## Savepoints (Nested Transactions)

Savepoints allow partial rollback within a transaction.

### Creating Savepoints

```python
db.begin()
db.insert({"name": "Alice"})

# Create savepoint
sp = db.savepoint()
db.insert({"name": "Bob"})

# Rollback to savepoint (discards Bob, keeps Alice)
db.rollback_to(sp)

db.commit()  # Alice committed, Bob discarded
```

### Named Savepoints

```python
sp = db.savepoint("my_savepoint")
db.rollback_to("my_savepoint")
```

### Releasing Savepoints

Release a savepoint (commit it within the transaction):

```python
sp = db.savepoint()
db.insert({"data": "value"})
db.release_savepoint(sp)  # Can't rollback past this point
```

## Nested Transactions

The context manager automatically uses savepoints for nested transactions:

```python
with db.transaction():  # Outer transaction
    db.insert({"name": "Alice"})

    try:
        with db.transaction():  # Inner transaction (savepoint)
            db.insert({"name": "Bob"})
            raise ValueError("Error!")
    except ValueError:
        pass  # Bob rolled back via savepoint

    db.insert({"name": "Carol"})
# Alice and Carol committed, Bob discarded
```

## Use Cases

### 1. Multi-Step Operations

Ensure related operations succeed or fail together:

```python
with db.transaction():
    # Transfer money between accounts
    db.update("account", "alice", {"balance": 900})
    db.update("account", "bob", {"balance": 1100})
    # Both updates committed atomically
```

### 2. Batch Inserts with Validation

```python
with db.transaction():
    for doc in large_dataset:
        if validate(doc):
            db.insert(doc)
        else:
            raise ValueError(f"Invalid document: {doc}")
    # All inserted or none
```

### 3. Complex Business Logic

```python
with db.transaction():
    # Create user
    user_id = db.insert({"email": "user@example.com"})

    # Create associated records
    db.insert({"user_id": user_id, "type": "profile"})
    db.insert({"user_id": user_id, "type": "preferences"})

    # If any step fails, everything rolls back
```

### 4. Safe Updates

```python
with db.transaction():
    # Read-modify-write pattern
    user = db.search("email", "alice@example.com")[0]
    user["login_count"] += 1
    db.update("email", "alice@example.com", user)
```

## ODM Transaction Support

The ODM layer fully supports transactions:

```python
from dataclasses import dataclass
from kenobix import KenobiX, Document

@dataclass
class User(Document):
    name: str
    email: str
    balance: int

db = KenobiX('app.db')
Document.set_database(db)

# Using context manager
with User.transaction():
    alice = User(name="Alice", email="alice@example.com", balance=100)
    bob = User(name="Bob", email="bob@example.com", balance=50)

    alice.save()
    bob.save()
    # Both saved atomically

# Or manual control
User.begin()
try:
    alice.balance -= 50
    bob.balance += 50
    alice.save()
    bob.save()
    User.commit()
except:
    User.rollback()
    raise
```

## Performance Considerations

### Transaction Overhead

Transactions add minimal overhead:

```python
# Without transaction (auto-commit each operation)
for i in range(1000):
    db.insert({"value": i})  # 1000 commits

# With transaction (single commit)
with db.transaction():
    for i in range(1000):
        db.insert({"value": i})  # 1 commit
```

**Result**: Transaction is ~50-100x faster for bulk operations!

### WAL Mode

KenobiX uses SQLite's WAL (Write-Ahead Logging) mode, which provides:

- Better concurrency during transactions
- Readers don't block writers
- Writers don't block readers (for committed data)
- Fast commits

### Lock Granularity

- **Reads**: No locking (multiple readers concurrent)
- **Writes**: Locked at database level (writers serialize)
- **Transactions**: Hold write lock for duration

## Error Handling

### Automatic Rollback

The context manager automatically rolls back on exceptions:

```python
try:
    with db.transaction():
        db.insert({"data": 1})
        raise Exception("Error!")
        db.insert({"data": 2})  # Never reached
except Exception:
    # Transaction automatically rolled back
    pass
```

### Manual Recovery

```python
db.begin()
try:
    db.insert({"data": 1})
    risky_operation()
    db.insert({"data": 2})
    db.commit()
except Exception as e:
    db.rollback()
    log_error(e)
    # Can retry or handle error
```

### Nested Failures

```python
with db.transaction():
    db.insert({"data": 1})

    try:
        with db.transaction():  # Savepoint
            db.insert({"data": 2})
            raise ValueError()
    except ValueError:
        # Inner transaction rolled back
        # Outer transaction continues
        pass

    db.insert({"data": 3})
# Data 1 and 3 committed, 2 discarded
```

## Best Practices

### 1. Use Context Managers

**✅ Good**:
```python
with db.transaction():
    db.insert(data)
```

**❌ Avoid**:
```python
db.begin()
db.insert(data)
db.commit()  # Easy to forget error handling
```

### 2. Keep Transactions Short

```python
# ✅ Good - short transaction
with db.transaction():
    db.insert({"user": "Alice"})
    db.insert({"user": "Bob"})

# ❌ Bad - long-running transaction
with db.transaction():
    data = fetch_from_api()  # Slow!
    process_data(data)  # Slow!
    db.insert(data)
```

### 3. Don't Mix Transaction Styles

```python
# ❌ Bad - mixing manual and context manager
db.begin()
with db.transaction():  # Will raise RuntimeError!
    db.insert(data)
```

### 4. Handle Specific Exceptions

```python
# ✅ Good - specific error handling
with db.transaction():
    try:
        db.insert(data)
    except sqlite3.IntegrityError:
        # Handle constraint violation
        raise DuplicateKeyError()
```

### 5. Use Savepoints for Complex Logic

```python
with db.transaction():
    db.insert(required_data)

    sp = db.savepoint()
    try:
        db.insert(optional_data)
    except Exception:
        db.rollback_to(sp)  # Keep required_data

    db.commit()
```

## Comparison with Other Databases

| Feature | KenobiX | PostgreSQL | MongoDB | Redis |
|---------|---------|------------|---------|-------|
| Multi-op transactions | ✅ | ✅ | ✅ (4.0+) | ⚠️ Limited |
| Savepoints | ✅ | ✅ | ❌ | ❌ |
| Nested transactions | ✅ (via savepoints) | ✅ | ❌ | ❌ |
| Context manager | ✅ | ✅ (with libs) | ✅ | ⚠️ Limited |
| Isolation levels | Read Committed | Configurable | Read Committed | Read Uncommitted |

## Limitations

### 1. No Cross-Database Transactions

Each database file has independent transactions:

```python
db1 = KenobiX('db1.db')
db2 = KenobiX('db2.db')

# Cannot create single transaction across both
with db1.transaction():
    db1.insert({"data": 1})
    # db2.insert() would be separate transaction
```

### 2. Isolation Level

KenobiX provides **Read Committed** isolation (SQLite default with WAL mode):
- No dirty reads ✅
- No serializable transactions ❌

### 3. Concurrent Writes

Multiple writers serialize via the write lock:

```python
# Process 1
with db.transaction():  # Holds write lock
    db.insert({"data": 1})
    time.sleep(10)  # Blocks other writers

# Process 2 (blocked until Process 1 completes)
with db.transaction():
    db.insert({"data": 2})
```

## Troubleshooting

### "Already in a transaction" Error

**Problem**: Calling `begin()` twice without `commit()` or `rollback()`.

**Solution**: Use context manager or ensure proper cleanup:
```python
try:
    db.begin()
    # operations...
finally:
    if db._in_transaction:
        db.rollback()
```

### "Not in a transaction" Error

**Problem**: Calling `commit()` or `rollback()` without `begin()`.

**Solution**: Ensure `begin()` was called:
```python
db.begin()  # Don't forget this!
db.commit()
```

### Database Locked

**Problem**: Long-running transactions block other writers.

**Solution**: Keep transactions short or use optimistic locking:
```python
# ✅ Better - short transaction
data = prepare_data()  # Outside transaction
with db.transaction():
    db.insert(data)  # Quick!
```

## Migration Guide

### From Auto-Commit

**Before**:
```python
db.insert({"user": "Alice"})  # Auto-committed
db.insert({"user": "Bob"})    # Auto-committed
```

**After**:
```python
with db.transaction():
    db.insert({"user": "Alice"})
    db.insert({"user": "Bob"})
# Both committed together
```

### From Try/Except Patterns

**Before**:
```python
try:
    db.insert({"user": "Alice"})
    db.insert({"user": "Bob"})
except Exception:
    # Can't rollback Alice!
    pass
```

**After**:
```python
try:
    with db.transaction():
        db.insert({"user": "Alice"})
        db.insert({"user": "Bob"})
except Exception:
    # Both automatically rolled back
    pass
```

## Examples

See `examples/transaction_example.py` for complete working examples.

## References

- [SQLite Transaction Documentation](https://www.sqlite.org/lang_transaction.html)
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [ACID Properties](https://en.wikipedia.org/wiki/ACID)
