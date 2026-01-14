"""App state management for KenobiX Web UI.

This module manages the application state, database connections,
and template rendering.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bottle import Bottle, request
from jinja2 import Environment, PackageLoader, select_autoescape

from .config import WebUIConfig, load_config, reset_config


def _get_query_param(name: str, default: str = "") -> str:
    """Get a query string parameter with type-safe access."""
    query = request.query
    try:
        value = query[name]  # pyrefly: ignore[bad-index]
        return value or default
    except KeyError:
        return default


@dataclass
class _AppState:
    """Module-level state container."""

    db_path: str | None = None
    db_name: str | None = None
    config: WebUIConfig = field(default_factory=WebUIConfig)


# Module state (avoids global statement warnings)
_state = _AppState()

# Create Bottle app
app = Bottle()

# Setup Jinja2 environment
env = Environment(
    loader=PackageLoader("kenobix.webui", "templates"),
    autoescape=select_autoescape(["html"]),
)


def get_state() -> _AppState:
    """Get the current app state."""
    return _state


def get_config() -> WebUIConfig:
    """Get the current WebUI config."""
    return _state.config


def init_app(db_path: str, *, ignore_config: bool = False) -> None:
    """
    Initialize the app with database path.

    Args:
        db_path: Path to the KenobiX database file
        ignore_config: If True, skip loading kenobix.toml config file
    """
    _state.db_path = db_path
    _state.db_name = Path(db_path).name
    _state.config = load_config(db_path, ignore_config=ignore_config)


@contextmanager
def get_db():
    """
    Get a database connection.

    Yields:
        KenobiX database instance
    """
    from kenobix import KenobiX  # noqa: PLC0415

    if _state.db_path is None:
        msg = "Database not initialized. Call init_app() first."
        raise RuntimeError(msg)

    db = KenobiX(_state.db_path)
    try:
        yield db
    finally:
        db.close()


def render(template_name: str, **context: Any) -> str:
    """
    Render a Jinja2 template.

    Args:
        template_name: Name of the template file
        **context: Variables to pass to the template

    Returns:
        Rendered HTML string
    """
    tmpl = env.get_template(template_name)
    # Add common context
    context.setdefault("db_name", _state.db_name)
    return tmpl.render(**context)


def reset_app() -> None:
    """Reset app state (useful for testing)."""
    global _state  # noqa: PLW0603
    _state = _AppState()
    reset_config()
