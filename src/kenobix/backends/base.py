"""
Base classes and protocols for database backends.

This module defines the interface that all database backends must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterator


@runtime_checkable
class SQLDialect(Protocol):
    """
    Protocol defining SQL dialect differences between databases.

    Each backend provides a dialect implementation that handles
    database-specific SQL syntax.
    """

    @property
    def placeholder(self) -> str:
        """
        Return the parameter placeholder for this dialect.

        Returns:
            '?' for SQLite, '%s' for PostgreSQL
        """
        ...

    def json_extract(self, column: str, field: str) -> str:
        """
        Generate SQL for extracting a field from a JSON column.

        Args:
            column: The JSON column name (e.g., 'data')
            field: The field path (e.g., 'name' or 'address.city')

        Returns:
            SQL expression for JSON field extraction
        """
        ...

    def json_extract_path(self, column: str, path: str) -> str:
        """
        Generate SQL for extracting a field using JSON path syntax.

        Args:
            column: The JSON column name
            path: The JSON path (e.g., '$.name' or '$.address.city')

        Returns:
            SQL expression for JSON path extraction
        """
        ...

    def json_array_each(self, column: str, path: str) -> str:
        """
        Generate SQL for iterating over a JSON array.

        Args:
            column: The JSON column name
            path: The JSON path to the array

        Returns:
            SQL expression for array iteration
        """
        ...

    def regex_match(self, column_expr: str) -> str:
        """
        Generate SQL for regex matching.

        Args:
            column_expr: The column or expression to match against

        Returns:
            SQL expression with placeholder for pattern
        """
        ...

    def generated_column(self, name: str, expression: str) -> str:
        """
        Generate SQL for a generated column definition.

        Args:
            name: Column name
            expression: The expression to compute the column value

        Returns:
            SQL column definition
        """
        ...

    def auto_increment_pk(self) -> str:
        """
        Generate SQL for an auto-incrementing primary key column.

        Returns:
            SQL column definition for primary key
        """
        ...

    def insert_returning_id(self, table: str) -> str:
        """
        Generate SQL for INSERT with ID return.

        Args:
            table: Table name

        Returns:
            SQL INSERT statement template with placeholder and RETURNING clause
        """
        ...

    def list_tables_query(self) -> str:
        """
        Generate SQL to list all user tables.

        Returns:
            SQL query that returns table names
        """
        ...

    def database_size_query(self) -> str:
        """
        Generate SQL to get database size in bytes.

        Returns:
            SQL query that returns size as integer
        """
        ...


class DatabaseBackend(ABC):
    """
    Abstract base class for database backends.

    Each backend implementation handles database-specific connection
    management, query execution, and transaction handling.
    """

    def __init__(self) -> None:
        """Initialize the backend."""
        self._connection: Any = None
        self._in_transaction: bool = False
        self._savepoint_counter: int = 0

    @property
    @abstractmethod
    def dialect(self) -> SQLDialect:
        """Return the SQL dialect for this backend."""
        ...

    @property
    def connection(self) -> Any:
        """Return the underlying database connection."""
        return self._connection

    @property
    def in_transaction(self) -> bool:
        """Return whether currently in a transaction."""
        return self._in_transaction

    @in_transaction.setter
    def in_transaction(self, value: bool) -> None:
        """Set transaction state."""
        self._in_transaction = value

    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the database.

        Should be called before any operations.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """
        Close the database connection.

        Should be called when done with the database.
        """
        ...

    @abstractmethod
    def execute(self, query: str, params: tuple | list = ()) -> Any:
        """
        Execute a SQL query with parameters.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Cursor or result object
        """
        ...

    @abstractmethod
    def executemany(self, query: str, params_list: list[tuple | list]) -> Any:
        """
        Execute a SQL query with multiple parameter sets.

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            Cursor or result object
        """
        ...

    @abstractmethod
    def fetchone(self, cursor: Any) -> tuple | None:
        """
        Fetch one row from cursor.

        Args:
            cursor: Database cursor

        Returns:
            Row tuple or None
        """
        ...

    @abstractmethod
    def fetchall(self, cursor: Any) -> list[tuple]:
        """
        Fetch all rows from cursor.

        Args:
            cursor: Database cursor

        Returns:
            List of row tuples
        """
        ...

    @abstractmethod
    def get_last_insert_id(self, cursor: Any) -> int:
        """
        Get the ID of the last inserted row.

        Args:
            cursor: Database cursor from INSERT operation

        Returns:
            The inserted row's ID
        """
        ...

    @abstractmethod
    def get_rowcount(self, cursor: Any) -> int:
        """
        Get the number of affected rows.

        Args:
            cursor: Database cursor

        Returns:
            Number of rows affected
        """
        ...

    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    def maybe_commit(self) -> None:
        """Commit only if not in an explicit transaction."""
        if not self._in_transaction:
            self.commit()

    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin an explicit transaction."""
        ...

    @abstractmethod
    def create_savepoint(self, name: str) -> None:
        """
        Create a savepoint within a transaction.

        Args:
            name: Savepoint name
        """
        ...

    @abstractmethod
    def rollback_to_savepoint(self, name: str) -> None:
        """
        Rollback to a savepoint.

        Args:
            name: Savepoint name
        """
        ...

    @abstractmethod
    def release_savepoint(self, name: str) -> None:
        """
        Release (commit) a savepoint.

        Args:
            name: Savepoint name
        """
        ...

    def new_savepoint_name(self) -> str:
        """Generate a new unique savepoint name."""
        self._savepoint_counter += 1
        return f"sp_{self._savepoint_counter}"

    def reset_savepoint_counter(self) -> None:
        """Reset the savepoint counter (after transaction ends)."""
        self._savepoint_counter = 0

    @abstractmethod
    def add_regexp_support(self) -> None:
        """
        Add REGEXP function support if needed.

        Some databases (like SQLite) need custom function registration.
        """
        ...

    @abstractmethod
    def enable_wal_mode(self) -> None:
        """
        Enable WAL (Write-Ahead Logging) mode if applicable.

        Some databases always use WAL or have different configuration.
        """
        ...

    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table

        Returns:
            True if table exists
        """
        ...

    @abstractmethod
    def get_table_columns(self, table_name: str) -> list[str]:
        """
        Get column names for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of column names
        """
        ...
