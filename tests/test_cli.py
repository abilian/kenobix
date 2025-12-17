"""
Tests for KenobiX CLI.

Tests cover:
- Database dump functionality
- Database info display
- Error handling for missing files and tables
- Output formatting
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from kenobix import KenobiX
from kenobix.cli import (
    check_database_exists,
    cmd_dump,
    cmd_info,
    dump_database,
    dump_table,
    get_all_tables,
    get_table_info,
    main,
    print_column_details,
    print_database_header,
    print_index_details,
    show_basic_table_list,
    show_database_info,
    show_detailed_table_info,
)


@pytest.fixture
def db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_with_data(db_path):
    """Create a database with sample data."""
    db = KenobiX(str(db_path), indexed_fields=["name", "category"])

    # Insert sample documents
    db.insert({"name": "Alice", "age": 30, "category": "user"})
    db.insert({"name": "Bob", "age": 25, "category": "user"})
    db.insert({"name": "Widget", "price": 9.99, "category": "product"})

    db.close()
    return db_path


@pytest.fixture
def db_with_collections(db_path):
    """Create a database with multiple collections."""
    db = KenobiX(str(db_path))

    # Create users collection
    users = db.collection("users", indexed_fields=["user_id", "email"])
    users.insert({"user_id": 1, "name": "Alice", "email": "alice@example.com"})
    users.insert({"user_id": 2, "name": "Bob", "email": "bob@example.com"})

    # Create orders collection
    orders = db.collection("orders", indexed_fields=["order_id"])
    orders.insert({"order_id": 101, "user_id": 1, "total": 99.99})

    db.close()
    return db_path


@pytest.fixture
def empty_db(db_path):
    """Create an empty database (no tables)."""
    # Just create the SQLite file without any KenobiX tables
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.close()
    return db_path


class TestCheckDatabaseExists:
    """Tests for check_database_exists function."""

    def test_existing_database_passes(self, db_with_data):
        """Existing database should not raise."""
        # Should not raise
        check_database_exists(str(db_with_data))

    def test_missing_database_exits(self, tmp_path):
        """Missing database should exit with code 1."""
        missing_path = tmp_path / "nonexistent.db"
        with pytest.raises(SystemExit) as exc_info:
            check_database_exists(str(missing_path))
        assert exc_info.value.code == 1


class TestGetAllTables:
    """Tests for get_all_tables function."""

    def test_returns_table_names(self, db_with_data):
        """Should return list of table names."""
        tables = get_all_tables(str(db_with_data))
        assert "documents" in tables

    def test_returns_multiple_collections(self, db_with_collections):
        """Should return all collection tables."""
        tables = get_all_tables(str(db_with_collections))
        assert "users" in tables
        assert "orders" in tables

    def test_empty_database_returns_empty_list(self, empty_db):
        """Empty database should return empty list."""
        tables = get_all_tables(str(empty_db))
        assert tables == []

    def test_excludes_sqlite_internal_tables(self, db_with_data):
        """Should not include sqlite_ prefixed tables."""
        tables = get_all_tables(str(db_with_data))
        for table in tables:
            assert not table.startswith("sqlite_")


class TestDumpTable:
    """Tests for dump_table function."""

    def test_dumps_all_records(self, db_with_data):
        """Should dump all records from table."""
        records = dump_table(str(db_with_data), "documents")
        assert len(records) == 3

    def test_includes_id_field(self, db_with_data):
        """Each record should have _id field."""
        records = dump_table(str(db_with_data), "documents")
        for record in records:
            assert "_id" in record

    def test_includes_document_data(self, db_with_data):
        """Records should include original document data."""
        records = dump_table(str(db_with_data), "documents")
        names = [r.get("name") for r in records]
        assert "Alice" in names
        assert "Bob" in names
        assert "Widget" in names


class TestGetTableInfo:
    """Tests for get_table_info function."""

    def test_returns_table_name(self, db_with_data):
        """Should include table name."""
        info = get_table_info(str(db_with_data), "documents")
        assert info["name"] == "documents"

    def test_returns_row_count(self, db_with_data):
        """Should include accurate row count."""
        info = get_table_info(str(db_with_data), "documents")
        assert info["row_count"] == 3

    def test_returns_columns(self, db_with_data):
        """Should include column information."""
        info = get_table_info(str(db_with_data), "documents")
        assert len(info["columns"]) > 0
        column_names = [c["name"] for c in info["columns"]]
        assert "id" in column_names
        assert "data" in column_names

    def test_returns_indexes(self, db_with_data):
        """Should include index information."""
        info = get_table_info(str(db_with_data), "documents")
        assert "indexes" in info


class TestDumpDatabase:
    """Tests for dump_database function."""

    def test_dumps_to_stdout(self, db_with_data, capsys):
        """Should print JSON to stdout when no output file specified."""
        dump_database(str(db_with_data))
        captured = capsys.readouterr()

        # Should be valid JSON
        data = json.loads(captured.out)
        assert "database" in data
        assert "tables" in data

    def test_dumps_specific_table(self, db_with_collections, capsys):
        """Should dump only specified table."""
        dump_database(str(db_with_collections), table_name="users")
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "users" in data["tables"]
        assert "orders" not in data["tables"]

    def test_dumps_to_file(self, db_with_data, tmp_path):
        """Should write JSON to file when output specified."""
        output_file = tmp_path / "dump.json"
        dump_database(str(db_with_data), output_file=str(output_file))

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "database" in data

    def test_exits_on_missing_database(self, tmp_path):
        """Should exit when database doesn't exist."""
        missing = tmp_path / "missing.db"
        with pytest.raises(SystemExit) as exc_info:
            dump_database(str(missing))
        assert exc_info.value.code == 1

    def test_exits_on_invalid_table(self, db_with_data):
        """Should exit when specified table doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            dump_database(str(db_with_data), table_name="nonexistent")
        assert exc_info.value.code == 1

    def test_exits_gracefully_on_empty_database(self, empty_db):
        """Should exit gracefully when database has no tables."""
        with pytest.raises(SystemExit) as exc_info:
            dump_database(str(empty_db))
        assert exc_info.value.code == 0


class TestShowDatabaseInfo:
    """Tests for show_database_info function."""

    def test_shows_basic_info(self, db_with_data, capsys):
        """Should show database name and table count."""
        show_database_info(str(db_with_data), verbosity=0)
        captured = capsys.readouterr()

        assert "Database:" in captured.out
        assert "Tables:" in captured.out

    def test_shows_table_counts(self, db_with_data, capsys):
        """Should show record counts per table."""
        show_database_info(str(db_with_data), verbosity=0)
        captured = capsys.readouterr()

        assert "documents" in captured.out
        assert "3" in captured.out  # 3 records

    def test_verbose_shows_columns(self, db_with_data, capsys):
        """Verbose mode should show column details."""
        show_database_info(str(db_with_data), verbosity=2)
        captured = capsys.readouterr()

        assert "Column Details:" in captured.out
        assert "id" in captured.out
        assert "data" in captured.out

    def test_exits_on_missing_database(self, tmp_path):
        """Should exit when database doesn't exist."""
        missing = tmp_path / "missing.db"
        with pytest.raises(SystemExit) as exc_info:
            show_database_info(str(missing))
        assert exc_info.value.code == 1

    def test_handles_empty_database(self, empty_db, capsys):
        """Should handle empty database gracefully."""
        show_database_info(str(empty_db))
        captured = capsys.readouterr()
        assert "No tables found" in captured.out


