"""Tests for KenobiX Web UI configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest

from kenobix import KenobiX


# =============================================================================
# Config Module Tests
# =============================================================================


class TestFormatColumnName:
    """Tests for format_column_name function."""

    def test_id_field(self):
        """Test _id is formatted as ID."""
        from kenobix.webui.config import format_column_name

        assert format_column_name("_id") == "ID"

    def test_snake_case(self):
        """Test snake_case to Title Case."""
        from kenobix.webui.config import format_column_name

        assert format_column_name("user_name") == "User Name"
        assert format_column_name("created_at") == "Created At"
        assert format_column_name("first_name") == "First Name"

    def test_camel_case(self):
        """Test camelCase to Title Case."""
        from kenobix.webui.config import format_column_name

        assert format_column_name("firstName") == "First Name"
        assert format_column_name("createdAt") == "Created At"
        assert format_column_name("userId") == "User Id"

    def test_pascal_case(self):
        """Test PascalCase to Title Case."""
        from kenobix.webui.config import format_column_name

        assert format_column_name("FirstName") == "First Name"
        assert format_column_name("UserID") == "User Id"  # Handles consecutive caps


class TestCollectionConfig:
    """Tests for CollectionConfig dataclass."""

    def test_get_label_configured(self):
        """Test get_label returns configured label."""
        from kenobix.webui.config import CollectionConfig

        config = CollectionConfig(
            name="users",
            labels={"email": "Email Address", "name": "Full Name"},
        )

        assert config.get_label("email") == "Email Address"
        assert config.get_label("name") == "Full Name"

    def test_get_label_auto_format(self):
        """Test get_label auto-formats when no label configured."""
        from kenobix.webui.config import CollectionConfig

        config = CollectionConfig(name="users")

        assert config.get_label("user_name") == "User Name"
        assert config.get_label("_id") == "ID"

    def test_get_formatter_configured(self):
        """Test get_formatter returns configured formatter."""
        from kenobix.webui.config import CollectionConfig

        config = CollectionConfig(
            name="orders",
            format={"total": "currency:USD", "status": "badge"},
        )

        assert config.get_formatter("total") == "currency:USD"
        assert config.get_formatter("status") == "badge"

    def test_get_formatter_default(self):
        """Test get_formatter returns 'auto' for unconfigured columns."""
        from kenobix.webui.config import CollectionConfig

        config = CollectionConfig(name="users")

        assert config.get_formatter("name") == "auto"
        assert config.get_formatter("email") == "auto"


class TestWebUIConfig:
    """Tests for WebUIConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        from kenobix.webui.config import WebUIConfig

        config = WebUIConfig()

        assert config.theme == "light"
        assert config.per_page == 20
        assert config.date_format == "%Y-%m-%d %H:%M"
        assert config.number_format == "comma"
        assert config.max_columns == 6

    def test_get_collection_creates_default(self):
        """Test get_collection creates default config if not configured."""
        from kenobix.webui.config import WebUIConfig

        config = WebUIConfig()
        coll = config.get_collection("users")

        assert coll.name == "users"
        assert coll.display_name is None
        assert coll.columns is None

    def test_get_collection_returns_configured(self):
        """Test get_collection returns configured collection."""
        from kenobix.webui.config import CollectionConfig, WebUIConfig

        config = WebUIConfig(
            collections={
                "users": CollectionConfig(
                    name="users",
                    display_name="User Accounts",
                    columns=["_id", "name", "email"],
                )
            }
        )

        coll = config.get_collection("users")
        assert coll.display_name == "User Accounts"
        assert coll.columns == ["_id", "name", "email"]

    def test_is_collection_hidden_default(self):
        """Test is_collection_hidden returns False by default."""
        from kenobix.webui.config import WebUIConfig

        config = WebUIConfig()
        assert config.is_collection_hidden("users") is False

    def test_is_collection_hidden_configured(self):
        """Test is_collection_hidden returns configured value."""
        from kenobix.webui.config import CollectionConfig, WebUIConfig

        config = WebUIConfig(
            collections={
                "_internal": CollectionConfig(name="_internal", hidden=True),
                "users": CollectionConfig(name="users", hidden=False),
            }
        )

        assert config.is_collection_hidden("_internal") is True
        assert config.is_collection_hidden("users") is False


