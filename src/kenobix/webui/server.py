"""
KenobiX Web UI - Server Entry Point.

Provides the run_server function for starting the web UI.
"""

from __future__ import annotations

import sys
import webbrowser
from threading import Timer

from .app import app, init_app


def run_server(
    db_path: str,
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    open_browser: bool = True,
    quiet: bool = False,
) -> None:
    """
    Start the KenobiX Web UI server.

    Args:
        db_path: Path to the KenobiX database file
        host: Host address to bind to
        port: Port number to listen on
        open_browser: Whether to open browser automatically
        quiet: Suppress startup messages
    """
    # Security warning for non-localhost binding
    if host == "0.0.0.0":  # noqa: S104
        print("WARNING: Server is accessible from the network.", file=sys.stderr)
        print(
            "This server has no authentication. Consider using a reverse proxy.",
            file=sys.stderr,
        )
        print(file=sys.stderr)

    # Initialize app with database path
    init_app(db_path)

    # Build URL
    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host  # noqa: S104
    url = f"http://{display_host}:{port}"

    if not quiet:
        print("KenobiX Web UI")
        print(f"Database: {db_path}")
        print(f"Server:   {url}")
        print()
        print("Press Ctrl+C to stop the server")
        print()

    # Open browser after short delay (to let server start)
    if open_browser and host in ("127.0.0.1", "localhost"):

        def open_browser_delayed():
            webbrowser.open(url)

        Timer(0.5, open_browser_delayed).start()

    # Run the server
    try:
        app.run(host=host, port=port, quiet=True)
    except KeyboardInterrupt:
        if not quiet:
            print("\nServer stopped.")
