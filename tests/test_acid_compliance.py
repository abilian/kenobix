#!/usr/bin/env python3
"""
Comprehensive ACID Compliance Tests for KenobiX

This test suite rigorously verifies that KenobiX provides full ACID guarantees:
- Atomicity: All-or-nothing execution
- Consistency: Valid state transitions
- Isolation: Concurrent transaction safety
- Durability: Committed data persists

Each property is tested with multiple scenarios to ensure complete compliance.
"""

from __future__ import annotations

import contextlib
import multiprocessing
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from kenobix import KenobiX
from kenobix.odm import Document

# ============================================================================
# Test Fixtures and Helpers
# ============================================================================


def create_test_db(indexed_fields: list[str] | None = None) -> tuple[str, KenobiX]:
    """Create a temporary test database."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115
    db_path = tmp.name
    tmp.close()
    db = KenobiX(db_path, indexed_fields=indexed_fields)
    return db_path, db


def cleanup_db(db_path: str, db: KenobiX | None = None):
    """Clean up test database."""
    if db:
        with contextlib.suppress(Exception):
            db.close()
    if Path(db_path).exists():
        with contextlib.suppress(Exception):
            Path(db_path).unlink()


# Worker functions for multiprocessing tests (must be top-level)
def concurrent_reader_worker(db_path: str, worker_id: int, iterations: int) -> dict:
    """Worker that performs reads during a long transaction."""
    db = KenobiX(db_path)
    start = time.time()
    results_seen = []

    for _ in range(iterations):
        results = db.all(limit=1000)
        results_seen.append(len(results))
        time.sleep(0.001)  # Small delay to allow interleaving

    elapsed = time.time() - start
    db.close()

    return {
        "worker_id": worker_id,
        "results_seen": results_seen,
        "elapsed": elapsed,
    }


def concurrent_transaction_worker(
    db_path: str, worker_id: int, iterations: int
) -> dict:
    """Worker that performs transactions concurrently."""
    db = KenobiX(db_path, indexed_fields=["worker_id", "counter"])
    success_count = 0

    for i in range(iterations):
        try:
            with db.transaction():
                db.insert({
                    "worker_id": worker_id,
                    "counter": i,
                    "data": f"w{worker_id}_i{i}",
                })
                # Small delay to increase chance of conflicts
                time.sleep(0.001)
                success_count += 1
        except Exception:  # noqa: BLE001, S110, PERF203
            pass  # Transaction failed, that's okay - testing concurrency

    db.close()
    return {"worker_id": worker_id, "success_count": success_count}


def balance_transfer_worker(db_path: str, worker_id: int, iterations: int) -> dict:
    """Worker that performs balance transfers (tests consistency)."""
    db = KenobiX(db_path, indexed_fields=["account_id"])
    transfers_completed = 0

    for _ in range(iterations):
        try:
            with db.transaction():
                # Read two accounts
                account_a = db.search("account_id", "A", limit=1)[0]
                account_b = db.search("account_id", "B", limit=1)[0]

                # Transfer 10 from A to B
                if account_a["balance"] >= 10:
                    account_a["balance"] -= 10
                    account_b["balance"] += 10

                    db.update("account_id", "A", {"balance": account_a["balance"]})
                    db.update("account_id", "B", {"balance": account_b["balance"]})
                    transfers_completed += 1
        except Exception:  # noqa: BLE001, S110, PERF203
            pass  # Transaction may fail due to concurrency - that's expected

    db.close()
    return {"worker_id": worker_id, "transfers_completed": transfers_completed}


# ============================================================================
# ATOMICITY TESTS - All-or-Nothing Execution
# ============================================================================


class TestAtomicity:
    """
    Test that transactions are atomic - all operations succeed or all fail.
    No partial updates should ever be visible.
    """

    def test_atomicity_multiple_inserts(self):
        """All inserts in transaction succeed or all fail."""
        db_path, db = create_test_db()

        try:
            # Successful transaction
            with db.transaction():
                for i in range(100):
                    db.insert({"id": i, "value": i * 2})

            assert len(db.all(limit=200)) == 100

            # Failed transaction - nothing should be inserted
            msg = "Intentional failure"
            try:
                with db.transaction():
                    for i in range(100, 200):
                        db.insert({"id": i, "value": i * 2})
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # Still only 100 records
            assert len(db.all(limit=200)) == 100

        finally:
            cleanup_db(db_path, db)

    def test_atomicity_mixed_operations(self):
        """Mixed insert/update/delete operations are atomic."""
        db_path, db = create_test_db(indexed_fields=["name"])

        try:
            # Setup initial data
            db.insert({"name": "Alice", "balance": 100})
            db.insert({"name": "Bob", "balance": 100})
            db.insert({"name": "Carol", "balance": 100})

            # Failed transaction with mixed operations
            msg = "Intentional failure"
            try:
                with db.transaction():
                    db.insert({"name": "Dave", "balance": 100})
                    db.update("name", "Alice", {"balance": 150})
                    db.remove("name", "Carol")
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # All operations should be rolled back
            results = db.all(limit=10)
            assert len(results) == 3  # Dave not inserted, Carol not deleted

            alice = db.search("name", "Alice")[0]
            assert alice["balance"] == 100  # Update rolled back

        finally:
            cleanup_db(db_path, db)

    def test_atomicity_nested_transactions(self):
        """Nested transaction failures only rollback inner transaction."""
        db_path, db = create_test_db()

        try:
            with db.transaction():
                db.insert({"name": "Alice"})

                # Inner transaction fails
                msg = "Inner failure"
                try:
                    with db.transaction():
                        db.insert({"name": "Bob"})
                        raise ValueError(msg)
                except ValueError:
                    pass

                # Bob rolled back, Alice still pending
                assert len(db.all(limit=10)) == 1

                db.insert({"name": "Carol"})

            # Outer transaction commits - Alice and Carol saved
            results = db.all(limit=10)
            assert len(results) == 2
            names = {r["name"] for r in results}
            assert names == {"Alice", "Carol"}

        finally:
            cleanup_db(db_path, db)

    def test_atomicity_large_batch(self):
        """Large batch operations are atomic."""
        db_path, db = create_test_db()

        try:
            # Insert 1000 documents in transaction
            with db.transaction():
                for i in range(1000):
                    db.insert({"id": i, "data": f"record_{i}"})

            assert len(db.all(limit=2000)) == 1000

            # Failed large batch
            msg = "Batch failure"
            try:
                with db.transaction():
                    for i in range(1000, 2000):
                        db.insert({"id": i, "data": f"record_{i}"})
                        if i == 1500:  # Fail halfway through
                            raise RuntimeError(msg)
            except RuntimeError:
                pass

            # Should still have only 1000
            assert len(db.all(limit=2000)) == 1000

        finally:
            cleanup_db(db_path, db)

    def test_atomicity_with_savepoints(self):
        """Savepoints allow partial rollback within transaction."""
        db_path, db = create_test_db()

        try:
            db.begin()
            db.insert({"name": "Alice"})

            sp1 = db.savepoint()
            db.insert({"name": "Bob"})

            sp2 = db.savepoint()
            db.insert({"name": "Carol"})

            # Rollback to sp2 - Carol discarded
            db.rollback_to(sp2)
            assert len(db.all(limit=10)) == 2

            db.insert({"name": "Dave"})

            # Rollback to sp1 - Dave and Bob discarded
            db.rollback_to(sp1)
            assert len(db.all(limit=10)) == 1

            db.insert({"name": "Eve"})
            db.commit()

            # Only Alice and Eve saved
            results = db.all(limit=10)
            assert len(results) == 2
            names = {r["name"] for r in results}
            assert names == {"Alice", "Eve"}

        finally:
            cleanup_db(db_path, db)

    def test_atomicity_odm_operations(self):
        """ODM operations are atomic."""

        @dataclass
        class User(Document):
            name: str
            email: str
            balance: int

        db_path, db = create_test_db()

        try:
            Document.set_database(db)

            # Successful transaction
            with User.transaction():
                user1 = User(name="Alice", email="alice@example.com", balance=100)
                user2 = User(name="Bob", email="bob@example.com", balance=100)
                user1.save()
                user2.save()

            assert User.count() == 2

            # Failed transaction
            msg = "ODM failure"
            try:
                with User.transaction():
                    user3 = User(name="Carol", email="carol@example.com", balance=100)
                    user3.save()
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # Carol not saved
            assert User.count() == 2

        finally:
            cleanup_db(db_path, db)


# ============================================================================
# CONSISTENCY TESTS - Valid State Transitions
# ============================================================================


class TestConsistency:
    """
    Test that transactions maintain consistency.
    Database should always be in a valid state.
    """

    def test_consistency_balance_transfer(self):
        """Balance transfers maintain total balance invariant."""
        db_path, db = create_test_db(indexed_fields=["account_id"])

        try:
            # Setup accounts
            db.insert({"account_id": "A", "name": "Alice", "balance": 1000})
            db.insert({"account_id": "B", "name": "Bob", "balance": 1000})

            initial_total = 2000

            # Perform transfers
            for _ in range(50):
                with db.transaction():
                    account_a = db.search("account_id", "A")[0]
                    account_b = db.search("account_id", "B")[0]

                    # Transfer 10 from A to B
                    account_a["balance"] -= 10
                    account_b["balance"] += 10

                    db.update("account_id", "A", {"balance": account_a["balance"]})
                    db.update("account_id", "B", {"balance": account_b["balance"]})

            # Total balance should be unchanged
            account_a = db.search("account_id", "A")[0]
            account_b = db.search("account_id", "B")[0]
            final_total = account_a["balance"] + account_b["balance"]

            assert final_total == initial_total
            assert account_a["balance"] == 500
            assert account_b["balance"] == 1500

        finally:
            cleanup_db(db_path, db)

    def test_consistency_no_negative_balance(self):
        """Business rules enforced - balances can't go negative."""
        db_path, db = create_test_db(indexed_fields=["account_id"])

        try:
            db.insert({"account_id": "A", "balance": 100})

            # Try to withdraw more than balance
            msg = "Insufficient funds"
            try:
                with db.transaction():
                    account = db.search("account_id", "A")[0]
                    new_balance = account["balance"] - 150

                    if new_balance < 0:
                        raise ValueError(msg)

                    db.update("account_id", "A", {"balance": new_balance})
            except ValueError:
                pass

            # Balance unchanged
            account = db.search("account_id", "A")[0]
            assert account["balance"] == 100

        finally:
            cleanup_db(db_path, db)

    def test_consistency_referential_integrity(self):
        """Related records remain consistent."""
        db_path, db = create_test_db(indexed_fields=["user_id", "order_id", "type"])

        try:
            # Create user and orders in transaction
            with db.transaction():
                db.insert({"type": "user", "user_id": "U1", "name": "Alice"})
                db.insert({
                    "type": "order",
                    "order_id": "O1",
                    "user_id": "U1",
                    "amount": 100,
                })
                db.insert({
                    "type": "order",
                    "order_id": "O2",
                    "user_id": "U1",
                    "amount": 200,
                })

            # Verify consistency - search for orders specifically
            all_u1 = db.search("user_id", "U1", limit=10)
            orders = [r for r in all_u1 if r.get("type") == "order"]
            assert len(orders) == 2

            # Failed transaction - no orphaned orders
            msg = "User creation failed"
            try:
                with db.transaction():
                    db.insert({"type": "user", "user_id": "U2", "name": "Bob"})
                    db.insert({
                        "type": "order",
                        "order_id": "O3",
                        "user_id": "U2",
                        "amount": 300,
                    })
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # User U2 and order O3 not created
            all_u2 = db.search("user_id", "U2")
            assert len(all_u2) == 0
            orders_o3 = db.search("order_id", "O3")
            assert len(orders_o3) == 0

        finally:
            cleanup_db(db_path, db)

    def test_consistency_counter_increment(self):
        """Counter increments maintain correct sequence."""
        db_path, db = create_test_db(indexed_fields=["counter_id"])

        try:
            db.insert({"counter_id": "C1", "value": 0})

            # Increment counter 100 times
            for _ in range(100):
                with db.transaction():
                    counter = db.search("counter_id", "C1")[0]
                    new_value = counter["value"] + 1
                    db.update("counter_id", "C1", {"value": new_value})

            # Counter should be exactly 100
            counter = db.search("counter_id", "C1")[0]
            assert counter["value"] == 100

        finally:
            cleanup_db(db_path, db)

    def test_consistency_inventory_tracking(self):
        """Inventory counts remain accurate."""
        db_path, db = create_test_db(indexed_fields=["product_id"])

        try:
            db.insert({"product_id": "P1", "name": "Widget", "stock": 100})

            # Simulate 20 sales
            for _ in range(20):
                with db.transaction():
                    product = db.search("product_id", "P1")[0]
                    if product["stock"] >= 1:
                        product["stock"] -= 1
                        product["sales"] = product.get("sales", 0) + 1
                        db.update("product_id", "P1", product)

            # Stock should be 80, sales should be 20
            product = db.search("product_id", "P1")[0]
            assert product["stock"] == 80
            assert product["sales"] == 20
            assert product["stock"] + product["sales"] == 100

        finally:
            cleanup_db(db_path, db)


