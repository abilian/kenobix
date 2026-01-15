"""
Unit tests for CLI argument parser.

These tests verify parser configuration without executing commands.
"""

from __future__ import annotations

import pytest

from kenobix.cli import create_parser


class TestParserStructure:
    """Tests for parser structure and options."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return create_parser()

    def test_parser_prog_name(self, parser):
        """Should have correct program name."""
        assert parser.prog == "kenobix"

    def test_global_database_option(self, parser):
        """Should have global -d/--database option."""
        # Parse with -d before command
        args = parser.parse_args(["-d", "test.db", "info"])
        assert args.database == "test.db"

    def test_global_verbose_option(self, parser):
        """Should have global -v/--verbose option."""
        args = parser.parse_args(["-v", "-d", "test.db", "info"])
        assert args.verbose == 1

        args = parser.parse_args(["-vv", "-d", "test.db", "info"])
        assert args.verbose == 2

    def test_global_quiet_option(self, parser):
        """Should have global -q/--quiet option."""
        args = parser.parse_args(["-q", "-d", "test.db", "info"])
        assert args.quiet is True

    def test_global_config_option(self, parser):
        """Should have global -c/--config option."""
        args = parser.parse_args(["-c", "config.toml", "-d", "test.db", "serve"])
        assert args.config == "config.toml"


class TestExportCommand:
    """Tests for export command parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return create_parser()

    def test_export_command_exists(self, parser):
        """Should have export command."""
        args = parser.parse_args(["-d", "test.db", "export"])
        assert args.command == "export"

    def test_export_format_option(self, parser):
        """Should have -f/--format option with choices."""
        args = parser.parse_args(["-d", "test.db", "export", "-f", "json"])
        assert args.format == "json"

        args = parser.parse_args(["-d", "test.db", "export", "--format", "csv"])
        assert args.format == "csv"

        args = parser.parse_args(["-d", "test.db", "export", "-f", "sql"])
        assert args.format == "sql"

        args = parser.parse_args(["-d", "test.db", "export", "-f", "flat-sql"])
        assert args.format == "flat-sql"

    def test_export_format_default(self, parser):
        """Should default to json format."""
        args = parser.parse_args(["-d", "test.db", "export"])
        assert args.format == "json"

    def test_export_output_option(self, parser):
        """Should have -o/--output option."""
        args = parser.parse_args(["-d", "test.db", "export", "-o", "out.json"])
        assert args.output == "out.json"

    def test_export_table_option(self, parser):
        """Should have -t/--table option."""
        args = parser.parse_args(["-d", "test.db", "export", "-t", "users"])
        assert args.table == "users"

    def test_export_compact_option(self, parser):
        """Should have --compact option."""
        args = parser.parse_args(["-d", "test.db", "export", "--compact"])
        assert args.compact is True


class TestDumpCommand:
    """Tests for deprecated dump command parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return create_parser()

    def test_dump_command_exists(self, parser):
        """Should have dump command (deprecated alias)."""
        args = parser.parse_args(["-d", "test.db", "dump"])
        assert args.command == "dump"


class TestInfoCommand:
    """Tests for info command parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return create_parser()

    def test_info_command_exists(self, parser):
        """Should have info command."""
        args = parser.parse_args(["-d", "test.db", "info"])
        assert args.command == "info"

    def test_info_table_option(self, parser):
        """Should have -t/--table option."""
        args = parser.parse_args(["-d", "test.db", "info", "-t", "users"])
        assert args.table == "users"


class TestServeCommand:
    """Tests for serve command parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return create_parser()

    def test_serve_command_exists(self, parser):
        """Should have serve command."""
        args = parser.parse_args(["-d", "test.db", "serve"])
        assert args.command == "serve"

    def test_serve_host_option(self, parser):
        """Should have --host option with default."""
        args = parser.parse_args(["-d", "test.db", "serve"])
        assert args.host == "127.0.0.1"

        args = parser.parse_args(["-d", "test.db", "serve", "--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

    def test_serve_port_option(self, parser):
        """Should have --port option with default."""
        args = parser.parse_args(["-d", "test.db", "serve"])
        assert args.port == 8000

        args = parser.parse_args(["-d", "test.db", "serve", "--port", "9000"])
        assert args.port == 9000

    def test_serve_no_browser_option(self, parser):
        """Should have --no-browser option."""
        args = parser.parse_args(["-d", "test.db", "serve", "--no-browser"])
        assert args.no_browser is True

    def test_serve_no_config_option(self, parser):
        """Should have --no-config option."""
        args = parser.parse_args(["-d", "test.db", "serve", "--no-config"])
        assert args.no_config is True

    def test_serve_validate_config_option(self, parser):
        """Should have --validate-config option."""
        args = parser.parse_args(["-d", "test.db", "serve", "--validate-config"])
        assert args.validate_config is True


class TestImportCommand:
    """Tests for import command parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return create_parser()

    def test_import_command_exists(self, parser):
        """Should have import command."""
        args = parser.parse_args(["import", "data.json", "output.db"])
        assert args.command == "import"
        assert args.input == "data.json"
        assert args.dest == "output.db"


class TestMigrateCommand:
    """Tests for migrate command parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return create_parser()

    def test_migrate_command_exists(self, parser):
        """Should have migrate command."""
        args = parser.parse_args(["migrate", "source.db", "dest.db"])
        assert args.command == "migrate"
        assert args.source == "source.db"
        assert args.dest == "dest.db"
