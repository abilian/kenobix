"""
SQLite database backend for KenobiX.

This is the default backend, using Python's built-in sqlite3 module.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from .base import DatabaseBackend, SQLDialect


class SQLiteDialect:
    """SQL dialect implementation for SQLite."""

    @property
    def placeholder(self) -> str:
        """SQLite uses ? for placeholders."""
        return "?"

    def json_extract(self, column: str, field: str) -> str:
        """
        Generate SQLite JSON extract expression.

        Args:
            column: JSON column name
            field: Field name (without $. prefix)

        Returns:
            SQLite json_extract expression
        """
        return f"json_extract({column}, '$.{field}')"

    def json_extract_path(self, column: str, path: str) -> str:
        """
        Generate SQLite JSON extract expression from path.

        Args:
            column: JSON column name
            path: JSON path (e.g., '$.name')

        Returns:
            SQLite json_extract expression
        """
        return f"json_extract({column}, '{path}')"

    def json_array_each(self, column: str, path: str) -> str:
        """
        Generate SQLite json_each expression.

        Args:
            column: JSON column name
            path: JSON path to the array

        Returns:
            SQLite json_each expression for use in FROM clause
        """
        return f"json_each({column}, '{path}')"

    def regex_match(self, column_expr: str) -> str:
        """
        Generate SQLite REGEXP expression.

        Args:
            column_expr: Column or expression to match

        Returns:
            SQLite REGEXP expression with placeholder
        """
        return f"{column_expr} REGEXP ?"

    def generated_column(self, name: str, expression: str) -> str:
        """
        Generate SQLite VIRTUAL generated column definition.

        Args:
            name: Column name
            expression: SQL expression for the column

        Returns:
            SQLite generated column definition
        """
        return f"{name} TEXT GENERATED ALWAYS AS ({expression}) VIRTUAL"

    def auto_increment_pk(self) -> str:
        """Return SQLite auto-increment primary key definition."""
        return "id INTEGER PRIMARY KEY AUTOINCREMENT"

    def insert_returning_id(self, table: str) -> str:
        """
        Generate SQLite INSERT statement.

        Note: SQLite doesn't support RETURNING, so we use lastrowid.

        Args:
            table: Table name

        Returns:
            INSERT statement template
        """
        return f"INSERT INTO {table} (data) VALUES (?)"

    def list_tables_query(self) -> str:
        """Return SQLite query to list tables."""
        return (
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )

    def database_size_query(self) -> str:
        """Return SQLite query to get database size."""
        return "SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()"


class SQLiteBackend(DatabaseBackend):
    """
    SQLite database backend implementation.

    Uses Python's built-in sqlite3 module with WAL mode for concurrency.
    """

    def __init__(self, file_path: str) -> None:
        """
        Initialize SQLite backend.

        Args:
            file_path: Path to SQLite database file, or ":memory:" for in-memory
        """
        super().__init__()
        self.file_path = file_path
        self._dialect = SQLiteDialect()

    @property
    def dialect(self) -> SQLDialect:
        """Return SQLite dialect."""
        return self._dialect

    def connect(self) -> None:
        """Connect to SQLite database."""
        self._connection = sqlite3.connect(
            self.file_path, check_same_thread=False
        )

    def close(self) -> None:
        """Close SQLite connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def execute(self, query: str, params: tuple | list = ()) -> Any:
        """
        Execute a SQL query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            SQLite cursor

        Raises:
            sqlite3.ProgrammingError: If connection is closed
        """
        if self._connection is None:
            msg = "Cannot operate on a closed database."
            raise sqlite3.ProgrammingError(msg)
        return self._connection.execute(query, params)

    def executemany(self, query: str, params_list: list[tuple | list]) -> Any:
        """
        Execute a SQL query with multiple parameter sets.

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            SQLite cursor
        """
        return self._connection.executemany(query, params_list)

    def fetchone(self, cursor: Any) -> tuple | None:
        """Fetch one row from cursor."""
        return cursor.fetchone()

    def fetchall(self, cursor: Any) -> list[tuple]:
        """Fetch all rows from cursor."""
        return cursor.fetchall()

    def get_last_insert_id(self, cursor: Any) -> int:
        """Get last inserted row ID using SQLite's lastrowid."""
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def get_rowcount(self, cursor: Any) -> int:
        """Get number of affected rows."""
        return cursor.rowcount

    def commit(self) -> None:
        """Commit transaction."""
        self._connection.commit()

    def rollback(self) -> None:
        """Rollback transaction."""
        self._connection.rollback()

    def begin_transaction(self) -> None:
        """Begin explicit transaction."""
        self._connection.execute("BEGIN")
        self._in_transaction = True

    def create_savepoint(self, name: str) -> None:
        """Create a savepoint."""
        self._connection.execute(f"SAVEPOINT {name}")

    def rollback_to_savepoint(self, name: str) -> None:
        """Rollback to a savepoint."""
        self._connection.execute(f"ROLLBACK TO SAVEPOINT {name}")

    def release_savepoint(self, name: str) -> None:
        """Release a savepoint."""
        self._connection.execute(f"RELEASE SAVEPOINT {name}")

    def add_regexp_support(self) -> None:
        """Add REGEXP function to SQLite."""

        def regexp(pattern: str, value: str) -> bool:
            if value is None:
                return False
            return re.search(pattern, value) is not None

        self._connection.create_function("REGEXP", 2, regexp)

    def enable_wal_mode(self) -> None:
        """Enable WAL mode for better concurrency."""
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.commit()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in SQLite."""
        cursor = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def get_table_columns(self, table_name: str) -> list[str]:
        """Get column names for a table."""
        cursor = self._connection.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]
