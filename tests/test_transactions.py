"""
Tests for KenobiX transaction API.

Verifies ACID compliance:
- Atomicity: All-or-nothing execution
- Consistency: Data integrity maintained
- Isolation: Transactions don't interfere
- Durability: Committed data persists
"""

from __future__ import annotations

import pytest

from kenobix import KenobiX


@pytest.fixture
def db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    """Provide KenobiX database instance."""
    database = KenobiX(str(db_path))
    yield database
    database.close()


class TestTransactions:
    """Test transaction functionality."""

    def test_simple_transaction_commit(self, db):
        """Test basic transaction with commit."""
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

    def test_simple_transaction_rollback(self, db):
        """Test transaction rollback."""
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

    def test_transaction_context_manager_commit(self, db):
        """Test transaction context manager with successful commit."""
        # Use context manager
        with db.transaction():
            db.insert({"name": "Alice"})
            db.insert({"name": "Bob"})

        # Both should be committed
        results = db.all(limit=10)
        assert len(results) == 2

    def test_transaction_context_manager_rollback(self, db):
        """Test transaction context manager with exception (rollback)."""
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

    def test_transaction_isolation(self, db):
        """Test that operations in transaction are isolated."""
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

    def test_transaction_with_updates(self, db_path):
        """Test transaction with update operations."""
        db = KenobiX(str(db_path), indexed_fields=["name"])

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

    def test_transaction_with_deletes(self, db_path):
        """Test transaction with delete operations."""
        db = KenobiX(str(db_path), indexed_fields=["name"])

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

    def test_savepoints(self, db):
        """Test savepoints for partial rollback."""
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

    def test_nested_transactions(self, db):
        """Test nested transactions using savepoints."""
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

    def test_transaction_atomicity(self, db_path):
        """Test that transaction is truly atomic (all-or-nothing)."""
        db = KenobiX(str(db_path), indexed_fields=["id"])

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

    def test_transaction_durability(self, db_path):
        """Test that committed transactions are durable."""
        # Insert data in transaction
        db = KenobiX(str(db_path))
        with db.transaction():
            db.insert({"name": "Alice"})
            db.insert({"name": "Bob"})
        db.close()

        # Reopen database - data should persist
        db = KenobiX(str(db_path))
        results = db.all(limit=10)
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Alice", "Bob"}

        db.close()

    def test_cannot_begin_twice(self, db):
        """Test that begin() fails if already in transaction."""
        db.begin()
        with pytest.raises(RuntimeError, match="Already in a transaction"):
            db.begin()
        db.rollback()

    def test_cannot_commit_without_transaction(self, db):
        """Test that commit() fails if not in transaction."""
        with pytest.raises(RuntimeError, match="Not in a transaction"):
            db.commit()

    def test_mixed_transaction_and_autocommit(self, db):
        """Test mixing transaction and auto-commit operations."""
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

    def test_release_savepoint(self, db):
        """Test releasing a savepoint (committing it)."""
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
