from __future__ import annotations

import typing as t
from datetime import datetime
from markupsafe import Markup

if t.TYPE_CHECKING:
    from .jinja2 import Jinja2Templates


def register_default_filters(adapter: Jinja2Templates) -> None:
    """Register default ACB template filters.

    Args:
        adapter: Templates adapter instance
    """
    adapter.add_filter("json", json_filter)
    adapter.add_filter("datetime", datetime_filter)
    adapter.add_filter("filesize", filesize_filter)


def json_filter(value: t.Any, indent: int | None = None) -> Markup:
    """JSON encoding filter.

    Example:
        {{ data|json }}
        {{ data|json(2) }}  # Pretty print with indent
    """
    import json

    # Encode to JSON and escape HTML-significant characters to prevent XSS
    raw = json.dumps(value, indent=indent, default=str)
    safe = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    # Mark as safe for templates after sanitization
    return Markup(safe)


def datetime_filter(value: t.Any, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Datetime formatting filter.

    Example:
        {{ timestamp|datetime }}
        {{ timestamp|datetime("%B %d, %Y") }}
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return str(value)  # Return as-is if not parseable
    if isinstance(value, datetime):
        return value.strftime(format)
    return str(value)


def filesize_filter(value: float, binary: bool = True) -> str:
    """File size formatting filter.

    Args:
        value: Size in bytes
        binary: Use binary (1024) vs decimal (1000) units

    Example:
        {{ file_size|filesize }}        # "1.5 KiB"
        {{ file_size|filesize(False) }} # "1.5 KB"
    """
    units = (
        ["B", "KiB", "MiB", "GiB", "TiB"] if binary else ["B", "KB", "MB", "GB", "TB"]
    )
    divisor = 1024 if binary else 1000

    size = float(value)
    for unit in units[:-1]:
        if abs(size) < divisor:
            return f"{size:.1f} {unit}"
        size /= divisor
    return f"{size:.1f} {units[-1]}"


__all__ = [
    "datetime_filter",
    "filesize_filter",
    "json_filter",
    "register_default_filters",
]