class TestConfigLoading:
    """Tests for config file loading."""

    def test_load_config_no_file(self, tmp_path: Path):
        """Test loading config when no file exists."""
        from kenobix.webui.config import load_config, reset_config

        reset_config()
        db_path = tmp_path / "test.db"
        db_path.touch()

        config = load_config(str(db_path))

        assert config.theme == "light"
        assert config.per_page == 20

    def test_load_config_from_db_dir(self, tmp_path: Path):
        """Test loading config from database directory."""
        from kenobix.webui.config import load_config, reset_config

        reset_config()

        # Create config file
        config_content = """
[webui]
theme = "dark"
per_page = 25
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        db_path = tmp_path / "test.db"
        db_path.touch()

        config = load_config(str(db_path))

        assert config.theme == "dark"
        assert config.per_page == 25

    def test_load_config_with_collections(self, tmp_path: Path):
        """Test loading config with collection settings."""
        from kenobix.webui.config import load_config, reset_config

        reset_config()

        config_content = """
[webui]
theme = "light"

[webui.collections.users]
display_name = "User Accounts"
columns = ["_id", "name", "email"]
labels = { name = "Full Name" }
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        db_path = tmp_path / "test.db"
        db_path.touch()

        config = load_config(str(db_path))
        users = config.get_collection("users")

        assert users.display_name == "User Accounts"
        assert users.columns == ["_id", "name", "email"]
        assert users.get_label("name") == "Full Name"

    def test_load_config_ignore_flag(self, tmp_path: Path):
        """Test ignore_config flag skips config file."""
        from kenobix.webui.config import load_config, reset_config

        reset_config()

        config_content = """
[webui]
theme = "dark"
per_page = 100
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        db_path = tmp_path / "test.db"
        db_path.touch()

        config = load_config(str(db_path), ignore_config=True)

        # Should use defaults, not config file values
        assert config.theme == "light"
        assert config.per_page == 20

    def test_load_config_invalid_theme(self, tmp_path: Path):
        """Test error on invalid theme value."""
        from kenobix.webui.config import ConfigError, load_config, reset_config

        reset_config()

        config_content = """
[webui]
theme = "blue"
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        db_path = tmp_path / "test.db"
        db_path.touch()

        with pytest.raises(ConfigError, match="Invalid theme"):
            load_config(str(db_path))

    def test_load_config_invalid_sort_order(self, tmp_path: Path):
        """Test error on invalid sort_order value."""
        from kenobix.webui.config import ConfigError, load_config, reset_config

        reset_config()

        config_content = """
[webui]
[webui.collections.users]
sort_order = "random"
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        db_path = tmp_path / "test.db"
        db_path.touch()

        with pytest.raises(ConfigError, match="Invalid sort_order"):
            load_config(str(db_path))

    def test_load_config_invalid_toml(self, tmp_path: Path):
        """Test error on invalid TOML syntax."""
        from kenobix.webui.config import ConfigError, load_config, reset_config

        reset_config()

        config_content = """