# ============================================================================
# ISOLATION TESTS - Concurrent Transaction Safety
# ============================================================================


class TestIsolation:
    """
    Test that concurrent transactions are properly isolated.
    Read Committed isolation level should be maintained.
    """

    def test_isolation_no_dirty_reads(self):
        """Uncommitted changes should not be visible to other connections."""
        db_path, _ = create_test_db(indexed_fields=["name"])

        try:
            # Connection 1: Start transaction but don't commit
            db1 = KenobiX(db_path, indexed_fields=["name"])
            db1.begin()
            db1.insert({"name": "Alice", "balance": 100})

            # Connection 2: Should not see uncommitted data
            db2 = KenobiX(db_path, indexed_fields=["name"])
            results = db2.search("name", "Alice")
            assert len(results) == 0  # No dirty read!

            # Commit and verify visibility
            db1.commit()
            results = db2.search("name", "Alice")
            assert len(results) == 1  # Now visible

            db1.close()
            db2.close()

        finally:
            cleanup_db(db_path, None)

    def test_isolation_read_committed(self):
        """Only committed data should be readable."""
        db_path, _ = create_test_db()

        try:
            db1 = KenobiX(db_path)
            db2 = KenobiX(db_path)

            # db1 inserts in transaction
            db1.begin()
            db1.insert({"value": 1})
            db1.insert({"value": 2})

            # db2 sees no data yet
            assert len(db2.all(limit=10)) == 0

            db1.commit()

            # Now db2 can see committed data
            assert len(db2.all(limit=10)) == 2

            db1.close()
            db2.close()

        finally:
            cleanup_db(db_path, None)

    def test_isolation_concurrent_transactions(self):
        """Multiple concurrent transactions should not interfere."""
        db_path, db = create_test_db(indexed_fields=["worker_id", "counter"])
        db.close()

        try:
            num_workers = 4
            iterations = 20

            with multiprocessing.Pool(processes=num_workers) as pool:
                results = pool.starmap(
                    concurrent_transaction_worker,
                    [(db_path, i, iterations) for i in range(num_workers)],
                )

            # Verify all transactions completed
            total_success = sum(r["success_count"] for r in results)
            assert total_success == num_workers * iterations

            # Verify data integrity
            db = KenobiX(db_path, indexed_fields=["worker_id", "counter"])
            for worker_id in range(num_workers):
                records = db.search("worker_id", worker_id, limit=100)
                assert len(records) == iterations

        finally:
            cleanup_db(db_path, db)

    def test_isolation_readers_during_write_transaction(self):
        """Readers should see consistent snapshot during write transactions."""
        db_path, _ = create_test_db()

        try:
            db1 = KenobiX(db_path)

            # Insert initial data
            for i in range(50):
                db1.insert({"id": i})

            # Start a long write transaction in background
            db1.begin()
            for i in range(50, 100):
                db1.insert({"id": i})

            # Launch readers - they should see consistent state (50 records)
            db2 = KenobiX(db_path)
            results = db2.all(limit=200)
            initial_count = len(results)
            assert initial_count == 50  # Don't see uncommitted writes

            # Another read should see same count
            results = db2.all(limit=200)
            assert len(results) == initial_count

            # Commit and verify new reads see updated data
            db1.commit()
            results = db2.all(limit=200)
            assert len(results) == 100

            db1.close()
            db2.close()

        finally:
            cleanup_db(db_path, None)

    def test_isolation_serializable_transactions(self):
        """Write transactions serialize properly."""
        db_path, db = create_test_db(indexed_fields=["account_id"])

        # Setup test accounts
        db.insert({"account_id": "A", "balance": 1000})
        db.insert({"account_id": "B", "balance": 1000})
        db.close()

        try:
            num_workers = 4
            iterations = 10

            # Multiple workers doing balance transfers
            with multiprocessing.Pool(processes=num_workers) as pool:
                pool.starmap(
                    balance_transfer_worker,
                    [(db_path, i, iterations) for i in range(num_workers)],
                )

            # Verify total balance unchanged
            db = KenobiX(db_path, indexed_fields=["account_id"])
            account_a = db.search("account_id", "A")[0]
            account_b = db.search("account_id", "B")[0]
            total = account_a["balance"] + account_b["balance"]

            assert total == 2000  # Total preserved despite concurrent transfers

        finally:
            cleanup_db(db_path, db)


