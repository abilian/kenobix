"""
PostgreSQL database backend for KenobiX.

Requires psycopg2: uv add kenobix[postgres]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import DatabaseBackend, SQLDialect

if TYPE_CHECKING:
    pass

# Import psycopg2 - will raise ImportError if not installed
try:
    import psycopg2
    import psycopg2.pool
except ImportError as e:
    msg = (
        "PostgreSQL support requires psycopg2. "
        "Install with: uv add kenobix[postgres]"
    )
    raise ImportError(msg) from e


class PostgreSQLDialect:
    """SQL dialect implementation for PostgreSQL with JSONB."""

    @property
    def placeholder(self) -> str:
        """PostgreSQL uses %s for placeholders."""
        return "%s"

    def json_extract(self, column: str, field: str) -> str:
        """
        Generate PostgreSQL JSONB extract expression.

        Args:
            column: JSONB column name
            field: Field name (may contain dots for nested access)

        Returns:
            PostgreSQL JSONB expression returning text
        """
        # Handle nested paths like 'address.city'
        parts = field.split(".")
        if len(parts) == 1:
            return f"{column}->>'{field}'"
        else:
            # For nested: data->'address'->>'city'
            accessors = "->".join(f"'{p}'" for p in parts[:-1])
            return f"{column}->{accessors}->>'{parts[-1]}'"

    def json_extract_path(self, column: str, path: str) -> str:
        """
        Generate PostgreSQL JSONB extract expression from path.

        Args:
            column: JSONB column name
            path: JSON path (e.g., '$.name' or '$.address.city')

        Returns:
            PostgreSQL JSONB expression
        """
        # Convert $.field.subfield to PostgreSQL syntax
        field = path.lstrip("$.")
        return self.json_extract(column, field)

    def json_array_each(self, column: str, path: str) -> str:
        """
        Generate PostgreSQL jsonb_array_elements expression.

        Args:
            column: JSONB column name
            path: JSON path to the array (e.g., '$.tags')

        Returns:
            PostgreSQL expression for use in FROM clause
        """
        field = path.lstrip("$.")
        parts = field.split(".")
        if len(parts) == 1:
            return f"jsonb_array_elements({column}->'{field}')"
        else:
            accessors = "->".join(f"'{p}'" for p in parts)
            return f"jsonb_array_elements({column}->{accessors})"

    def regex_match(self, column_expr: str) -> str:
        """
        Generate PostgreSQL regex match expression.

        Args:
            column_expr: Column or expression to match

        Returns:
            PostgreSQL regex expression with placeholder
        """
        return f"{column_expr} ~ %s"

    def generated_column(self, name: str, expression: str) -> str:
        """
        Generate PostgreSQL STORED generated column definition.

        Note: PostgreSQL only supports STORED generated columns, not VIRTUAL.

        Args:
            name: Column name
            expression: SQL expression for the column

        Returns:
            PostgreSQL generated column definition
        """
        return f"{name} TEXT GENERATED ALWAYS AS ({expression}) STORED"

    def auto_increment_pk(self) -> str:
        """Return PostgreSQL auto-increment primary key definition."""
        return "id SERIAL PRIMARY KEY"

    def insert_returning_id(self, table: str) -> str:
        """
        Generate PostgreSQL INSERT statement with RETURNING.

        Args:
            table: Table name

        Returns:
            INSERT statement template with RETURNING clause
        """
        return f"INSERT INTO {table} (data) VALUES (%s) RETURNING id"

    def list_tables_query(self) -> str:
        """Return PostgreSQL query to list tables."""
        return (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )

    def database_size_query(self) -> str:
        """Return PostgreSQL query to get database size."""
        return "SELECT pg_database_size(current_database())"


class PostgreSQLBackend(DatabaseBackend):
    """
    PostgreSQL database backend implementation.

    Uses psycopg2 with connection pooling for concurrent access.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "kenobix",
        user: str = "postgres",
        password: str = "",
        dsn: str | None = None,
        min_connections: int = 1,
        max_connections: int = 10,
    ) -> None:
        """
        Initialize PostgreSQL backend.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            dsn: Full connection string (overrides other params)
            min_connections: Minimum pool connections
            max_connections: Maximum pool connections
        """
        super().__init__()
        self._dialect = PostgreSQLDialect()
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None

        if dsn:
            self._dsn = dsn
        else:
            self._dsn = (
                f"host={host} port={port} dbname={database} "
                f"user={user} password={password}"
            )

        self._min_connections = min_connections
        self._max_connections = max_connections
        self._database = database

    @property
    def dialect(self) -> SQLDialect:
        """Return PostgreSQL dialect."""
        return self._dialect

    def connect(self) -> None:
        """Create connection pool."""
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            self._min_connections,
            self._max_connections,
            self._dsn,
        )
        # Get initial connection for setup
        self._connection = self._pool.getconn()
        # Set autocommit to False for transaction support
        self._connection.autocommit = False

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._connection and self._pool:
            self._pool.putconn(self._connection)
            self._connection = None
        if self._pool:
            self._pool.closeall()
            self._pool = None

    def execute(self, query: str, params: tuple | list = ()) -> Any:
        """
        Execute a SQL query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            PostgreSQL cursor
        """
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        return cursor

    def executemany(self, query: str, params_list: list[tuple | list]) -> Any:
        """
        Execute a SQL query with multiple parameter sets.

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            PostgreSQL cursor
        """
        cursor = self._connection.cursor()
        cursor.executemany(query, params_list)
        return cursor

    def fetchone(self, cursor: Any) -> tuple | None:
        """Fetch one row from cursor."""
        return cursor.fetchone()

    def fetchall(self, cursor: Any) -> list[tuple]:
        """Fetch all rows from cursor."""
        return cursor.fetchall()

    def get_last_insert_id(self, cursor: Any) -> int:
        """
        Get last inserted row ID.

        PostgreSQL requires RETURNING clause, so fetch from cursor.
        """
        row = cursor.fetchone()
        if row:
            return row[0]
        raise RuntimeError("No row returned from INSERT ... RETURNING")

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
        """
        Begin explicit transaction.

        PostgreSQL auto-starts transactions, so just set the flag.
        """
        # PostgreSQL is already in transaction mode by default
        # when autocommit is False
        self._in_transaction = True

    def create_savepoint(self, name: str) -> None:
        """Create a savepoint."""
        self._connection.cursor().execute(f"SAVEPOINT {name}")

    def rollback_to_savepoint(self, name: str) -> None:
        """Rollback to a savepoint."""
        self._connection.cursor().execute(f"ROLLBACK TO SAVEPOINT {name}")

    def release_savepoint(self, name: str) -> None:
        """Release a savepoint."""
        self._connection.cursor().execute(f"RELEASE SAVEPOINT {name}")

    def add_regexp_support(self) -> None:
        """PostgreSQL has native regex support, nothing to do."""
        pass

    def enable_wal_mode(self) -> None:
        """PostgreSQL always uses WAL, nothing to do."""
        pass

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in PostgreSQL."""
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s)",
            (table_name,),
        )
        result = cursor.fetchone()
        return result[0] if result else False

    def get_table_columns(self, table_name: str) -> list[str]:
        """Get column names for a table."""
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table_name,),
        )
        return [row[0] for row in cursor.fetchall()]


def parse_postgres_url(url: str) -> dict[str, Any]:
    """
    Parse a PostgreSQL connection URL.

    Args:
        url: Connection URL like 'postgresql://user:pass@host:port/dbname'

    Returns:
        Dict with connection parameters
    """
    import urllib.parse

    parsed = urllib.parse.urlparse(url)

    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") or "kenobix",
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
    }