class TestPrintHelpers:
    """Tests for print helper functions."""

    def test_print_database_header(self, db_with_data, capsys):
        """Should print database header information."""
        tables = get_all_tables(str(db_with_data))
        print_database_header(str(db_with_data), tables)
        captured = capsys.readouterr()

        assert "Database:" in captured.out
        assert "Size:" in captured.out
        assert "Tables:" in captured.out

    def test_print_column_details(self, capsys):
        """Should print column information."""
        columns = [
            {"name": "id", "type": "INTEGER", "primary_key": True, "notnull": True, "default": None},
            {"name": "data", "type": "TEXT", "primary_key": False, "notnull": True, "default": None},
        ]
        print_column_details(columns)
        captured = capsys.readouterr()

        assert "id" in captured.out
        assert "INTEGER" in captured.out
        assert "PRIMARY KEY" in captured.out

    def test_print_index_details_empty(self, capsys):
        """Should handle empty index list."""
        print_index_details([], verbosity=2)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_index_details_with_indexes(self, capsys):
        """Should print index information."""
        indexes = [{"name": "idx_name", "columns": ["name"]}]
        print_index_details(indexes, verbosity=2)
        captured = capsys.readouterr()

        assert "Indexes:" in captured.out
        assert "idx_name" in captured.out

    def test_show_basic_table_list(self, db_with_data, capsys):
        """Should show table names with counts."""
        tables = get_all_tables(str(db_with_data))
        show_basic_table_list(str(db_with_data), tables)
        captured = capsys.readouterr()

        assert "Tables:" in captured.out
        assert "documents" in captured.out

    def test_show_detailed_table_info(self, db_with_data, capsys):
        """Should show detailed table information."""
        tables = get_all_tables(str(db_with_data))
        show_detailed_table_info(str(db_with_data), tables, verbosity=1)
        captured = capsys.readouterr()

        assert "Table Details:" in captured.out
        assert "documents" in captured.out
        assert "Records:" in captured.out


