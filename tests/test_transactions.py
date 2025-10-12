#!/usr/bin/env python3
"""
Tests for KenobiX transaction API.

Verifies ACID compliance:
- Atomicity: All-or-nothing execution
- Consistency: Data integrity maintained
- Isolation: Transactions don't interfere
- Durability: Committed data persists
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import pytest
except ImportError:
    pytest = None

from kenobix import KenobiX


class TestTransactions:
    """Test transaction functionality."""

    def test_simple_transaction_commit(self):
        """Test basic transaction with commit."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            # Start transaction
            db.begin()
            db.insert({"name": "Alice"})
            db.insert({"name": "Bob"})
            db.commit()

            # Verify both inserts persisted
            results = db.all(limit=10)
            assert len(results) == 2
            names = {r["name"] for r in results}
            assert names == {"Alice", "Bob"}

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_simple_transaction_rollback(self):
        """Test transaction rollback."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            # Insert some data
            db.insert({"name": "Alice"})

            # Start transaction and rollback
            db.begin()
            db.insert({"name": "Bob"})
            db.insert({"name": "Carol"})
            db.rollback()

            # Only Alice should exist
            results = db.all(limit=10)
            assert len(results) == 1
            assert results[0]["name"] == "Alice"

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_transaction_context_manager_commit(self):
        """Test transaction context manager with successful commit."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            # Use context manager
            with db.transaction():
                db.insert({"name": "Alice"})
                db.insert({"name": "Bob"})

            # Both should be committed
            results = db.all(limit=10)
            assert len(results) == 2

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_transaction_context_manager_rollback(self):
        """Test transaction context manager with exception (rollback)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            # Insert initial data
            db.insert({"name": "Alice"})

            # Transaction with exception
            msg = "Simulated error"
            try:
                with db.transaction():
                    db.insert({"name": "Bob"})
                    raise ValueError(msg)
            except ValueError:
                pass  # Expected

            # Only Alice should exist (Bob rolled back)
            results = db.all(limit=10)
            assert len(results) == 1
            assert results[0]["name"] == "Alice"

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_transaction_isolation(self):
        """Test that operations in transaction are isolated."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            # Start transaction
            db.begin()
            db.insert({"name": "Alice"})

            # Data is visible within transaction
            results = db.all(limit=10)
            assert len(results) == 1

            # Don't commit yet - rollback
            db.rollback()

            # Data should not exist
            results = db.all(limit=10)
            assert len(results) == 0

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_transaction_with_updates(self):
        """Test transaction with update operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path, indexed_fields=["name"])

            # Insert initial data
            db.insert({"name": "Alice", "age": 30})
            db.insert({"name": "Bob", "age": 25})

            # Transaction with updates
            with db.transaction():
                db.update("name", "Alice", {"age": 31})
                db.update("name", "Bob", {"age": 26})

            # Verify updates
            alice = db.search("name", "Alice")[0]
            bob = db.search("name", "Bob")[0]
            assert alice["age"] == 31
            assert bob["age"] == 26

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_transaction_with_deletes(self):
        """Test transaction with delete operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path, indexed_fields=["name"])

            # Insert data
            db.insert({"name": "Alice"})
            db.insert({"name": "Bob"})
            db.insert({"name": "Carol"})

            # Transaction with deletes
            with db.transaction():
                db.remove("name", "Bob")
                db.remove("name", "Carol")

            # Only Alice should remain
            results = db.all(limit=10)
            assert len(results) == 1
            assert results[0]["name"] == "Alice"

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_savepoints(self):
        """Test savepoints for partial rollback."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            db.begin()
            db.insert({"name": "Alice"})

            # Create savepoint
            sp = db.savepoint()
            db.insert({"name": "Bob"})

            # Rollback to savepoint (Bob discarded, Alice kept)
            db.rollback_to(sp)
            db.commit()

            # Only Alice should exist
            results = db.all(limit=10)
            assert len(results) == 1
            assert results[0]["name"] == "Alice"

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_nested_transactions(self):
        """Test nested transactions using savepoints."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            # Outer transaction
            with db.transaction():
                db.insert({"name": "Alice"})

                # Nested transaction (uses savepoint)
                msg = "Inner error"
                try:
                    with db.transaction():
                        db.insert({"name": "Bob"})
                        raise ValueError(msg)
                except ValueError:
                    pass  # Expected

                # Alice should still be there, Bob rolled back
                results = db.all(limit=10)
                assert len(results) == 1
                assert results[0]["name"] == "Alice"

                db.insert({"name": "Carol"})

            # Alice and Carol committed
            results = db.all(limit=10)
            assert len(results) == 2
            names = {r["name"] for r in results}
            assert names == {"Alice", "Carol"}

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_transaction_atomicity(self):
        """Test that transaction is truly atomic (all-or-nothing)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path, indexed_fields=["id"])

            # Insert 100 documents in transaction
            with db.transaction():
                for i in range(100):
                    db.insert({"id": i, "value": i * 2})

            # All 100 should exist
            results = db.all(limit=200)
            assert len(results) == 100

            # Now try transaction that fails
            msg = "Simulated failure"
            try:
                with db.transaction():
                    for i in range(100, 200):
                        db.insert({"id": i, "value": i * 2})
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # Should still have only 100 (second batch rolled back)
            results = db.all(limit=200)
            assert len(results) == 100

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_transaction_durability(self):
        """Test that committed transactions are durable."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            # Insert data in transaction
            db = KenobiX(db_path)
            with db.transaction():
                db.insert({"name": "Alice"})
                db.insert({"name": "Bob"})
            db.close()

            # Reopen database - data should persist
            db = KenobiX(db_path)
            results = db.all(limit=10)
            assert len(results) == 2
            names = {r["name"] for r in results}
            assert names == {"Alice", "Bob"}

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_cannot_begin_twice(self):
        """Test that begin() fails if already in transaction."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            db.begin()
            error_raised = False
            error_msg = ""
            try:
                db.begin()  # Should raise
            except RuntimeError as e:
                error_raised = True
                error_msg = str(e)

            if not error_raised:
                msg = "Should have raised RuntimeError"
                raise AssertionError(msg)
            if "Already in a transaction" not in error_msg:
                msg = f"Expected 'Already in a transaction' in error, got: {error_msg}"
                raise AssertionError(msg)

            db.rollback()
            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_cannot_commit_without_transaction(self):
        """Test that commit() fails if not in transaction."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            error_raised = False
            error_msg = ""
            try:
                db.commit()  # Should raise
            except RuntimeError as e:
                error_raised = True
                error_msg = str(e)

            if not error_raised:
                msg = "Should have raised RuntimeError"
                raise AssertionError(msg)
            if "Not in a transaction" not in error_msg:
                msg = f"Expected 'Not in a transaction' in error, got: {error_msg}"
                raise AssertionError(msg)

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_mixed_transaction_and_autocommit(self):
        """Test mixing transaction and auto-commit operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            # Auto-commit
            db.insert({"name": "Alice"})

            # Transaction
            with db.transaction():
                db.insert({"name": "Bob"})

            # Auto-commit again
            db.insert({"name": "Carol"})

            # All three should exist
            results = db.all(limit=10)
            assert len(results) == 3
            names = {r["name"] for r in results}
            assert names == {"Alice", "Bob", "Carol"}

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()

    def test_release_savepoint(self):
        """Test releasing a savepoint (committing it)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db = KenobiX(db_path)

            db.begin()
            db.insert({"name": "Alice"})

            sp = db.savepoint()
            db.insert({"name": "Bob"})

            # Release savepoint (commit Bob within transaction)
            db.release_savepoint(sp)

            # Can't rollback to released savepoint, but can commit transaction
            db.commit()

            # Both should exist
            results = db.all(limit=10)
            assert len(results) == 2

            db.close()
        finally:
            if Path(db_path).exists():
                Path(db_path).unlink()


