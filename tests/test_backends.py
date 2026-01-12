"""
Tests for database backend abstraction.

These tests verify that the backend abstraction layer works correctly
for both SQLite and PostgreSQL backends.
"""

from __future__ import annotations

import pytest

from kenobix import KenobiX
from kenobix.backends import SQLiteBackend, SQLiteDialect


# ============================================================================
# SQLite Backend Tests
# ============================================================================


class TestSQLiteDialect:
    """Tests for SQLite SQL dialect."""

    def test_placeholder(self):
        """Test SQLite placeholder."""
        dialect = SQLiteDialect()
        assert dialect.placeholder == "?"

    def test_json_extract_simple(self):
        """Test simple JSON field extraction."""
        dialect = SQLiteDialect()
        result = dialect.json_extract("data", "name")
        assert result == "json_extract(data, '$.name')"

    def test_json_extract_nested(self):
        """Test nested JSON field extraction."""
        dialect = SQLiteDialect()
        result = dialect.json_extract("data", "address.city")
        assert result == "json_extract(data, '$.address.city')"

    def test_json_extract_path(self):
        """Test JSON path extraction."""
        dialect = SQLiteDialect()
        result = dialect.json_extract_path("data", "$.name")
        assert result == "json_extract(data, '$.name')"

    def test_json_array_each(self):
        """Test JSON array iteration."""
        dialect = SQLiteDialect()
        result = dialect.json_array_each("data", "$.tags")
        assert result == "json_each(data, '$.tags')"

    def test_regex_match(self):
        """Test regex matching expression."""
        dialect = SQLiteDialect()
        result = dialect.regex_match("column_name")
        assert result == "column_name REGEXP ?"

    def test_generated_column(self):
        """Test generated column definition."""
        dialect = SQLiteDialect()
        result = dialect.generated_column("name", "json_extract(data, '$.name')")
        assert "GENERATED ALWAYS AS" in result
        assert "VIRTUAL" in result

    def test_auto_increment_pk(self):
        """Test auto-increment primary key definition."""
        dialect = SQLiteDialect()
        result = dialect.auto_increment_pk()
        assert "INTEGER PRIMARY KEY AUTOINCREMENT" in result

    def test_insert_returning_id(self):
        """Test insert statement generation."""
        dialect = SQLiteDialect()
        result = dialect.insert_returning_id("users")
        assert "INSERT INTO users" in result

    def test_list_tables_query(self):
        """Test list tables query."""
        dialect = SQLiteDialect()
        result = dialect.list_tables_query()
        assert "sqlite_master" in result

    def test_database_size_query(self):
        """Test database size query."""
        dialect = SQLiteDialect()
        result = dialect.database_size_query()
        assert "page_count" in result


class TestSQLiteBackend:
    """Tests for SQLite backend."""

    def test_create_backend(self, tmp_path):
        """Test creating a SQLite backend."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        try:
            assert backend.connection is not None
        finally:
            backend.close()

    def test_backend_in_memory(self):
        """Test in-memory SQLite backend."""
        backend = SQLiteBackend(":memory:")
        backend.connect()
        try:
            assert backend.connection is not None
            # Create a table and verify it works
            backend.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            backend.execute("INSERT INTO test (name) VALUES (?)", ("Alice",))
            backend.commit()
            cursor = backend.execute("SELECT name FROM test")
            rows = backend.fetchall(cursor)
            assert len(rows) == 1
            assert rows[0][0] == "Alice"
        finally:
            backend.close()

    def test_execute_with_params(self, tmp_path):
        """Test executing queries with parameters."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        try:
            backend.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            backend.execute("INSERT INTO test (name) VALUES (?)", ("Bob",))
            backend.commit()
            cursor = backend.execute("SELECT name FROM test WHERE name = ?", ("Bob",))
            row = backend.fetchone(cursor)
            assert row is not None
            assert row[0] == "Bob"
        finally:
            backend.close()

    def test_executemany(self, tmp_path):
        """Test executing multiple inserts."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        try:
            backend.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            backend.executemany(
                "INSERT INTO test (name) VALUES (?)",
                [("Alice",), ("Bob",), ("Charlie",)],
            )
            backend.commit()
            cursor = backend.execute("SELECT COUNT(*) FROM test")
            row = backend.fetchone(cursor)
            assert row is not None
            assert row[0] == 3
        finally:
            backend.close()

    def test_transaction_state(self, tmp_path):
        """Test transaction state tracking."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        try:
            assert not backend.in_transaction
            backend.begin_transaction()
            assert backend.in_transaction
            backend.in_transaction = False  # Reset for test
        finally:
            backend.close()

    def test_savepoint(self, tmp_path):
        """Test savepoint creation."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        try:
            backend.begin_transaction()
            backend.create_savepoint("sp1")
            backend.rollback_to_savepoint("sp1")
            # Should not raise
        finally:
            backend.rollback()
            backend.close()

    def test_closed_connection_raises(self, tmp_path):
        """Test that operations on closed connection raise error."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        backend.close()

        import sqlite3

        with pytest.raises(sqlite3.ProgrammingError):
            backend.execute("SELECT 1")

    def test_wal_mode(self, tmp_path):
        """Test enabling WAL mode."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        try:
            backend.enable_wal_mode()
            cursor = backend.execute("PRAGMA journal_mode")
            row = backend.fetchone(cursor)
            assert row is not None
            assert row[0].lower() == "wal"
        finally:
            backend.close()

    def test_regexp_support(self, tmp_path):
        """Test REGEXP function support."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.connect()
        try:
            backend.add_regexp_support()
            backend.execute("CREATE TABLE test (name TEXT)")
            backend.execute("INSERT INTO test VALUES ('Alice')")
            backend.execute("INSERT INTO test VALUES ('Bob')")
            backend.commit()

            cursor = backend.execute("SELECT name FROM test WHERE name REGEXP ?", ("^A",))
            rows = backend.fetchall(cursor)
            assert len(rows) == 1
            assert rows[0][0] == "Alice"
        finally:
            backend.close()


