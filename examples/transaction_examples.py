#!/usr/bin/env python3
"""
KenobiX Transaction Examples

Demonstrates various transaction patterns and use cases:
- Banking transfers with ACID guarantees
- Batch imports with error recovery
- Savepoints for partial rollback
- Nested transactions
- ODM transaction support
- Performance optimization with transactions
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from kenobix import KenobiX

# ODM is optional - only import if available
try:
    from kenobix import Document

    HAS_ODM = True
except ImportError:
    HAS_ODM = False
    Document = None


# ==============================================================================
# Example 1: Banking Transfer (Classic ACID Use Case)
# ==============================================================================


def example_banking_transfer():
    """Demonstrate atomic balance transfer between accounts."""
    print("\n" + "=" * 70)
    print("Example 1: Banking Transfer (Atomicity)")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=["account_id"])

        # Create accounts
        db.insert({"account_id": "A1", "name": "Alice", "balance": 1000})
        db.insert({"account_id": "A2", "name": "Bob", "balance": 500})

        print("\nInitial balances:")
        for account in db.all(limit=10):
            print(f"  {account['name']}: ${account['balance']}")

        # Transfer $200 from Alice to Bob
        print("\nTransferring $200 from Alice to Bob...")

        with db.transaction():
            # Debit Alice
            alice = db.search("account_id", "A1")[0]
            db.update("account_id", "A1", {"balance": alice["balance"] - 200})

            # Credit Bob
            bob = db.search("account_id", "A2")[0]
            db.update("account_id", "A2", {"balance": bob["balance"] + 200})

        print("\nFinal balances:")
        for account in db.all(limit=10):
            print(f"  {account['name']}: ${account['balance']}")

        # Demonstrate rollback on insufficient funds
        print("\nAttempting to transfer $2000 (insufficient funds)...")

        try:
            with db.transaction():
                alice = db.search("account_id", "A1")[0]
                if alice["balance"] < 2000:
                    msg = "Insufficient funds"
                    raise ValueError(msg)
                db.update("account_id", "A1", {"balance": alice["balance"] - 2000})
                bob = db.search("account_id", "A2")[0]
                db.update("account_id", "A2", {"balance": bob["balance"] + 2000})
        except ValueError as e:
            print(f"  Transaction rolled back: {e}")

        print("\nBalances after failed transfer (unchanged):")
        for account in db.all(limit=10):
            print(f"  {account['name']}: ${account['balance']}")

        db.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


# ==============================================================================
# Example 2: Batch Import with Error Recovery
# ==============================================================================


def example_batch_import():
    """Demonstrate batch import with automatic rollback on error."""
    print("\n" + "=" * 70)
    print("Example 2: Batch Import with Error Recovery")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=["user_id", "email"])

        # Simulate CSV import with validation
        users_to_import = [
            {"user_id": 1, "email": "alice@example.com", "name": "Alice"},
            {"user_id": 2, "email": "bob@example.com", "name": "Bob"},
            {"user_id": 3, "email": "invalid", "name": "Carol"},  # Invalid email
            {"user_id": 4, "email": "dave@example.com", "name": "Dave"},
        ]

        print(f"\nImporting {len(users_to_import)} users...")

        def validate_email(email: str) -> bool:
            return "@" in email and "." in email.split("@")[1]

        # First attempt: All-or-nothing import
        print("\nAttempt 1: All-or-nothing import")
        try:
            with db.transaction():
                for user in users_to_import:
                    if not validate_email(user["email"]):
                        msg = f"Invalid email: {user['email']}"
                        raise ValueError(msg)
                    db.insert(user)
        except ValueError as e:
            print(f"  Import failed: {e}")
            print("  All changes rolled back")

        print(f"  Records in database: {len(db.all(limit=100))}")

        # Second attempt: Skip invalid records
        print("\nAttempt 2: Skip invalid records (no transaction)")
        for user in users_to_import:
            if validate_email(user["email"]):
                db.insert(user)
                print(f"  Imported: {user['name']}")
            else:
                print(f"  Skipped invalid record: {user['name']}")

        print(f"\nTotal records imported: {len(db.all(limit=100))}")

        db.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


# ==============================================================================
# Example 3: Savepoints for Partial Rollback
# ==============================================================================


def example_savepoints():
    """Demonstrate savepoints for fine-grained transaction control."""
    print("\n" + "=" * 70)
    print("Example 3: Savepoints for Partial Rollback")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=["status"])

        print("\nProcessing multi-step operation with savepoints...")

        db.begin()

        # Step 1: Create order
        db.insert({"type": "order", "order_id": "O1", "status": "pending"})
        print("  Step 1: Order created")

        # Savepoint before inventory update
        sp1 = db.savepoint("before_inventory")

        # Step 2: Try to reserve inventory
        try:
            inventory = 5  # Current inventory
            required = 10  # Required amount

            if inventory < required:
                msg = "Insufficient inventory"
                raise ValueError(msg)

            db.insert({"type": "inventory", "item": "widget", "reserved": required})
            print("  Step 2: Inventory reserved")
        except ValueError as e:
            print(f"  Step 2 failed: {e}")
            print("  Rolling back to savepoint (keeping order)...")
            db.rollback_to(sp1)

        # Step 3: Continue processing
        db.update("type", "order", {"status": "awaiting_inventory"})
        print("  Step 3: Order status updated")

        db.commit()

        print("\nFinal state:")
        for doc in db.all(limit=10):
            print(f"  {doc}")

        db.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


# ==============================================================================
# Example 4: Nested Transactions
# ==============================================================================


def example_nested_transactions():
    """Demonstrate nested transactions using automatic savepoints."""
    print("\n" + "=" * 70)
    print("Example 4: Nested Transactions")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path)

        print("\nOuter transaction with nested inner transaction...")

        with db.transaction():
            db.insert({"name": "Alice", "action": "outer"})
            print("  Outer: Inserted Alice")

            # Nested transaction (automatically uses savepoint)
            try:
                with db.transaction():
                    db.insert({"name": "Bob", "action": "inner"})
                    print("  Inner: Inserted Bob")
                    msg = "Simulated inner error"
                    raise ValueError(msg)
            except ValueError as e:
                print(f"  Inner transaction rolled back: {e}")

            db.insert({"name": "Carol", "action": "outer"})
            print("  Outer: Inserted Carol")

        print("\nFinal records (Bob rolled back, Alice and Carol committed):")
        for doc in db.all(limit=10):
            print(f"  {doc['name']} - {doc['action']}")

        db.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


# ==============================================================================
# Example 5: ODM Transaction Support
# ==============================================================================


if HAS_ODM:

    @dataclass
    class User(Document):
        """User model with ODM transaction support."""

        name: str
        email: str
        credits: int = 0

else:
    User = None


def example_odm_transactions():
    """Demonstrate transactions with the ODM layer."""
    print("\n" + "=" * 70)
    print("Example 5: ODM Transaction Support")
    print("=" * 70)

    if not HAS_ODM:
        print("\nSkipping ODM example (cattrs not installed)")
        print("Install with: pip install kenobix[odm]")
        return

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=["email", "name"])
        Document.set_database(db)

        print("\nCreating users with ODM transactions...")

        # Context manager approach
        with User.transaction():
            alice = User(name="Alice", email="alice@example.com", credits=100)
            bob = User(name="Bob", email="bob@example.com", credits=50)
            alice.save()
            bob.save()
            print("  Created Alice and Bob atomically")

        # Manual transaction control
        User.begin()
        try:
            alice = User.get(email="alice@example.com")
            bob = User.get(email="bob@example.com")

            # Transfer 30 credits from Alice to Bob
            alice.credits -= 30
            bob.credits += 30

            alice.save()
            bob.save()

            User.commit()
            print("  Transferred 30 credits from Alice to Bob")
        except Exception:
            User.rollback()
            raise

        print("\nFinal user credits:")
        for user in User.all(limit=10):
            print(f"  {user.name}: {user.credits} credits")

        db.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


# ==============================================================================
# Example 6: Performance Optimization with Transactions
# ==============================================================================


def example_transaction_performance():
    """Demonstrate massive performance improvement with transactions."""
    print("\n" + "=" * 70)
    print("Example 6: Performance Optimization with Transactions")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=["batch_id"])

        # Generate test data
        num_records = 1000
        records = [{"batch_id": i, "value": i * 2} for i in range(num_records)]

        # Without transaction (slow)
        print(f"\nInserting {num_records} records WITHOUT transaction...")
        db.purge()  # Clear database
        start = time.time()
        for record in records[:100]:  # Only 100 for demo
            db.insert(record)
        duration_no_tx = time.time() - start
        print(f"  Time: {duration_no_tx:.3f}s for 100 records")
        print(f"  Estimated for {num_records}: {duration_no_tx * 10:.1f}s")

        # With transaction (fast)
        print(f"\nInserting {num_records} records WITH transaction...")
        db.purge()  # Clear database
        start = time.time()
        with db.transaction():
            for record in records:
                db.insert(record)
        duration_tx = time.time() - start
        print(f"  Time: {duration_tx:.3f}s for {num_records} records")

        speedup = (duration_no_tx * 10) / duration_tx
        print(f"\n  Speedup: {speedup:.1f}x faster with transaction!")

        db.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


# ==============================================================================
# Example 7: Manual Transaction Control with Error Handling
# ==============================================================================


def example_manual_transaction_control():
    """Demonstrate explicit transaction control with proper error handling."""
    print("\n" + "=" * 70)
    print("Example 7: Manual Transaction Control")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = KenobiX(db_path, indexed_fields=["order_id"])

        print("\nManual transaction with multiple operations...")

        db.begin()
        try:
            # Operation 1: Create order
            db.insert({"order_id": "O1", "status": "pending", "total": 100})
            print("  Operation 1: Order created")

            # Operation 2: Update inventory
            db.insert({"type": "inventory", "item": "widget", "change": -5})
            print("  Operation 2: Inventory updated")

            # Operation 3: Create invoice
            db.insert({"type": "invoice", "order_id": "O1", "amount": 100})
            print("  Operation 3: Invoice created")

            # All succeeded - commit
            db.commit()
            print("  All operations committed successfully")

        except Exception as e:
            # Any failure - rollback everything
            db.rollback()
            print(f"  Transaction rolled back due to error: {e}")
            raise

        print(f"\nTotal records: {len(db.all(limit=100))}")

        db.close()
    finally:
        if Path(db_path).exists():
            Path(db_path).unlink()


# ==============================================================================
# Main - Run All Examples
# ==============================================================================


def main():
    """Run all transaction examples."""
    print("\n" + "=" * 70)
    print("KenobiX Transaction Examples")
    print("=" * 70)
    print("\nDemonstrating full ACID transaction support with various patterns\n")

    try:
        example_banking_transfer()
        example_batch_import()
        example_savepoints()
        example_nested_transactions()
        example_odm_transactions()
        example_transaction_performance()
        example_manual_transaction_control()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)
        print("\nKey Takeaways:")
        print("  1. Use transactions for multi-step operations requiring atomicity")
        print("  2. Context managers provide automatic commit/rollback")
        print("  3. Savepoints enable partial rollback within transactions")
        print("  4. Transactions can provide 50-100x performance boost for bulk ops")
        print("  5. ODM layer fully supports transactions")
        print("  6. Manual control available for complex workflows")
        print("\nSee docs/transactions.md for complete API documentation")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        raise


if __name__ == "__main__":
    main()
