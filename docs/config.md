# Configuration

The KenobiX Web UI can be customized using a `kenobix.toml` configuration file. Configuration is **entirely optional** - everything works with sensible defaults.

## Config File Location

The Web UI looks for `kenobix.toml` in this order:

1. **Same directory as the database file**
2. **Current working directory**

The first file found is used. If no file exists, defaults are applied.

## Basic Example

```toml
# kenobix.toml

[webui]
theme = "dark"
per_page = 25
```

## Full Configuration Reference

### Global Settings

```toml
[webui]
theme = "light"              # "light" or "dark" (default: "light")
per_page = 20                # Items per page (default: 20)
date_format = "%Y-%m-%d %H:%M"  # Python strftime format
number_format = "comma"      # "comma", "space", or "plain"
max_columns = 6              # Max auto-inferred columns (default: 6)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `theme` | string | `"light"` | Default color theme |
| `per_page` | int | `20` | Default pagination size |
| `date_format` | string | `"%Y-%m-%d %H:%M"` | Date display format |
| `number_format` | string | `"comma"` | Number separator style |
| `max_columns` | int | `6` | Maximum columns in auto-inference |

#### Number Format Options

| Value | Example |
|-------|---------|
| `"comma"` | 1,234,567 |
| `"space"` | 1 234 567 |
| `"plain"` | 1234567 |

### Per-Collection Settings

```toml
[webui.collections.users]
display_name = "User Accounts"   # Display name in UI
description = "Registered users" # Optional description
columns = ["_id", "name", "email", "role", "created_at"]
labels = { name = "Full Name", email = "Email Address" }
format = { created_at = "date", role = "badge" }
sort_by = "name"                 # Default sort column
sort_order = "asc"               # "asc" or "desc"
hidden = false                   # Hide from collection list
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `display_name` | string | Collection name | Human-readable name |
| `description` | string | None | Optional description |
| `columns` | array | Auto-inferred | Columns to display |
| `labels` | table | Auto-formatted | Custom column headers |
| `format` | table | Type-based | Value formatters |
| `sort_by` | string | `"_id"` | Default sort column |
| `sort_order` | string | `"asc"` | Sort direction |
| `hidden` | bool | `false` | Hide collection from UI |

## Value Formatters

Formatters control how cell values are displayed. Specify them in the `format` table:

```toml
[webui.collections.orders]
format = {
    total = "currency:USD",
    status = "badge",
    created_at = "date"
}
```

### Available Formatters

| Formatter | Description | Example Output |
|-----------|-------------|----------------|
| `auto` | Automatic (default) | Based on value type |
| `string` | Plain string | `"Hello World"` |
| `number` | Formatted number | `1,234,567` |
| `currency:CODE` | Currency with symbol | `$99.99`, `€50.00` |
| `date` | Date using global format | `2024-01-15 10:30` |
| `datetime` | Full datetime | `2024-01-15 10:30:45` |
| `boolean` | Boolean display | `true` / `false` |
| `badge` | Styled badge/chip | Status indicators |
| `truncate:N` | Truncate to N chars | `"Long text..."` |
| `json` | Pretty-printed JSON | Collapsible object |

### Currency Codes

Supported currency symbols:

| Code | Symbol |
|------|--------|
| `USD` | $ |
| `EUR` | € |
| `GBP` | £ |
| `JPY` | ¥ |
| `CHF` | CHF |
| `CAD` | CA$ |
| `AUD` | A$ |

## Complete Examples

### E-Commerce Database

```toml
# kenobix.toml

[webui]
theme = "light"
per_page = 25
date_format = "%b %d, %Y"

[webui.collections.users]
display_name = "Customers"
columns = ["_id", "name", "email", "tier", "created_at"]
labels = { tier = "Membership", created_at = "Joined" }
format = { tier = "badge", created_at = "date" }
sort_by = "created_at"
sort_order = "desc"

[webui.collections.products]
display_name = "Product Catalog"
columns = ["_id", "name", "price", "stock", "category"]
labels = { stock = "In Stock" }
format = { price = "currency:USD" }
sort_by = "name"

[webui.collections.orders]
display_name = "Orders"
columns = ["_id", "customer_id", "status", "total", "created_at"]
labels = { customer_id = "Customer", total = "Order Total" }
format = { total = "currency:USD", status = "badge" }
sort_by = "created_at"
sort_order = "desc"

# Hide internal migration tracking
[webui.collections._migrations]
hidden = true
```

### Analytics Database

```toml
# kenobix.toml

[webui]
theme = "dark"
per_page = 50
number_format = "space"  # European style

[webui.collections.events]
display_name = "Analytics Events"
columns = ["_id", "event_type", "user_id", "timestamp", "properties"]
labels = { event_type = "Event", properties = "Data" }
format = { timestamp = "datetime", properties = "json" }
sort_by = "timestamp"
sort_order = "desc"

[webui.collections.sessions]
columns = ["_id", "user_id", "start_time", "duration", "pages"]
labels = { pages = "Page Views" }
format = { start_time = "datetime" }
sort_by = "start_time"
sort_order = "desc"
```

### Minimal Config (Theme Only)

```toml
# kenobix.toml
[webui]
theme = "dark"
```

## Column Auto-Inference

When `columns` is not specified, the UI automatically selects columns using these heuristics:

1. **_id** is always first
2. **Indexed fields** are prioritized
3. **Common fields** (present in most documents) are preferred
4. **Simple types** (string, number, boolean) preferred over complex types
5. Maximum columns limited by `max_columns` setting

## Label Auto-Formatting

When `labels` is not specified, column headers are auto-formatted:

| Field Name | Display Label |
|------------|---------------|
| `_id` | ID |
| `user_name` | User Name |
| `firstName` | First Name |
| `created_at` | Created At |
| `userID` | User Id |

## Validation

Validate your configuration file without starting the server:

```bash
kenobix serve -d mydb.db --validate-config
```

Output shows:
- Config file path (or "none" if using defaults)
- Validation status
- Warnings for missing collections or columns

Example output:
```
Config file: /data/kenobix.toml
Validation: OK

# Or with warnings:
Config file: /data/kenobix.toml
Validation warnings:
  - Collection 'old_table' in config does not exist in database
  - Column 'legacy_field' in collection 'users' not found in sampled documents
```

## Ignoring Configuration

To temporarily ignore the config file and use defaults:

```bash
kenobix serve -d mydb.db --no-config
```

## Programmatic Access

The configuration system can also be accessed programmatically:

```python
from kenobix.webui.config import load_config, get_config

# Load config for a database
config = load_config("/path/to/db.db")

# Access settings
print(config.theme)        # "light" or "dark"
print(config.per_page)     # 20

# Get collection config
users = config.get_collection("users")
print(users.columns)       # ["_id", "name", "email"] or None
print(users.get_label("name"))  # "Full Name" or auto-formatted

# Check if collection is hidden
print(config.is_collection_hidden("_internal"))  # True/False
```