# ============================================================================
# KenobiX with Backend Tests
# ============================================================================


class TestKenobiXWithBackend:
    """Tests for KenobiX using explicit backend."""

    def test_create_with_string(self, tmp_path):
        """Test creating KenobiX with connection string."""
        db_path = tmp_path / "test.db"
        db = KenobiX(str(db_path))
        try:
            assert db._backend is not None
            assert isinstance(db._backend, SQLiteBackend)
        finally:
            db.close()

    def test_create_with_path_object(self, tmp_path):
        """Test creating KenobiX with Path object."""
        db_path = tmp_path / "test.db"
        db = KenobiX(db_path)  # Pass Path directly
        try:
            assert db._backend is not None
            assert isinstance(db._backend, SQLiteBackend)
        finally:
            db.close()

    def test_create_with_explicit_backend(self, tmp_path):
        """Test creating KenobiX with explicit backend."""
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        db = KenobiX(backend=backend)
        try:
            assert db._backend is backend
        finally:
            db.close()

    def test_stats_includes_backend(self, tmp_path):
        """Test that stats include backend type."""
        db_path = tmp_path / "test.db"
        db = KenobiX(str(db_path))
        try:
            stats = db.stats()
            assert "backend" in stats
            assert stats["backend"] == "SQLiteBackend"
        finally:
            db.close()

    def test_dialect_access(self, tmp_path):
        """Test accessing dialect through KenobiX."""
        db_path = tmp_path / "test.db"
        db = KenobiX(str(db_path))
        try:
            assert db.dialect is not None
            assert db.dialect.placeholder == "?"
        finally:
            db.close()


# ============================================================================
# PostgreSQL Backend Tests (Skipped if psycopg2 not installed)
# ============================================================================


# Try to import PostgreSQL backend
try:
    from kenobix.backends.postgres import PostgreSQLBackend, PostgreSQLDialect

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="psycopg2 not installed")
class TestPostgreSQLDialect:
    """Tests for PostgreSQL SQL dialect."""

    def test_placeholder(self):
        """Test PostgreSQL placeholder."""
        dialect = PostgreSQLDialect()
        assert dialect.placeholder == "%s"

    def test_json_extract_simple(self):
        """Test simple JSON field extraction."""
        dialect = PostgreSQLDialect()
        result = dialect.json_extract("data", "name")
        assert "data" in result
        assert "name" in result
        assert "->>" in result

    def test_json_extract_nested(self):
        """Test nested JSON field extraction."""
        dialect = PostgreSQLDialect()
        result = dialect.json_extract("data", "address.city")
        assert "data" in result
        assert "address" in result
        assert "city" in result

    def test_regex_match(self):
        """Test regex matching expression."""
        dialect = PostgreSQLDialect()
        result = dialect.regex_match("column_name")
        assert "~" in result

    def test_generated_column(self):
        """Test generated column definition."""
        dialect = PostgreSQLDialect()
        result = dialect.generated_column("name", "data->>'name'")
        assert "GENERATED ALWAYS AS" in result
        assert "STORED" in result

    def test_auto_increment_pk(self):
        """Test auto-increment primary key definition."""
        dialect = PostgreSQLDialect()
        result = dialect.auto_increment_pk()
        assert "SERIAL" in result or "IDENTITY" in result

    def test_insert_returning_id(self):
        """Test insert statement generation."""
        dialect = PostgreSQLDialect()
        result = dialect.insert_returning_id("users")
        assert "INSERT INTO users" in result
        assert "RETURNING id" in result


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="psycopg2 not installed")
class TestPostgreSQLBackend:
    """
    Tests for PostgreSQL backend.

    These tests require a running PostgreSQL server.
    Set KENOBIX_TEST_POSTGRES_URL environment variable to enable.
    """

    @pytest.fixture
    def postgres_url(self):
        """Get PostgreSQL URL from environment or skip."""
        import os

        url = os.environ.get("KENOBIX_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("KENOBIX_TEST_POSTGRES_URL not set")
        return url

    def test_parse_postgres_url(self):
        """Test parsing PostgreSQL connection URL."""
        from kenobix.backends.postgres import parse_postgres_url

        result = parse_postgres_url("postgresql://user:pass@localhost:5432/dbname")
        assert result["host"] == "localhost"
        assert result["port"] == 5432
        assert result["database"] == "dbname"
        assert result["user"] == "user"
        assert result["password"] == "pass"

    def test_parse_postgres_url_minimal(self):
        """Test parsing minimal PostgreSQL connection URL."""
        from kenobix.backends.postgres import parse_postgres_url

        result = parse_postgres_url("postgresql://localhost/mydb")
        assert result["host"] == "localhost"
        assert result["database"] == "mydb"

    def test_kenobix_rejects_invalid_postgres_url(self):
        """Test that KenobiX raises on invalid PostgreSQL URL."""
        # This should fail because we're trying to connect to a non-existent server
        with pytest.raises(Exception):  # Could be ImportError or connection error
            db = KenobiX("postgresql://invalid:5432/nonexistent")
            db.close()
