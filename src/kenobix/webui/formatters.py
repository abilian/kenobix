"""Value formatters for KenobiX Web UI.

Formatters control how cell values are displayed in tables.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import WebUIConfig


# Currency symbols mapping
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "\u20ac",
    "GBP": "\u00a3",
    "JPY": "\u00a5",
    "CNY": "\u00a5",
    "CHF": "CHF ",
    "CAD": "CA$",
    "AUD": "A$",
}


def format_value(
    value: Any,
    formatter: str,
    config: WebUIConfig,
    max_length: int = 50,
) -> dict[str, Any]:
    """Format a cell value according to formatter spec.

    Args:
        value: The value to format
        formatter: Formatter specification (e.g., "auto", "currency:USD")
        config: WebUI configuration
        max_length: Maximum display length for strings

    Returns:
        Dict with keys: display, type, full, css_class (optional)
    """
    if formatter == "auto":
        return auto_format(value, config, max_length)

    # Parse formatter:arg syntax
    parts = formatter.split(":", 1)
    fmt_name = parts[0]
    fmt_arg = parts[1] if len(parts) > 1 else None

    formatters = {
        "string": _format_string,
        "number": _format_number,
        "currency": _format_currency,
        "date": _format_date,
        "datetime": _format_datetime,
        "boolean": _format_boolean,
        "badge": _format_badge,
        "truncate": _format_truncate,
        "json": _format_json,
    }

    if fmt_name in formatters:
        return formatters[fmt_name](value, fmt_arg, config, max_length)

    return auto_format(value, config, max_length)


def auto_format(  # noqa: C901
    value: Any,
    config: WebUIConfig,
    max_length: int = 50,
) -> dict[str, Any]:
    """Automatically format a value based on its type.

    This is the default formatter when no specific formatter is configured.
    """
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    if isinstance(value, bool):
        return {
            "display": "true" if value else "false",
            "type": "boolean",
            "full": None,
        }

    if isinstance(value, int):
        return {
            "display": _format_integer(value, config.number_format),
            "type": "number",
            "full": None,
        }

    if isinstance(value, float):
        return {
            "display": _format_float(value, config.number_format),
            "type": "number",
            "full": None,
        }

    if isinstance(value, str):
        # Check if it looks like a date/datetime
        if _looks_like_datetime(value):
            return _format_date(value, None, config, max_length)

        if len(value) > max_length:
            return {
                "display": value[:max_length] + "\u2026",
                "type": "string truncated",
                "full": value,
            }
        return {"display": value, "type": "string", "full": None}

    if isinstance(value, list):
        count = len(value)
        item_word = "item" if count == 1 else "items"
        return {
            "display": f"[{count} {item_word}]",
            "type": "array",
            "full": json.dumps(value, indent=2, default=str),
        }

    if isinstance(value, dict):
        count = len(value)
        field_word = "field" if count == 1 else "fields"
        return {
            "display": f"{{{count} {field_word}}}",
            "type": "object",
            "full": json.dumps(value, indent=2, default=str),
        }

    # Fallback for other types
    str_value = str(value)
    if len(str_value) > max_length:
        return {
            "display": str_value[:max_length] + "\u2026",
            "type": "string truncated",
            "full": str_value,
        }
    return {"display": str_value, "type": "string", "full": None}


def _format_integer(value: int, number_format: str) -> str:
    """Format an integer with the configured separator."""
    if number_format == "comma":
        return f"{value:,}"
    if number_format == "space":
        # Format with comma then replace
        return f"{value:,}".replace(",", " ")
    return str(value)


def _format_float(value: float, number_format: str) -> str:
    """Format a float with 2 decimal places and configured separator."""
    if number_format == "comma":
        return f"{value:,.2f}"
    if number_format == "space":
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:.2f}"


def _looks_like_datetime(value: str) -> bool:
    """Check if a string looks like a datetime value."""
    # Common datetime patterns
    patterns = [
        # ISO 8601
        r"^\d{4}-\d{2}-\d{2}",
        # Common date formats
        r"^\d{2}/\d{2}/\d{4}",
        r"^\d{2}-\d{2}-\d{4}",
    ]
    return any(re.match(pattern, value) for pattern in patterns)


def _format_string(
    value: Any,
    arg: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as string."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    str_value = str(value)
    if len(str_value) > max_length:
        return {
            "display": str_value[:max_length] + "\u2026",
            "type": "string truncated",
            "full": str_value,
        }
    return {"display": str_value, "type": "string", "full": None}


def _format_number(
    value: Any,
    arg: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as number."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    try:
        num = float(value)
        if num.is_integer():
            return {
                "display": _format_integer(int(num), config.number_format),
                "type": "number",
                "full": None,
            }
        return {
            "display": _format_float(num, config.number_format),
            "type": "number",
            "full": None,
        }
    except (TypeError, ValueError):
        return {"display": str(value), "type": "string", "full": None}


def _format_currency(
    value: Any,
    currency: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as currency."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    currency = currency or "USD"
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")

    try:
        num = float(value)
        # Format with 2 decimal places
        if config.number_format == "comma":
            formatted = f"{symbol}{num:,.2f}"
        elif config.number_format == "space":
            formatted = f"{symbol}{num:,.2f}".replace(",", " ")
        else:
            formatted = f"{symbol}{num:.2f}"
        return {"display": formatted, "type": "currency", "full": None}
    except (TypeError, ValueError):
        return {"display": str(value), "type": "string", "full": None}


def _format_date(
    value: Any,
    arg: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as date using config's date_format."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    # Use arg as format override if provided, otherwise use config
    date_format = arg or config.date_format

    # Try to parse various date formats
    if isinstance(value, datetime):
        formatted = value.strftime(date_format)
        return {"display": formatted, "type": "date", "full": str(value)}

    if isinstance(value, str):
        # Try common date formats
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(value, fmt)  # noqa: DTZ007
                formatted = dt.strftime(date_format)
                return {"display": formatted, "type": "date", "full": value}
            except ValueError:
                continue

        # If parsing fails, return as string
        return {"display": value, "type": "string", "full": None}

    return {"display": str(value), "type": "string", "full": None}


def _format_datetime(
    value: Any,
    arg: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as datetime with seconds."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    # Use a more detailed format for datetime
    datetime_format = arg or "%Y-%m-%d %H:%M:%S"

    if isinstance(value, datetime):
        formatted = value.strftime(datetime_format)
        return {"display": formatted, "type": "datetime", "full": str(value)}

    if isinstance(value, str):
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(value, fmt)  # noqa: DTZ007
                formatted = dt.strftime(datetime_format)
                return {"display": formatted, "type": "datetime", "full": value}
            except ValueError:
                continue

        return {"display": value, "type": "string", "full": None}

    return {"display": str(value), "type": "string", "full": None}


def _format_boolean(
    value: Any,
    arg: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as boolean."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    # Handle various boolean representations
    if isinstance(value, bool):
        return {
            "display": "true" if value else "false",
            "type": "boolean",
            "full": None,
        }

    # Handle string representations
    if isinstance(value, str):
        lower = value.lower()
        if lower in ("true", "yes", "1", "on"):
            return {"display": "true", "type": "boolean", "full": None}
        if lower in ("false", "no", "0", "off"):
            return {"display": "false", "type": "boolean", "full": None}

    # Handle numeric representations
    if isinstance(value, (int, float)):
        return {
            "display": "true" if value else "false",
            "type": "boolean",
            "full": None,
        }

    return {"display": str(value), "type": "string", "full": None}


def _format_badge(
    value: Any,
    arg: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as a styled badge/chip."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    str_value = str(value)
    css_class = f"badge-{str_value.lower().replace(' ', '-').replace('_', '-')}"

    return {
        "display": str_value,
        "type": "badge",
        "css_class": css_class,
        "full": None,
    }


def _format_truncate(
    value: Any,
    length_str: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format with explicit truncation length."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    # Parse length from arg
    try:
        truncate_length = int(length_str) if length_str else max_length
    except ValueError:
        truncate_length = max_length

    str_value = str(value)
    if len(str_value) > truncate_length:
        return {
            "display": str_value[:truncate_length] + "\u2026",
            "type": "string truncated",
            "full": str_value,
        }
    return {"display": str_value, "type": "string", "full": None}


def _format_json(
    value: Any,
    arg: str | None,
    config: WebUIConfig,
    max_length: int,
) -> dict[str, Any]:
    """Format as JSON (for complex objects)."""
    if value is None:
        return {"display": "\u2014", "type": "null", "full": None}

    if isinstance(value, (dict, list)):
        json_str = json.dumps(value, indent=2, default=str)
        if isinstance(value, dict):
            count = len(value)
            display = f"{{{count} field{'s' if count != 1 else ''}}}"
        else:
            count = len(value)
            display = f"[{count} item{'s' if count != 1 else ''}]"
        return {
            "display": display,
            "type": "json",
            "full": json_str,
        }

    # For non-dict/list, just format as string
    str_value = str(value)
    return {"display": str_value, "type": "string", "full": None}
