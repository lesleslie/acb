"""Security-focused sanitization utilities for ACB applications.

These helpers provide safe string and path sanitization primitives that can be
used across projects, independent of any specific adapter implementation.

Modules and functions are intentionally framework-agnostic and keep minimal
dependencies.
"""

from __future__ import annotations

import re
import typing as t
from html import escape
from pathlib import Path

__all__ = [
    "sanitize_input",
    "sanitize_path",
    "mask_sensitive_data",
    "sanitize_output",
    "sanitize_dict_for_logging",
    "sanitize_html",
    "sanitize_sql",
]


# Common sensitive key/token patterns
SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "openai": re.compile(r"sk-[A-Za-z0-9]{48}"),  # OpenAI API key pattern
    "anthropic": re.compile(r"sk-ant-[A-Za-z0-9\-_]{95,}"),  # Anthropic API key pattern
    "github": re.compile(r"gh[ps]_[A-Za-z0-9]{36,255}"),  # GitHub token pattern
    "jwt": re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
    "generic_hex": re.compile(r"\b[0-9a-f]{32,}\b"),  # Generic hex token
}


def sanitize_html(value: str) -> str:
    """Sanitize HTML by escaping special characters.

    Args:
        value: HTML string to sanitize

    Returns:
        Escaped string safe for HTML rendering
    """
    return escape(value, quote=True)


def sanitize_sql(value: str) -> str:
    """Basic SQL quote escaping to reduce injection risk.

    Note: This is not a replacement for parameterized queries. Always use
    bound parameters with your database driver.
    """
    value = value.replace("'", "''")
    return value.replace('"', '""')


def sanitize_input(
    value: str,
    *,
    max_length: int | None = None,
    allowed_chars: str | None = None,
    strip_html: bool = False,
) -> str:
    """Sanitize input string with optional constraints.

    - Enforces type str (raises ValueError otherwise)
    - Optionally strips HTML tags (basic regex)
    - Optionally enforces max length
    - Optionally enforces allowed character whitelist
    """
    if not isinstance(value, str):
        msg = "Expected string"
        raise ValueError(msg)

    cleaned = value
    if strip_html:
        cleaned = re.sub(r"<[^>]+>", "", cleaned)

    if max_length is not None and len(cleaned) > max_length:
        msg = f"Input exceeds maximum length of {max_length}"
        raise ValueError(msg)

    if allowed_chars is not None and not re.match(rf"^[{allowed_chars}]*$", cleaned):
        msg = f"Input contains disallowed characters. Allowed: {allowed_chars}"
        raise ValueError(msg)

    return cleaned.strip()


def sanitize_path(
    path: str | Path,
    *,
    base_dir: str | Path | None = None,
    allow_absolute: bool = False,
) -> Path:
    """Sanitize file path to prevent directory traversal and unsafe access.

    - Blocks ".." traversal components
    - Optionally confines to a base directory
    - Optionally allows absolute paths, but blocks sensitive system dirs
    """
    p = Path(path)

    if ".." in p.parts:
        msg = f"Path traversal detected in '{path}'"
        raise ValueError(msg)

    if p.is_absolute() and not allow_absolute:
        msg = f"Absolute paths not allowed: '{path}'"
        raise ValueError(msg)

    if p.is_absolute() and allow_absolute:
        system_dirs = ("/etc", "/sys", "/proc", "/boot", "/root")
        p_str = str(p)
        if any(p_str.startswith(sd) for sd in system_dirs):
            msg = f"Access to system directory denied: '{path}'"
            raise ValueError(msg)

    if base_dir is not None:
        base = Path(base_dir).resolve()
        try:
            resolved = (base / p).resolve()
            resolved.relative_to(base)
        except ValueError as e:  # Outside base
            msg = f"Path '{path}' escapes base directory '{base_dir}'"
            raise ValueError(msg) from e

    return p


def mask_sensitive_data(
    text: str,
    *,
    visible_chars: int = 4,
    patterns: list[re.Pattern[str]] | None = None,
) -> str:
    """Mask tokens/api keys in text while preserving minimal readability."""
    masked = text
    pats = patterns or list(SENSITIVE_PATTERNS.values())
    for pat in pats:
        for m in pat.finditer(masked):
            original = m.group(0)
            replacement = (
                "***"
                if len(original) <= visible_chars
                else f"{original[:3]}...{original[-visible_chars:]}"
            )
            masked = masked.replace(original, replacement)
    return masked


def _sanitize_string(
    data: str,
    *,
    mask_keys: bool = True,
    mask_patterns: list[str] | None = None,
) -> str:
    s = data
    if mask_keys:
        for name, pat in SENSITIVE_PATTERNS.items():
            if pat.search(s):
                s = pat.sub(f"[REDACTED-{name.upper()}]", s)

    if mask_patterns:
        for cp in mask_patterns:
            s = re.sub(cp, "[REDACTED]", s)
    return s


def sanitize_output(
    data: t.Any,
    *,
    mask_keys: bool = True,
    mask_patterns: list[str] | None = None,
) -> t.Any:
    """Recursively sanitize data structures for safe logging/output."""
    if isinstance(data, dict):
        return {
            k: sanitize_output(v, mask_keys=mask_keys, mask_patterns=mask_patterns)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [
            sanitize_output(v, mask_keys=mask_keys, mask_patterns=mask_patterns)
            for v in data
        ]
    if isinstance(data, str):
        return _sanitize_string(data, mask_keys=mask_keys, mask_patterns=mask_patterns)
    return data


def sanitize_dict_for_logging(
    data: dict[str, t.Any],
    *,
    sensitive_keys: set[str] | None = None,
) -> dict[str, t.Any]:
    """Mask common sensitive keys within a dictionary for safe logs."""
    defaults = {
        "api_key",
        "apikey",
        "api-key",
        "token",
        "secret",
        "password",
        "passwd",
        "pwd",
        "bearer",
        "authorization",
        "auth",
        "credential",
        "private_key",
        "secret_key",
    }
    if sensitive_keys:
        defaults.update(sensitive_keys)

    out: dict[str, t.Any] = {}
    for k, v in data.items():
        if any(s in k.lower() for s in defaults):
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = sanitize_dict_for_logging(v, sensitive_keys=sensitive_keys)
        elif isinstance(v, list):
            out[k] = [
                sanitize_dict_for_logging(i, sensitive_keys=sensitive_keys)
                if isinstance(i, dict)
                else i
                for i in v
            ]
        else:
            out[k] = v
    return out