[webui
theme = "dark"
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        db_path = tmp_path / "test.db"
        db_path.touch()

        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config(str(db_path))


class TestConfigValidation:
    """Tests for config validation against database."""

    def test_validate_missing_collection(self, tmp_path: Path):
        """Test warning for collection that doesn't exist in database."""
        from kenobix.webui.config import (
            CollectionConfig,
            WebUIConfig,
            reset_config,
            validate_config_against_db,
        )
        from kenobix.webui.config import _config  # noqa: PLC2701

        reset_config()

        # Create database with only 'users' collection
        db_path = tmp_path / "test.db"
        db = KenobiX(str(db_path))
        db.insert({"name": "Alice"})
        db.close()

        # Create config with non-existent collection
        import kenobix.webui.config as config_module

        config_module._config = WebUIConfig(
            collections={
                "orders": CollectionConfig(name="orders"),
            }
        )

        db = KenobiX(str(db_path))
        try:
            warnings = validate_config_against_db(db)
            assert any("orders" in w and "does not exist" in w for w in warnings)
        finally:
            db.close()
            reset_config()

    def test_validate_missing_column(self, tmp_path: Path):
        """Test warning for column that doesn't exist in documents."""
        from kenobix.webui.config import (
            CollectionConfig,
            WebUIConfig,
            reset_config,
            validate_config_against_db,
        )

        reset_config()

        # Create database
        db_path = tmp_path / "test.db"
        db = KenobiX(str(db_path))
        db.insert({"name": "Alice", "email": "alice@example.com"})
        db.close()

        # Create config with non-existent column
        import kenobix.webui.config as config_module

        config_module._config = WebUIConfig(
            collections={
                "documents": CollectionConfig(
                    name="documents",
                    columns=["_id", "name", "nonexistent_field"],
                ),
            }
        )

        db = KenobiX(str(db_path))
        try:
            warnings = validate_config_against_db(db)
            assert any("nonexistent_field" in w for w in warnings)
        finally:
            db.close()
            reset_config()


# =============================================================================
# Formatters Module Tests
# =============================================================================


class TestAutoFormat:
    """Tests for auto_format function."""

    def test_null_value(self):
        """Test formatting of None."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        result = auto_format(None, config)

        assert result["display"] == "\u2014"  # em dash
        assert result["type"] == "null"

    def test_boolean_true(self):
        """Test formatting of True."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        result = auto_format(True, config)

        assert result["display"] == "true"
        assert result["type"] == "boolean"

    def test_boolean_false(self):
        """Test formatting of False."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        result = auto_format(False, config)

        assert result["display"] == "false"
        assert result["type"] == "boolean"

    def test_integer_comma_format(self):
        """Test formatting of integer with comma separator."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig(number_format="comma")
        result = auto_format(1234567, config)

        assert result["display"] == "1,234,567"
        assert result["type"] == "number"

    def test_integer_space_format(self):
        """Test formatting of integer with space separator."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig(number_format="space")
        result = auto_format(1234567, config)

        assert result["display"] == "1 234 567"
        assert result["type"] == "number"

    def test_integer_plain_format(self):
        """Test formatting of integer with no separator."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig(number_format="plain")
        result = auto_format(1234567, config)

        assert result["display"] == "1234567"
        assert result["type"] == "number"

    def test_float(self):
        """Test formatting of float."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        result = auto_format(3.14159, config)

        assert result["display"] == "3.14"
        assert result["type"] == "number"

    def test_short_string(self):
        """Test formatting of short string."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        result = auto_format("Hello World", config)

        assert result["display"] == "Hello World"
        assert result["type"] == "string"
        assert result["full"] is None

    def test_long_string_truncated(self):
        """Test formatting of long string is truncated."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        long_string = "A" * 100
        result = auto_format(long_string, config, max_length=50)

        assert len(result["display"]) == 51  # 50 + ellipsis
        assert result["display"].endswith("\u2026")
        assert result["type"] == "string truncated"
        assert result["full"] == long_string

    def test_array(self):
        """Test formatting of array."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        result = auto_format([1, 2, 3], config)

        assert result["display"] == "[3 items]"
        assert result["type"] == "array"
        assert result["full"] is not None

    def test_object(self):
        """Test formatting of object/dict."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import auto_format

        config = WebUIConfig()
        result = auto_format({"a": 1, "b": 2}, config)

        assert result["display"] == "{2 fields}"
        assert result["type"] == "object"
        assert result["full"] is not None


class TestCurrencyFormatter:
    """Tests for currency formatter."""

    def test_usd_currency(self):
        """Test USD currency formatting."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig()
        result = format_value(99.99, "currency:USD", config)

        assert result["display"] == "$99.99"
        assert result["type"] == "currency"

    def test_eur_currency(self):
        """Test EUR currency formatting."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig()
        result = format_value(99.99, "currency:EUR", config)

        assert result["display"] == "\u20ac99.99"  # Euro sign
        assert result["type"] == "currency"

    def test_currency_with_thousands(self):
        """Test currency with thousands separator."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig(number_format="comma")
        result = format_value(1234.56, "currency:USD", config)

        assert result["display"] == "$1,234.56"


class TestBadgeFormatter:
    """Tests for badge formatter."""

    def test_badge_simple(self):
        """Test badge formatting."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig()
        result = format_value("active", "badge", config)

        assert result["display"] == "active"
        assert result["type"] == "badge"
        assert result["css_class"] == "badge-active"

    def test_badge_with_spaces(self):
        """Test badge with spaces in value."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig()
        result = format_value("In Progress", "badge", config)

        assert result["display"] == "In Progress"
        assert result["css_class"] == "badge-in-progress"


class TestDateFormatter:
    """Tests for date formatter."""

    def test_iso_date_string(self):
        """Test formatting ISO date string."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig(date_format="%Y-%m-%d")
        result = format_value("2024-01-15T10:30:00Z", "date", config)

        assert result["display"] == "2024-01-15"
        assert result["type"] == "date"

    def test_date_with_custom_format(self):
        """Test date with custom format in config."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig(date_format="%B %d, %Y")
        result = format_value("2024-01-15", "date", config)

        assert result["display"] == "January 15, 2024"


class TestTruncateFormatter:
    """Tests for truncate formatter."""

    def test_truncate_with_length(self):
        """Test truncate with explicit length."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig()
        result = format_value("Hello World", "truncate:5", config)

        assert result["display"] == "Hello\u2026"
        assert result["full"] == "Hello World"

    def test_truncate_short_string(self):
        """Test truncate doesn't truncate short strings."""
        from kenobix.webui.config import WebUIConfig
        from kenobix.webui.formatters import format_value

        config = WebUIConfig()
        result = format_value("Hi", "truncate:10", config)

        assert result["display"] == "Hi"
        assert result["full"] is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestConfigIntegration:
    """Integration tests for config with app."""

    def test_init_app_loads_config(self, tmp_path: Path):
        """Test that init_app loads the config."""
        from kenobix.webui.app import init_app, reset_app
        from kenobix.webui.config import get_config

        reset_app()

        # Create config file
        config_content = """
[webui]
theme = "dark"
per_page = 30
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        # Create database
        db_path = tmp_path / "test.db"
        db = KenobiX(str(db_path))
        db.insert({"name": "Alice"})
        db.close()

        init_app(str(db_path))
        config = get_config()

        assert config.theme == "dark"
        assert config.per_page == 30

        reset_app()

    def test_infer_table_schema_uses_config(self, tmp_path: Path):
        """Test that infer_table_schema uses configured columns."""
        from kenobix.webui.app import (
            infer_table_schema,
            init_app,
            reset_app,
        )

        reset_app()

        # Create config file
        config_content = """
[webui]
[webui.collections.documents]
columns = ["_id", "email", "name"]
labels = { email = "Email Address" }
"""
        (tmp_path / "kenobix.toml").write_text(config_content)

        # Create database
        db_path = tmp_path / "test.db"
        db = KenobiX(str(db_path))
        db.insert({"name": "Alice", "email": "alice@example.com", "age": 30})
        db.close()

        init_app(str(db_path))

        # Test with sample documents
        documents = [{"_id": 1, "name": "Alice", "email": "alice@example.com", "age": 30}]
        columns = infer_table_schema(documents, ["email"], collection_name="documents")

        # Should use configured columns in order
        assert len(columns) == 3
        assert columns[0].name == "_id"
        assert columns[1].name == "email"
        assert columns[1].display_name == "Email Address"
        assert columns[2].name == "name"

        reset_app()
