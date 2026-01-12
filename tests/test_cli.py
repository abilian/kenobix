"""
Tests for KenobiX CLI.

Tests cover:
- Database dump functionality
- Database info display
- Error handling for missing files and tables
- Output formatting
- Database resolution (argument, env var, auto-detection)
- Options before and after command
"""

from __future__ import annotations

import json
import pathlib
import sqlite3

import pytest

from kenobix import KenobiX
from kenobix.cli import (
    check_database_exists,
    cmd_dump,
    cmd_info,
    create_parser,
    dump_database,
    dump_table,
    find_database,
    get_all_tables,
    get_indexed_fields,
    get_table_info,
    infer_json_type,
    infer_pseudo_schema,
    main,
    merge_types,
    print_column_details,
    print_database_header,
    print_index_details,
    resolve_database,
    show_basic_table_list,
    show_database_info,
    show_detailed_table_info,
    show_single_table_info,
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


class TestFindDatabase:
    """Tests for find_database function."""

    def test_finds_env_variable(self, db_with_data, monkeypatch):
        """Should find database from environment variable."""
        monkeypatch.setenv("KENOBIX_DATABASE", str(db_with_data))
        assert find_database() == str(db_with_data)

    def test_finds_single_db_file(self, db_with_data, monkeypatch):
        """Should find single .db file in current directory."""
        monkeypatch.delenv("KENOBIX_DATABASE", raising=False)
        monkeypatch.chdir(db_with_data.parent)
        assert find_database() == str(db_with_data)

    def test_returns_none_when_multiple_db_files(self, tmp_path, monkeypatch):
        """Should return None when multiple .db files exist."""
        monkeypatch.delenv("KENOBIX_DATABASE", raising=False)
        (tmp_path / "one.db").touch()
        (tmp_path / "two.db").touch()
        monkeypatch.chdir(tmp_path)
        assert find_database() is None

    def test_returns_none_when_no_db_files(self, tmp_path, monkeypatch):
        """Should return None when no .db files exist."""
        monkeypatch.delenv("KENOBIX_DATABASE", raising=False)
        monkeypatch.chdir(tmp_path)
        assert find_database() is None


class TestResolveDatabase:
    """Tests for resolve_database function."""

    def test_uses_explicit_argument(self, db_with_data):
        """Should use database from argument."""
        parser = create_parser()
        args = parser.parse_args(["dump", "-d", str(db_with_data)])
        assert resolve_database(args) == str(db_with_data)

    def test_falls_back_to_env_variable(self, db_with_data, monkeypatch):
        """Should fall back to environment variable."""
        monkeypatch.setenv("KENOBIX_DATABASE", str(db_with_data))
        parser = create_parser()
        args = parser.parse_args(["dump"])
        assert resolve_database(args) == str(db_with_data)

    def test_exits_when_no_database(self, tmp_path, monkeypatch):
        """Should exit with helpful error when no database found."""
        monkeypatch.delenv("KENOBIX_DATABASE", raising=False)
        monkeypatch.chdir(tmp_path)
        parser = create_parser()
        args = parser.parse_args(["dump"])
        with pytest.raises(SystemExit) as exc_info:
            resolve_database(args)
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

    def test_compact_output(self, db_with_data, capsys):
        """Compact mode should output JSON without indentation."""
        dump_database(str(db_with_data), compact=True)
        captured = capsys.readouterr()

        # Should be valid JSON without newlines in the middle
        data = json.loads(captured.out)
        assert "database" in data
        # Compact JSON has no indentation
        assert "\n  " not in captured.out

    def test_quiet_mode(self, db_with_data, tmp_path, capsys):
        """Quiet mode should suppress status messages."""
        output_file = tmp_path / "dump.json"
        dump_database(str(db_with_data), output_file=str(output_file), quiet=True)
        captured = capsys.readouterr()

        # Should not print "Database dumped to:" message
        assert "dumped to" not in captured.err

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
            {
                "name": "id",
                "type": "INTEGER",
                "primary_key": True,
                "notnull": True,
                "default": None,
            },
            {
                "name": "data",
                "type": "TEXT",
                "primary_key": False,
                "notnull": True,
                "default": None,
            },
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
        assert not captured.out

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
        parser = create_parser()
        args = parser.parse_args(["dump", "-d", str(db_with_data)])
        cmd_dump(args)
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_cmd_info(self, db_with_data, capsys):
        """cmd_info should call show_database_info."""
        parser = create_parser()
        args = parser.parse_args(["info", "-d", str(db_with_data)])
        cmd_info(args)
        captured = capsys.readouterr()

        assert "Database:" in captured.out


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_dump_command(self, db_with_data, capsys):
        """Main should handle dump command."""
        main(["dump", "-d", str(db_with_data)])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_info_command(self, db_with_data, capsys):
        """Main should handle info command."""
        main(["info", "-d", str(db_with_data)])
        captured = capsys.readouterr()

        assert "Database:" in captured.out

    def test_database_option_before_command(self, db_with_data, capsys):
        """Database option should work before command."""
        main(["-d", str(db_with_data), "dump"])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_database_option_after_command(self, db_with_data, capsys):
        """Database option should work after command."""
        main(["dump", "-d", str(db_with_data)])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_info_verbose(self, db_with_data, capsys):
        """Info command with -v flag should show details."""
        main(["info", "-d", str(db_with_data), "-v"])
        captured = capsys.readouterr()

        assert "Table Details:" in captured.out

    def test_info_very_verbose(self, db_with_data, capsys):
        """Info command with -vv should show column details."""
        main(["info", "-d", str(db_with_data), "-vv"])
        captured = capsys.readouterr()

        assert "Column Details:" in captured.out

    def test_info_with_table_option(self, db_with_collections, capsys):
        """Info with -t option should show detailed info with pseudo-schema."""
        main(["info", "-d", str(db_with_collections), "-t", "users"])
        captured = capsys.readouterr()

        assert "Table: users" in captured.out
        assert "Pseudo-schema" in captured.out
        assert "orders" not in captured.out

    def test_info_with_table_option_verbose(self, db_with_collections, capsys):
        """Info with -t and -v should show sample values."""
        main(["info", "-d", str(db_with_collections), "-t", "users", "-v"])
        captured = capsys.readouterr()

        assert "Table: users" in captured.out
        assert "examples:" in captured.out
        assert "orders" not in captured.out

    def test_info_with_invalid_table(self, db_with_data, capsys):
        """Info with invalid table should exit with error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["info", "-d", str(db_with_data), "-t", "nonexistent"])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_dump_with_table_option(self, db_with_collections, capsys):
        """Dump with -t option should dump only that table."""
        main(["dump", "-d", str(db_with_collections), "-t", "users"])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "users" in data["tables"]
        assert "orders" not in data["tables"]

    def test_dump_with_output_option(self, db_with_data, tmp_path, capsys):
        """Dump with -o option should write to file."""
        output_file = tmp_path / "output.json"
        main(["dump", "-d", str(db_with_data), "-o", str(output_file)])

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "tables" in data

    def test_dump_compact_option(self, db_with_data, capsys):
        """Dump with --compact should output minified JSON."""
        main(["dump", "-d", str(db_with_data), "--compact"])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data
        assert "\n  " not in captured.out

    def test_quiet_option(self, db_with_data, tmp_path, capsys):
        """Quiet option should suppress status messages."""
        output_file = tmp_path / "output.json"
        main(["dump", "-d", str(db_with_data), "-o", str(output_file), "-q"])
        captured = capsys.readouterr()

        assert "dumped to" not in captured.err

    def test_env_variable_database(self, db_with_data, capsys, monkeypatch):
        """Should use KENOBIX_DATABASE environment variable."""
        monkeypatch.setenv("KENOBIX_DATABASE", str(db_with_data))
        main(["dump"])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_auto_detect_database(self, db_with_data, capsys, monkeypatch):
        """Should auto-detect single .db file in current directory."""
        monkeypatch.delenv("KENOBIX_DATABASE", raising=False)
        monkeypatch.chdir(db_with_data.parent)
        main(["dump"])
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert "tables" in data

    def test_no_command_shows_help(self, capsys):
        """No command should show help."""
        main([])
        captured = capsys.readouterr()

        assert "usage:" in captured.out.lower()
        assert "commands:" in captured.out.lower()

    def test_version_flag(self, capsys):
        """--version flag should show version."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "kenobix" in captured.out


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_json_in_data(self, db_path, capsys):
        """Should handle invalid JSON in data column gracefully."""
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

    def test_no_database_specified_shows_help(self, tmp_path, capsys, monkeypatch):
        """Should show helpful error when no database found."""
        monkeypatch.delenv("KENOBIX_DATABASE", raising=False)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(["dump"])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No database specified" in captured.err
        assert "-d/--database" in captured.err


class TestPseudoSchema:
    """Tests for pseudo-schema inference functionality."""

    @pytest.fixture
    def db_with_varied_data(self, tmp_path):
        """Create a database with varied data types for schema inference."""
        db_path = tmp_path / "varied.db"
        db = KenobiX(str(db_path), indexed_fields=["name", "email"])

        # Insert documents with varied fields and types
        db.insert({
            "name": "Alice",
            "email": "alice@example.com",
            "age": 30,
            "active": True,
        })
        db.insert({"name": "Bob", "email": "bob@example.com", "age": 25})
        db.insert({
            "name": "Charlie",
            "email": "charlie@example.com",
            "active": False,
            "tags": ["admin"],
        })
        db.insert({"name": "Diana", "age": 35, "metadata": {"role": "admin"}})
        db.insert({"name": "Eve", "score": 95.5})

        db.close()
        return db_path

    def test_infer_json_type_primitives(self):
        """Should correctly infer types for primitive values."""
        assert infer_json_type(None) == "null"
        assert infer_json_type(True) == "boolean"
        assert infer_json_type(False) == "boolean"
        assert infer_json_type(42) == "integer"
        assert infer_json_type(3.5) == "number"
        assert infer_json_type("hello") == "string"

    def test_infer_json_type_complex(self):
        """Should correctly infer types for complex values."""
        assert infer_json_type([1, 2, 3]) == "array"
        assert infer_json_type({"key": "value"}) == "object"

    def test_merge_types_single(self):
        """Should return single type unchanged."""
        assert merge_types({"string"}) == "string"
        assert merge_types({"integer"}) == "integer"

    def test_merge_types_nullable(self):
        """Should mark nullable types with ?."""
        assert merge_types({"string", "null"}) == "string?"
        assert merge_types({"integer", "null"}) == "integer?"

    def test_merge_types_numeric(self):
        """Should merge integer and number to number."""
        assert merge_types({"integer", "number"}) == "number"

    def test_merge_types_multiple(self):
        """Should join multiple types with |."""
        result = merge_types({"string", "integer"})
        assert "string" in result
        assert "integer" in result
        assert "|" in result

    def test_get_indexed_fields(self, db_with_varied_data):
        """Should detect indexed fields from index names."""
        indexed = get_indexed_fields(str(db_with_varied_data), "documents")
        assert "name" in indexed
        assert "email" in indexed

    def test_get_indexed_fields_empty(self, db_path):
        """Should return empty list for table without indexes."""
        db = KenobiX(str(db_path))
        db.insert({"test": "data"})
        db.close()

        indexed = get_indexed_fields(str(db_path), "documents")
        assert indexed == []

    def test_infer_pseudo_schema_basic(self, db_with_varied_data):
        """Should infer schema from database records."""
        schema = infer_pseudo_schema(str(db_with_varied_data), "documents")

        assert "_meta" in schema
        assert schema["_meta"]["records_analyzed"] == 5

        assert "name" in schema
        assert schema["name"]["type"] == "string"
        assert schema["name"]["presence"] == 1.0

    def test_infer_pseudo_schema_optional_fields(self, db_with_varied_data):
        """Should detect optional fields with presence < 100%."""
        schema = infer_pseudo_schema(str(db_with_varied_data), "documents")

        # email is present in 3/5 records
        assert "email" in schema
        assert schema["email"]["presence"] < 1.0

        # tags is present in 1/5 records
        assert "tags" in schema
        assert schema["tags"]["presence"] < 1.0

    def test_infer_pseudo_schema_mixed_types(self, db_path):
        """Should handle fields with multiple types."""
        db = KenobiX(str(db_path))
        db.insert({"value": 42})
        db.insert({"value": "string"})
        db.insert({"value": None})
        db.close()

        schema = infer_pseudo_schema(str(db_path), "documents")
        assert "value" in schema
        # Type should show both or nullable
        assert "?" in schema["value"]["type"] or "|" in schema["value"]["type"]

    def test_show_single_table_info(self, db_with_varied_data, capsys):
        """Should display table info with pseudo-schema."""
        show_single_table_info(str(db_with_varied_data), "documents")
        captured = capsys.readouterr()

        assert "Table: documents" in captured.out
        assert "Records: 5" in captured.out
        assert "Indexed fields:" in captured.out
        assert "Pseudo-schema" in captured.out
        assert "name:" in captured.out
        assert "[indexed]" in captured.out

    def test_show_single_table_info_verbose(self, db_with_varied_data, capsys):
        """Should show sample values with verbosity."""
        show_single_table_info(str(db_with_varied_data), "documents", verbosity=1)
        captured = capsys.readouterr()

        assert "examples:" in captured.out

    def test_show_single_table_info_very_verbose(self, db_with_varied_data, capsys):
        """Should show SQLite schema with high verbosity."""
        show_single_table_info(str(db_with_varied_data), "documents", verbosity=2)
        captured = capsys.readouterr()

        assert "SQLite Schema:" in captured.out
        assert "Indexes:" in captured.out

    def test_info_single_table_via_main(self, db_with_varied_data, capsys):
        """Main CLI should show pseudo-schema for single table."""
        main(["info", "-d", str(db_with_varied_data), "-t", "documents"])
        captured = capsys.readouterr()

        assert "Pseudo-schema" in captured.out
        assert "name: string" in captured.out
        assert "[indexed]" in captured.out

    def test_info_empty_table_schema(self, db_path, capsys):
        """Should handle empty tables gracefully."""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE empty_table (id INTEGER PRIMARY KEY, data TEXT)")
        conn.commit()
        conn.close()

        show_single_table_info(str(db_path), "empty_table")
        captured = capsys.readouterr()

        assert "Records: 0" in captured.out
        assert "no data to analyze" in captured.out


# ============================================================================
# Import Command Tests
# ============================================================================


class TestImportCommand:
    """Tests for the import CLI command."""

    def test_import_basic(self, tmp_path, capsys):
        """Import command should import JSON to database."""
        json_path = tmp_path / "import.json"
        db_path = tmp_path / "imported.db"

        # Create JSON file
        data = {
            "users": [{"name": "Alice"}, {"name": "Bob"}],
            "products": [{"sku": "SKU001"}],
        }
        with pathlib.Path(json_path).open("w", encoding="utf-8") as f:
            json.dump(data, f)

        main(["import", str(json_path), str(db_path)])
        captured = capsys.readouterr()

        assert "Import complete" in captured.out
        assert "Collections: 2" in captured.out
        assert "Documents:   3" in captured.out

        # Verify database content
        db = KenobiX(str(db_path))
        assert db.collection("users").stats()["document_count"] == 2
        assert db.collection("products").stats()["document_count"] == 1
        db.close()

    def test_import_quiet_mode(self, tmp_path, capsys):
        """Import command should be quiet with -q option."""
        json_path = tmp_path / "import.json"
        db_path = tmp_path / "imported.db"

        # Create JSON file
        data = {"users": [{"name": "Alice"}]}
        with pathlib.Path(json_path).open("w", encoding="utf-8") as f:
            json.dump(data, f)

        main(["import", str(json_path), str(db_path), "-q"])
        captured = capsys.readouterr()

        # Should have no output in quiet mode
        assert captured.out == ""  # noqa: PLC1901
        assert db_path.exists()

    def test_import_missing_file(self, tmp_path, capsys):
        """Import command should error on missing input file."""
        db_path = tmp_path / "dest.db"

        with pytest.raises(SystemExit):
            main(["import", "nonexistent.json", str(db_path)])

        captured = capsys.readouterr()
        assert "Input file not found" in captured.err

    def test_import_invalid_json(self, tmp_path, capsys):
        """Import command should error on invalid JSON."""
        json_path = tmp_path / "invalid.json"
        db_path = tmp_path / "dest.db"

        # Create invalid JSON file
        pathlib.Path(json_path).write_text("not valid json {{{", encoding="utf-8")

        with pytest.raises(SystemExit):
            main(["import", str(json_path), str(db_path)])

        captured = capsys.readouterr()
        assert "Invalid JSON" in captured.err


# ============================================================================
# Migrate Command Tests
# ============================================================================


class TestMigrateCommand:
    """Tests for the migrate CLI command."""

    def test_migrate_basic(self, db_with_collections, tmp_path, capsys):
        """Migrate command should migrate all collections."""
        dest_path = tmp_path / "migrated.db"

        main(["migrate", str(db_with_collections), str(dest_path)])
        captured = capsys.readouterr()

        assert "Migration complete" in captured.out
        assert dest_path.exists()

        # Verify data
        db = KenobiX(str(dest_path))
        assert db.collection("users").stats()["document_count"] == 2
        assert db.collection("orders").stats()["document_count"] == 1
        db.close()

    def test_migrate_single_table(self, db_with_collections, tmp_path, capsys):
        """Migrate command should migrate single table with -t option."""
        dest_path = tmp_path / "migrated.db"

        main(["migrate", str(db_with_collections), str(dest_path), "-t", "users"])
        captured = capsys.readouterr()

        assert "Migration complete" in captured.out
        assert "Collection: users" in captured.out

        # Verify only users migrated
        db = KenobiX(str(dest_path))
        assert db.collection("users").stats()["document_count"] == 2
        db.close()

    def test_migrate_quiet_mode(self, db_with_collections, tmp_path, capsys):
        """Migrate command should be quiet with -q option."""
        dest_path = tmp_path / "migrated.db"

        main(["migrate", str(db_with_collections), str(dest_path), "-q"])
        captured = capsys.readouterr()

        # Should have no output in quiet mode
        assert captured.out == ""  # noqa: PLC1901
        assert dest_path.exists()

    def test_migrate_same_source_dest_error(self, db_with_data, capsys):
        """Migrate command should error when source equals destination."""
        with pytest.raises(SystemExit):
            main(["migrate", str(db_with_data), str(db_with_data)])

        captured = capsys.readouterr()
        assert "Source and destination cannot be the same" in captured.err

    def test_migrate_with_batch_size(self, db_with_collections, tmp_path, capsys):
        """Migrate command should accept --batch-size option."""
        dest_path = tmp_path / "migrated.db"

        main(
            [
                "migrate",
                str(db_with_collections),
                str(dest_path),
                "--batch-size",
                "10",
                "-q",
            ]
        )

        # Verify migration worked
        db = KenobiX(str(dest_path))
        assert db.collection("users").stats()["document_count"] == 2
        db.close()

    def test_migrate_roundtrip(self, db_with_collections, tmp_path, capsys):
        """Migrate to new db and back should preserve data."""
        intermediate = tmp_path / "intermediate.db"
        final = tmp_path / "final.db"

        # Migrate to intermediate
        main(["migrate", str(db_with_collections), str(intermediate), "-q"])

        # Migrate back to final
        main(["migrate", str(intermediate), str(final), "-q"])

        # Verify data preserved
        db = KenobiX(str(final))
        users = db.collection("users")
        assert users.stats()["document_count"] == 2

        alice = users.search("name", "Alice")
        assert len(alice) == 1
        assert alice[0]["email"] == "alice@example.com"
        db.close()