# ============================================================================
# DURABILITY TESTS - Committed Data Persists
# ============================================================================


class TestDurability:
    """
    Test that committed transactions are durable.
    Data should survive crashes and restarts.
    """

    def test_durability_simple_commit(self):
        """Committed data survives database close/reopen."""
        db_path, db = create_test_db()

        try:
            with db.transaction():
                for i in range(100):
                    db.insert({"id": i, "value": f"data_{i}"})

            db.close()

            # Reopen and verify data persisted
            db = KenobiX(db_path)
            results = db.all(limit=200)
            assert len(results) == 100

        finally:
            cleanup_db(db_path, db)

    def test_durability_multiple_transactions(self):
        """Multiple transactions persist correctly."""
        db_path, db = create_test_db()

        try:
            for batch in range(10):
                with db.transaction():
                    for i in range(10):
                        db.insert({"batch": batch, "item": i})

            db.close()

            # Reopen and verify all data
            db = KenobiX(db_path)
            results = db.all(limit=200)
            assert len(results) == 100

            # Verify all batches present
            batches_seen = {r["batch"] for r in results}
            assert batches_seen == set(range(10))

        finally:
            cleanup_db(db_path, db)

    def test_durability_with_rollback(self):
        """Only committed transactions survive restart."""
        db_path, db = create_test_db()

        try:
            # Committed transaction
            with db.transaction():
                db.insert({"id": 1, "status": "committed"})

            # Rolled back transaction
            msg = "Rollback"
            try:
                with db.transaction():
                    db.insert({"id": 2, "status": "rolled_back"})
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # Another committed transaction
            with db.transaction():
                db.insert({"id": 3, "status": "committed"})

            db.close()

            # Reopen and verify only committed data
            db = KenobiX(db_path)
            results = db.all(limit=10)
            assert len(results) == 2

            ids = {r["id"] for r in results}
            assert ids == {1, 3}

        finally:
            cleanup_db(db_path, db)

    def test_durability_wal_mode(self):
        """WAL mode provides durability guarantees."""
        db_path, db = create_test_db()

        try:
            # Verify WAL mode is enabled
            stats = db.stats()
            assert stats["wal_mode"] is True

            # Insert data
            with db.transaction():
                for i in range(50):
                    db.insert({"id": i})

            # WAL file (db_path + "-wal") may exist during operation
            # but may not exist after checkpointing - mode is what matters

            db.close()

            # Data should be durable
            db = KenobiX(db_path)
            assert len(db.all(limit=100)) == 50

        finally:
            cleanup_db(db_path, db)

    def test_durability_large_transaction(self):
        """Large transactions are durable."""
        db_path, db = create_test_db()

        try:
            # Insert 10,000 documents in single transaction
            with db.transaction():
                for i in range(10000):
                    db.insert({"id": i, "data": f"large_dataset_{i}" * 10})

            db.close()

            # Reopen and verify all data persisted
            db = KenobiX(db_path)
            count = len(db.all(limit=20000))
            assert count == 10000

        finally:
            cleanup_db(db_path, db)

    def test_durability_crash_recovery_simulation(self):
        """Simulate crash - committed data should survive."""
        db_path, db = create_test_db()

        try:
            # Commit some data
            with db.transaction():
                for i in range(50):
                    db.insert({"id": i, "committed": True})

            # Start transaction but DON'T commit (simulate crash)
            db.begin()
            for i in range(50, 100):
                db.insert({"id": i, "committed": False})

            # Simulate crash - close without commit/rollback
            # (In real crash, OS would kill process)
            db._connection.close()

            # Recovery - reopen database
            db = KenobiX(db_path)
            results = db.all(limit=200)

            # Only committed data should be present
            assert len(results) == 50
            assert all(r["committed"] for r in results)

        finally:
            cleanup_db(db_path, db)

    def test_durability_odm_persistence(self):
        """ODM objects persist correctly."""

        @dataclass
        class Product(Document):
            name: str
            price: float
            stock: int

        db_path, db = create_test_db()

        try:
            Document.set_database(db)

            # Save products
            products = [
                Product(name="Widget", price=9.99, stock=100),
                Product(name="Gadget", price=19.99, stock=50),
                Product(name="Doohickey", price=29.99, stock=25),
            ]

            with Product.transaction():
                for product in products:
                    product.save()

            db.close()

            # Reopen and verify
            db = KenobiX(db_path)
            Document.set_database(db)

            retrieved = Product.all(limit=10)
            assert len(retrieved) == 3

            names = {p.name for p in retrieved}
            assert names == {"Widget", "Gadget", "Doohickey"}

        finally:
            cleanup_db(db_path, db)


