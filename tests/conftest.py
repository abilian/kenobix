"""
Shared pytest fixtures and configuration.

Test pyramid structure:
- a_unit/: Unit tests (fast, isolated, no DB)
- b_integration/: Integration tests (with database)
- c_e2e/: End-to-end tests (full workflows)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kenobix import KenobiX


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no database)")
    config.addinivalue_line("markers", "integration: Integration tests (with database)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full workflows)")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on directory."""
    for item in items:
        # Get the test file path relative to tests/
        test_path = Path(item.fspath)
        parts = test_path.parts

        if "a_unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "b_integration" in parts:
            item.add_marker(pytest.mark.integration)
        elif "c_e2e" in parts:
            item.add_marker(pytest.mark.e2e)


# Common fixtures


@pytest.fixture
def db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def create_db(db_path):
    """
    Create a KenobiX database instance.

    Usage:
        def test_something(create_db):
            db = create_db()
            db.insert({"key": "value"})
    """
    db = KenobiX(str(db_path))

    def _factory():
        return db

    yield _factory
    db.close()


@pytest.fixture
def db_with_data(db_path):
    """Create a database with sample data."""
    db = KenobiX(str(db_path), indexed_fields=["name", "category"])

    db.insert({"name": "Alice", "age": 30, "category": "user"})
    db.insert({"name": "Bob", "age": 25, "category": "user"})
    db.insert({"name": "Widget", "price": 9.99, "category": "product"})

    db.close()
    return db_path


@pytest.fixture
def db_with_collections(db_path):
    """Create a database with multiple collections."""
    db = KenobiX(str(db_path))

    users = db.collection("users", indexed_fields=["user_id", "email"])
    users.insert({"user_id": 1, "name": "Alice", "email": "alice@example.com"})
    users.insert({"user_id": 2, "name": "Bob", "email": "bob@example.com"})

    orders = db.collection("orders", indexed_fields=["order_id"])
    orders.insert({"order_id": 101, "user_id": 1, "total": 99.99})

    db.close()
    return db_path
