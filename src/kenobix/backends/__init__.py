"""
KenobiX Database Backends

This module provides database backend implementations for KenobiX.
Currently supports SQLite (default) and PostgreSQL.

Usage:
    # SQLite (default, auto-detected from file path)
    db = KenobiX("mydb.db")
    db = KenobiX(":memory:")

    # PostgreSQL (auto-detected from URL)
    db = KenobiX("postgresql://user:pass@localhost/dbname")

    # Explicit backend
    from kenobix.backends import SQLiteBackend, PostgreSQLBackend
    db = KenobiX(backend=SQLiteBackend("mydb.db"))
    db = KenobiX(backend=PostgreSQLBackend(host="localhost", database="mydb"))
"""

from .base import DatabaseBackend, SQLDialect
from .sqlite import SQLiteBackend, SQLiteDialect

__all__ = [
    "DatabaseBackend",
    "SQLDialect",
    "SQLiteBackend",
    "SQLiteDialect",
]

# PostgreSQL backend is optional (requires psycopg2)
try:
    from .postgres import PostgreSQLBackend, PostgreSQLDialect

    __all__.extend(["PostgreSQLBackend", "PostgreSQLDialect"])
except ImportError:
    pass  # psycopg2 not installed