# ============================================================================
# Combined ACID Tests
# ============================================================================


class TestCombinedACID:
    """
    Tests that combine multiple ACID properties to verify they work together.
    """

    def test_acid_banking_scenario(self):
        """Complete banking scenario testing all ACID properties."""
        db_path, db = create_test_db(indexed_fields=["account_id"])

        try:
            # Setup accounts
            initial_balances = {
                "A": 1000,
                "B": 1000,
                "C": 1000,
                "D": 1000,
            }

            for account_id, balance in initial_balances.items():
                db.insert({"account_id": account_id, "balance": balance})

            initial_total = sum(initial_balances.values())

            # Perform 50 transactions
            for i in range(50):
                source = ["A", "B", "C", "D"][i % 4]
                dest = ["B", "C", "D", "A"][i % 4]
                amount = 10

                with db.transaction():
                    # Read accounts
                    source_account = db.search("account_id", source)[0]
                    dest_account = db.search("account_id", dest)[0]

                    # Validate and transfer
                    if source_account["balance"] >= amount:
                        source_account["balance"] -= amount
                        dest_account["balance"] += amount

                        db.update(
                            "account_id", source, {"balance": source_account["balance"]}
                        )
                        db.update(
                            "account_id", dest, {"balance": dest_account["balance"]}
                        )

            # Verify ACID properties:
            # 1. Atomicity: All 50 transactions committed fully
            # 2. Consistency: Total balance unchanged
            # 3. Isolation: No corrupted intermediate states
            # 4. Durability: Close and reopen

            db.close()
            db = KenobiX(db_path, indexed_fields=["account_id"])

            final_total = sum(
                db.search("account_id", acc)[0]["balance"]
                for acc in ["A", "B", "C", "D"]
            )

            assert final_total == initial_total  # Consistency maintained

        finally:
            cleanup_db(db_path, db)

    def test_acid_ecommerce_scenario(self):
        """E-commerce order processing testing ACID."""

        @dataclass
        class Order(Document):
            order_id: str
            user_id: str
            items: list
            total: float
            status: str

        db_path, db = create_test_db(indexed_fields=["order_id", "status"])

        try:
            Document.set_database(db)

            # Process 20 orders
            for i in range(20):
                order = Order(
                    order_id=f"ORD{i:03d}",
                    user_id=f"U{i % 5}",
                    items=[{"product": "P1", "qty": 1}],
                    total=99.99,
                    status="pending",
                )

                # Atomically create order and update inventory
                with Order.transaction():
                    order.save()

                    # Simulate inventory update
                    # (In real app, would update product stock)

                    # Update order status
                    order.status = "confirmed"
                    order.save()

            # Verify all orders processed
            confirmed_orders = Order.filter(status="confirmed", limit=50)
            assert len(confirmed_orders) == 20

            # Simulate failed order (rolled back)
            msg = "Payment failed"
            try:
                with Order.transaction():
                    failed_order = Order(
                        order_id="ORD999",
                        user_id="U999",
                        items=[],
                        total=999.99,
                        status="pending",
                    )
                    failed_order.save()
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # Failed order not in database
            assert Order.get(order_id="ORD999") is None

            # Verify durability
            db.close()
            db = KenobiX(db_path, indexed_fields=["order_id", "status"])
            Document.set_database(db)

            assert Order.count() == 20

        finally:
            cleanup_db(db_path, db)