class TestCmdHandlers:
    """Tests for command handler functions."""

    def test_cmd_dump(self, db_with_data, capsys):
        """cmd_dump should call dump_database."""
        args = argparse.Namespace(
            database=str(db_with_data),
            output=None,
            table=None,
        )
        cmd_dump(args)
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_cmd_info(self, db_with_data, capsys):
        """cmd_info should call show_database_info."""
        args = argparse.Namespace(
            database=str(db_with_data),
            verbose=0,
        )
        cmd_info(args)
        captured = capsys.readouterr()

        assert "Database:" in captured.out


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_dump_command(self, db_with_data, capsys, monkeypatch):
        """Main should handle dump command."""
        monkeypatch.setattr("sys.argv", ["kenobix", "dump", str(db_with_data)])
        main()
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_info_command(self, db_with_data, capsys, monkeypatch):
        """Main should handle info command."""
        monkeypatch.setattr("sys.argv", ["kenobix", "info", str(db_with_data)])
        main()
        captured = capsys.readouterr()

        assert "Database:" in captured.out

    def test_info_verbose(self, db_with_data, capsys, monkeypatch):
        """Info command with -v flag should show details."""
        monkeypatch.setattr("sys.argv", ["kenobix", "info", "-v", str(db_with_data)])
        main()
        captured = capsys.readouterr()

        assert "Table Details:" in captured.out

    def test_info_very_verbose(self, db_with_data, capsys, monkeypatch):
        """Info command with -vv should show column details."""
        monkeypatch.setattr("sys.argv", ["kenobix", "info", "-vv", str(db_with_data)])
        main()
        captured = capsys.readouterr()

        assert "Column Details:" in captured.out

    def test_dump_with_table_option(self, db_with_collections, capsys, monkeypatch):
        """Dump with -t option should dump only that table."""
        monkeypatch.setattr("sys.argv", ["kenobix", "dump", "-t", "users", str(db_with_collections)])
        main()
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "users" in data["tables"]
        assert "orders" not in data["tables"]

    def test_dump_with_output_option(self, db_with_data, tmp_path, capsys, monkeypatch):
        """Dump with -o option should write to file."""
        output_file = tmp_path / "output.json"
        monkeypatch.setattr("sys.argv", ["kenobix", "dump", "-o", str(output_file), str(db_with_data)])
        main()

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "tables" in data

    def test_missing_command_exits(self, monkeypatch):
        """Missing command should exit with error."""
        monkeypatch.setattr("sys.argv", ["kenobix"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2  # argparse error code

    def test_version_flag(self, capsys, monkeypatch):
        """--version flag should show version."""
        monkeypatch.setattr("sys.argv", ["kenobix", "--version"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "kenobix" in captured.out


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_json_in_data(self, db_path, capsys):
        """Should handle invalid JSON in data column gracefully."""
        import sqlite3

        # Create database with invalid JSON
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, data TEXT)")
        cursor.execute("INSERT INTO documents (data) VALUES ('not valid json')")
        conn.commit()
        conn.close()

        records = dump_table(str(db_path), "documents")
        assert len(records) == 1
        assert "_raw_data" in records[0]
        assert records[0]["_raw_data"] == "not valid json"

    def test_unicode_data(self, db_path, capsys):
        """Should handle unicode data correctly."""
        db = KenobiX(str(db_path))
        db.insert({"name": "日本語", "emoji": "🎉"})
        db.close()

        dump_database(str(db_path))
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        records = data["tables"]["documents"]["records"]
        assert records[0]["name"] == "日本語"
        assert records[0]["emoji"] == "🎉"

    def test_nested_document_data(self, db_path, capsys):
        """Should handle nested document structures."""
        db = KenobiX(str(db_path))
        db.insert({
            "user": {
                "name": "Alice",
                "address": {"city": "Paris", "country": "France"},
            },
            "tags": ["admin", "active"],
        })
        db.close()

        dump_database(str(db_path))
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        records = data["tables"]["documents"]["records"]
        assert records[0]["user"]["address"]["city"] == "Paris"
        assert records[0]["tags"] == ["admin", "active"]
