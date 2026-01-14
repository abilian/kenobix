# Web UI

KenobiX includes an optional **read-only web interface** for exploring database contents. It provides a clean, responsive UI for browsing collections, viewing documents, and searching across your data.

## Installation

The Web UI is an optional feature. Install it with:

```bash
pip install kenobix[webui]
# or with uv
uv add kenobix[webui]
```

This adds two dependencies:
- **Bottle** - Lightweight web framework
- **Jinja2** - Template engine

## Quick Start

Start the web server:

```bash
# Specify database file
kenobix serve -d mydb.db

# Auto-detect database (if single .db file in current directory)
kenobix serve
```

The server starts at `http://localhost:8000` and automatically opens your browser.

## Command Options

```bash
kenobix serve [options]

Options:
  -d, --database PATH    Path to database file (or auto-detect)
  --host HOST            Bind address (default: 127.0.0.1)
  --port PORT            Port number (default: 8000)
  --no-browser           Don't open browser automatically
  --no-config            Ignore kenobix.toml configuration file
  --validate-config      Validate config file and exit
  -q, --quiet            Suppress startup messages
```

### Examples

```bash
# Custom port
kenobix serve -d mydb.db --port 8080

# Accessible from network (use with caution)
kenobix serve -d mydb.db --host 0.0.0.0

# Headless mode (no browser, quiet)
kenobix serve -d mydb.db --no-browser -q

# Validate configuration without starting server
kenobix serve -d mydb.db --validate-config
```

## Features

### Database Overview

The home page shows:
- List of all collections with document counts
- Total document count across all collections
- Database file size
- Quick access to browse each collection

### Collection Browser

Each collection view provides:
- **Tabular display** with auto-inferred columns
- **Pagination** for large collections
- **Indexed field indicators** showing which fields have indexes
- **Smart column selection** prioritizing indexed and common fields

### Document Detail View

Individual documents are displayed as:
- Formatted JSON with syntax highlighting
- Copy-to-clipboard button
- Navigation back to collection

### Search

Global search across all collections:
- Case-insensitive substring matching
- Search within specific collection or all collections
- Context snippets showing where matches occur
- Direct links to matching documents

### Dark Mode

Toggle between light and dark themes using the moon/sun icon in the navigation bar. Your preference is saved in browser local storage.

## UI Components

### Table Display

Documents are displayed in tables with intelligent column selection:

1. **_id** is always the first column
2. **Indexed fields** are prioritized (shown with indicator)
3. **Common fields** across documents are preferred
4. **Simple types** (string, number, boolean) preferred over complex (array, object)
5. **Maximum 6 columns** by default (configurable)

### Cell Formatting

Values are formatted based on their type:

| Type | Display |
|------|---------|
| `null` | — (em dash) |
| `boolean` | `true` / `false` |
| `number` | Formatted with thousand separators |
| `string` | Truncated if > 50 chars |
| `array` | `[N items]` with tooltip |
| `object` | `{N fields}` with tooltip |

### Pagination

Collections are paginated with 20 documents per page (configurable). Navigation shows:
- Previous/Next buttons
- Current page and total pages
- Direct page links for nearby pages

## Configuration

The Web UI can be customized using a `kenobix.toml` configuration file. See [Configuration](config.md) for details.

Key configuration options:
- Custom theme (light/dark)
- Items per page
- Per-collection column selection
- Custom column labels
- Value formatters (currency, dates, badges)
- Hidden collections

## Security

### Read-Only Access

The Web UI is **strictly read-only**:
- No insert, update, or delete operations
- No database modification endpoints
- Safe for production database exploration

### Network Binding

By default, the server binds to `127.0.0.1` (localhost only):
- Not accessible from other machines
- Safe for local development

When binding to `0.0.0.0` (all interfaces), a warning is displayed:
```
WARNING: Server is accessible from the network.
This server has no authentication. Consider using a reverse proxy.
```

### Recommendations for Production

If exposing the Web UI externally:
1. Use a reverse proxy (nginx, caddy) with authentication
2. Enable HTTPS
3. Restrict access by IP if possible
4. Consider read-only database file permissions

## API Endpoints

The Web UI also provides JSON API endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/stats` | Database statistics |
| `GET /api/collection/<name>` | Collection documents (paginated) |
| `GET /api/collection/<name>/doc/<id>` | Single document |
| `GET /api/search?q=<query>` | Search results |

### Pagination Parameters

Collection API accepts:
- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 20, max: 100)

Example:
```bash
curl "http://localhost:8000/api/collection/users?page=2&per_page=50"
```

## Troubleshooting

### "Web UI not installed"

Install the optional dependency:
```bash
pip install kenobix[webui]
```

### Port already in use

Specify a different port:
```bash
kenobix serve -d mydb.db --port 8080
```

### Config file not loading

Check config file location (must be named `kenobix.toml`):
1. Same directory as database file
2. Current working directory

Validate your config:
```bash
kenobix serve -d mydb.db --validate-config
```

### Browser doesn't open

Use `--no-browser` and open manually:
```bash
kenobix serve -d mydb.db --no-browser
# Then open http://localhost:8000 in your browser
```
