"""Configuration system for KenobiX Web UI.

Loads optional configuration from kenobix.toml files.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Configuration validation error."""


@dataclass
class CollectionConfig:
    """Configuration for a single collection."""

    name: str
    display_name: str | None = None
    description: str | None = None
    columns: list[str] | None = None  # None = auto-infer
    labels: dict[str, str] = field(default_factory=dict)
    format: dict[str, str] = field(default_factory=dict)
    sort_by: str = "_id"
    sort_order: str = "asc"
    hidden: bool = False

    def get_label(self, column: str) -> str:
        """Get display label for a column."""
        if column in self.labels:
            return self.labels[column]
        return format_column_name(column)

    def get_formatter(self, column: str) -> str:
        """Get formatter for a column."""
        return self.format.get(column, "auto")


@dataclass
class WebUIConfig:
    """Global Web UI configuration."""

    theme: str = "light"
    per_page: int = 20
    date_format: str = "%Y-%m-%d %H:%M"
    number_format: str = "comma"
    max_columns: int = 6
    collections: dict[str, CollectionConfig] = field(default_factory=dict)

    def get_collection(self, name: str) -> CollectionConfig:
        """Get config for a collection, creating default if not configured."""
        if name not in self.collections:
            self.collections[name] = CollectionConfig(name=name)
        return self.collections[name]

    def is_collection_hidden(self, name: str) -> bool:
        """Check if a collection should be hidden from the UI."""
        if name in self.collections:
            return self.collections[name].hidden
        return False


def format_column_name(name: str) -> str:
    """Convert column name to display label.

    Examples:
        _id -> ID
        user_name -> User Name
        firstName -> First Name
        createdAt -> Created At
    """
    if name == "_id":
        return "ID"

    # Handle snake_case
    if "_" in name:
        return " ".join(word.capitalize() for word in name.split("_"))

    # Handle camelCase/PascalCase
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", name)
    if words:
        return " ".join(word.capitalize() for word in words)

    return name.capitalize()


# Module-level config cache
_config: WebUIConfig | None = None
_config_path: Path | None = None


def get_config() -> WebUIConfig:
    """Get the current configuration (must call load_config first)."""
    if _config is None:
        return WebUIConfig()
    return _config


def get_config_path() -> Path | None:
    """Get the path to the loaded config file, or None if using defaults."""
    return _config_path


def load_config(
    db_path: str,
    *,
    ignore_config: bool = False,
    config_path: str | Path | None = None,
) -> WebUIConfig:
    """Load configuration from TOML file or return defaults.

    Args:
        db_path: Path to the database file
        ignore_config: If True, skip config file and use defaults
        config_path: Explicit path to config file (overrides auto-discovery)

    Returns:
        WebUIConfig instance

    Raises:
        ConfigError: If config file is invalid or not found (when explicitly specified)
    """
    global _config, _config_path  # noqa: PLW0603

    if ignore_config:
        _config = WebUIConfig()
        _config_path = None
        return _config

    # Use explicit config path if provided
    if config_path is not None:
        resolved_path = Path(config_path)
        if not resolved_path.exists():
            msg = f"Config file not found: {config_path}"
            raise ConfigError(msg)
        found_config_path: Path | None = resolved_path
    else:
        found_config_path = _find_config_file(db_path)

    config_path = found_config_path

    if config_path is None:
        _config = WebUIConfig()
        _config_path = None
        return _config

    try:
        with config_path.open("rb") as f:
            data = tomllib.load(f)

        _config = _parse_config(data, config_path)
        _config_path = config_path
        return _config

    except tomllib.TOMLDecodeError as e:
        msg = f"Invalid TOML in {config_path}: {e}"
        raise ConfigError(msg) from e


def reset_config() -> None:
    """Reset the config cache (useful for testing)."""
    global _config, _config_path  # noqa: PLW0603
    _config = None
    _config_path = None


def _find_config_file(db_path: str) -> Path | None:
    """Find kenobix.toml config file.

    Searches in order:
    1. Same directory as database
    2. Current working directory
    """
    db_dir = Path(db_path).parent

    # Check same directory as database
    config_path = db_dir / "kenobix.toml"
    if config_path.exists():
        return config_path

    # Check current working directory
    config_path = Path("kenobix.toml")
    if config_path.exists():
        return config_path

    return None


def _parse_config(data: dict[str, Any], config_path: Path) -> WebUIConfig:
    """Parse raw TOML data into typed config objects."""
    webui_data = data.get("webui", {})

    # Parse global settings
    config = WebUIConfig(
        theme=webui_data.get("theme", "light"),
        per_page=webui_data.get("per_page", 20),
        date_format=webui_data.get("date_format", "%Y-%m-%d %H:%M"),
        number_format=webui_data.get("number_format", "comma"),
        max_columns=webui_data.get("max_columns", 6),
    )

    # Validate theme
    if config.theme not in ("light", "dark"):
        msg = f"Invalid theme '{config.theme}' in {config_path}. Must be 'light' or 'dark'."
        raise ConfigError(msg)

    # Validate number_format
    if config.number_format not in ("comma", "space", "plain"):
        msg = f"Invalid number_format '{config.number_format}' in {config_path}. Must be 'comma', 'space', or 'plain'."
        raise ConfigError(msg)

    # Validate per_page
    if not isinstance(config.per_page, int) or config.per_page < 1:
        msg = f"Invalid per_page '{config.per_page}' in {config_path}. Must be a positive integer."
        raise ConfigError(msg)

    # Parse per-collection settings
    collections_data = webui_data.get("collections", {})
    for name, coll_data in collections_data.items():
        if not isinstance(coll_data, dict):
            msg = f"Invalid configuration for collection '{name}' in {config_path}. Expected a table."
            raise ConfigError(msg)

        coll_config = CollectionConfig(
            name=name,
            display_name=coll_data.get("display_name"),
            description=coll_data.get("description"),
            columns=coll_data.get("columns"),
            labels=coll_data.get("labels", {}),
            format=coll_data.get("format", {}),
            sort_by=coll_data.get("sort_by", "_id"),
            sort_order=coll_data.get("sort_order", "asc"),
            hidden=coll_data.get("hidden", False),
        )

        # Validate sort_order
        if coll_config.sort_order not in ("asc", "desc"):
            msg = f"Invalid sort_order '{coll_config.sort_order}' for collection '{name}' in {config_path}. Must be 'asc' or 'desc'."
            raise ConfigError(msg)

        # Validate columns is a list if provided
        if coll_config.columns is not None and not isinstance(
            coll_config.columns, list
        ):
            msg = f"Invalid columns for collection '{name}' in {config_path}. Expected an array of column names."
            raise ConfigError(msg)

        config.collections[name] = coll_config

    return config


def validate_config_against_db(db: Any) -> list[str]:
    """Validate config against actual database schema.

    Args:
        db: KenobiX database instance

    Returns:
        List of warning messages
    """
    config = get_config()
    warnings: list[str] = []

    db_collections = db.collections()

    for coll_name, coll_config in config.collections.items():
        if coll_name not in db_collections:
            warnings.append(
                f"Collection '{coll_name}' in config does not exist in database"
            )
            continue

        if coll_config.columns:
            # Sample documents to check column existence
            coll = db.collection(coll_name)
            sample = coll.all(limit=10)
            all_fields: set[str] = set()
            for doc in sample:
                all_fields.update(doc.keys())

            missing_cols = [
                f"Column '{col}' in collection '{coll_name}' not found in sampled documents"
                for col in coll_config.columns
                if col != "_id" and col not in all_fields
            ]
            warnings.extend(missing_cols)

    return warnings