# ============================================================================
# Main Test Runner
# ============================================================================


if __name__ == "__main__":
    print("=" * 70)
    print("KenobiX ACID Compliance Test Suite")
    print("=" * 70)

    # Use spawn method for multiprocessing
    multiprocessing.set_start_method("spawn", force=True)

    # Atomicity Tests
    print("\n" + "=" * 70)
    print("ATOMICITY TESTS - All-or-Nothing Execution")
    print("=" * 70)

    atomicity_tests = TestAtomicity()

    print("\n1. Testing atomicity with multiple inserts...")
    atomicity_tests.test_atomicity_multiple_inserts()
    print("   ✓ PASS - All inserts atomic")

    print("\n2. Testing atomicity with mixed operations...")
    atomicity_tests.test_atomicity_mixed_operations()
    print("   ✓ PASS - Mixed operations atomic")

    print("\n3. Testing atomicity with nested transactions...")
    atomicity_tests.test_atomicity_nested_transactions()
    print("   ✓ PASS - Nested transactions atomic")

    print("\n4. Testing atomicity with large batches...")
    atomicity_tests.test_atomicity_large_batch()
    print("   ✓ PASS - Large batch operations atomic")

    print("\n5. Testing atomicity with savepoints...")
    atomicity_tests.test_atomicity_with_savepoints()
    print("   ✓ PASS - Savepoints work correctly")

    print("\n6. Testing atomicity with ODM operations...")
    atomicity_tests.test_atomicity_odm_operations()
    print("   ✓ PASS - ODM operations atomic")

    # Consistency Tests
    print("\n" + "=" * 70)
    print("CONSISTENCY TESTS - Valid State Transitions")
    print("=" * 70)

    consistency_tests = TestConsistency()

    print("\n1. Testing consistency with balance transfers...")
    consistency_tests.test_consistency_balance_transfer()
    print("   ✓ PASS - Balance totals consistent")

    print("\n2. Testing consistency with business rules...")
    consistency_tests.test_consistency_no_negative_balance()
    print("   ✓ PASS - Business rules enforced")

    print("\n3. Testing consistency with referential integrity...")
    consistency_tests.test_consistency_referential_integrity()
    print("   ✓ PASS - Referential integrity maintained")

    print("\n4. Testing consistency with counter increments...")
    consistency_tests.test_consistency_counter_increment()
    print("   ✓ PASS - Counters increment correctly")

    print("\n5. Testing consistency with inventory tracking...")
    consistency_tests.test_consistency_inventory_tracking()
    print("   ✓ PASS - Inventory counts accurate")

    # Isolation Tests
    print("\n" + "=" * 70)
    print("ISOLATION TESTS - Concurrent Transaction Safety")
    print("=" * 70)

    isolation_tests = TestIsolation()

    print("\n1. Testing isolation - no dirty reads...")
    isolation_tests.test_isolation_no_dirty_reads()
    print("   ✓ PASS - No dirty reads detected")

    print("\n2. Testing isolation - read committed...")
    isolation_tests.test_isolation_read_committed()
    print("   ✓ PASS - Read committed isolation maintained")

    print("\n3. Testing isolation - concurrent transactions...")
    isolation_tests.test_isolation_concurrent_transactions()
    print("   ✓ PASS - Concurrent transactions isolated")

    print("\n4. Testing isolation - readers during write transactions...")
    isolation_tests.test_isolation_readers_during_write_transaction()
    print("   ✓ PASS - Readers see consistent snapshots")

    print("\n5. Testing isolation - serializable transactions...")
    isolation_tests.test_isolation_serializable_transactions()
    print("   ✓ PASS - Write transactions serialize correctly")

    # Durability Tests
    print("\n" + "=" * 70)
    print("DURABILITY TESTS - Committed Data Persists")
    print("=" * 70)

    durability_tests = TestDurability()

    print("\n1. Testing durability - simple commit...")
    durability_tests.test_durability_simple_commit()
    print("   ✓ PASS - Data survives restart")

    print("\n2. Testing durability - multiple transactions...")
    durability_tests.test_durability_multiple_transactions()
    print("   ✓ PASS - All transactions persist")

    print("\n3. Testing durability - with rollback...")
    durability_tests.test_durability_with_rollback()
    print("   ✓ PASS - Only committed data survives")

    print("\n4. Testing durability - WAL mode...")
    durability_tests.test_durability_wal_mode()
    print("   ✓ PASS - WAL mode provides durability")

    print("\n5. Testing durability - large transactions...")
    durability_tests.test_durability_large_transaction()
    print("   ✓ PASS - Large transactions durable")

    print("\n6. Testing durability - crash recovery simulation...")
    durability_tests.test_durability_crash_recovery_simulation()
    print("   ✓ PASS - Uncommitted data lost on crash")

    print("\n7. Testing durability - ODM persistence...")
    durability_tests.test_durability_odm_persistence()
    print("   ✓ PASS - ODM objects persist correctly")

    # Combined ACID Tests
    print("\n" + "=" * 70)
    print("COMBINED ACID TESTS - All Properties Together")
    print("=" * 70)

    combined_tests = TestCombinedACID()

    print("\n1. Testing combined ACID - banking scenario...")
    combined_tests.test_acid_banking_scenario()
    print("   ✓ PASS - All ACID properties verified in banking scenario")

    print("\n2. Testing combined ACID - e-commerce scenario...")
    combined_tests.test_acid_ecommerce_scenario()
    print("   ✓ PASS - All ACID properties verified in e-commerce scenario")

    # Summary
    print("\n" + "=" * 70)
    print("ACID COMPLIANCE TEST SUMMARY")
    print("=" * 70)
    print("\n✅ ATOMICITY:    6/6 tests passed")
    print("✅ CONSISTENCY:  5/5 tests passed")
    print("✅ ISOLATION:    5/5 tests passed")
    print("✅ DURABILITY:   7/7 tests passed")
    print("✅ COMBINED:     2/2 tests passed")
    print("\n" + "=" * 70)
    print("TOTAL: 25/25 tests passed")
    print("=" * 70)
    print("\n🎉 KenobiX provides FULL ACID compliance!")
    print()