if __name__ == "__main__":
    print("Running KenobiX Transaction Tests")
    print("=" * 60)

    test = TestTransactions()

    print("\n1. Testing simple commit...")
    test.test_simple_transaction_commit()
    print("✓ Pass")

    print("\n2. Testing simple rollback...")
    test.test_simple_transaction_rollback()
    print("✓ Pass")

    print("\n3. Testing context manager commit...")
    test.test_transaction_context_manager_commit()
    print("✓ Pass")

    print("\n4. Testing context manager rollback...")
    test.test_transaction_context_manager_rollback()
    print("✓ Pass")

    print("\n5. Testing transaction isolation...")
    test.test_transaction_isolation()
    print("✓ Pass")

    print("\n6. Testing transaction with updates...")
    test.test_transaction_with_updates()
    print("✓ Pass")

    print("\n7. Testing transaction with deletes...")
    test.test_transaction_with_deletes()
    print("✓ Pass")

    print("\n8. Testing savepoints...")
    test.test_savepoints()
    print("✓ Pass")

    print("\n9. Testing nested transactions...")
    test.test_nested_transactions()
    print("✓ Pass")

    print("\n10. Testing atomicity...")
    test.test_transaction_atomicity()
    print("✓ Pass")

    print("\n11. Testing durability...")
    test.test_transaction_durability()
    print("✓ Pass")

    print("\n12. Testing error handling...")
    test.test_cannot_begin_twice()
    test.test_cannot_commit_without_transaction()
    print("✓ Pass")

    print("\n13. Testing mixed operations...")
    test.test_mixed_transaction_and_autocommit()
    print("✓ Pass")

    print("\n14. Testing savepoint release...")
    test.test_release_savepoint()
    print("✓ Pass")

    print("\n" + "=" * 60)
    print("✓ All transaction tests passed!")
