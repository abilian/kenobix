"""
KenobiX Web UI - Read-only database explorer.

This is an optional module. Install with:
    pip install kenobix[webui]

Usage:
    kenobix serve -d mydb.db
    kenobix serve -d mydb.db --port 8080
"""

from __future__ import annotations

from .app import app, init_app
from .server import run_server

__all__ = ["app", "init_app", "run_server"]
