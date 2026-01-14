"""Common CLI utilities.

This module provides utility functions for database resolution
and validation used across CLI commands.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse


def find_database() -> str | None:
    """
    Auto-detect database file.

    Resolution order:
    1. KENOBIX_DATABASE environment variable
    2. Single .db file in current directory

    Returns:
        Path to database file, or None if not found
    """
    # Check environment variable
    env_db = os.environ.get("KENOBIX_DATABASE")
    if env_db:
        return env_db

    # Look for single .db file in current directory
    db_files = list(Path.cwd().glob("*.db"))
    if len(db_files) == 1:
        return str(db_files[0])

    return None


def resolve_database(args: argparse.Namespace) -> str:
    """
    Resolve database path from arguments, environment, or auto-detection.

    Args:
        args: Parsed arguments (may have 'database' attribute)

    Returns:
        Path to database file

    Raises:
        SystemExit: If no database can be resolved
    """
    # Check explicit argument (handle both None and missing attribute)
    db_path = getattr(args, "database", None)
    if db_path is not None:
        return db_path

    # Try auto-detection
    db_path = find_database()
    if db_path:
        return db_path

    # No database found - show helpful error
    print("Error: No database specified.", file=sys.stderr)
    print("\nSpecify a database using one of:", file=sys.stderr)
    print("  -d/--database option:  kenobix dump -d mydb.db", file=sys.stderr)
    print(
        "  Environment variable:  KENOBIX_DATABASE=mydb.db kenobix dump",
        file=sys.stderr,
    )
    print(
        "  Auto-detection:        Place a single .db file in current directory",
        file=sys.stderr,
    )
    sys.exit(1)


def check_database_exists(db_path: str) -> None:
    """Check if database file exists and exit if not."""
    if not Path(db_path).exists():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)


def get_all_tables(db_path: str) -> list[str]:
    """
    Get all table names from the database.

    Args:
        db_path: Path to the SQLite database

    Returns:
        List of table names
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables except SQLite internal tables
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )

    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables
