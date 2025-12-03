"""Security patterns shared between validation actions and services.

This module centralizes security detection patterns to avoid duplication
between the actions layer and services layer.
"""

import re

# Common dangerous patterns for security validation
SQL_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        re.IGNORECASE,
    ),
    re.compile(r"(--|\/\*|\*\/)", re.IGNORECASE),
    # Classic tautology patterns like: ' OR '1'='1' or 1=1
    re.compile(r"\b(?:or|and)\b\s*1\s*=\s*1", re.IGNORECASE),
    re.compile(r"\b(?:or|and)\b\s*'1'\s*=\s*'1'", re.IGNORECASE),
    re.compile(r'\b(?:or|and)\b\s*"1"\s*=\s*"1"', re.IGNORECASE),
    # More generic 'OR x = x' style
    re.compile(r"\b(or|and)\b\s+[^=]+\s*=\s*[^=]+", re.IGNORECASE),
    re.compile(r"(;.*--)", re.IGNORECASE),
    re.compile(r"(\bxp_|\bsp_)", re.IGNORECASE),
]

SCRIPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"vbscript:", re.IGNORECASE),
    re.compile(
        r"on\w+\s*=\s*['\"][^'\"]*['\"]",
        re.IGNORECASE,
    ),  # REGEX OK: XSS detection
    re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<object[^>]*>.*?</object>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<embed[^>]*>.*?</embed>", re.IGNORECASE | re.DOTALL),
]

PATH_TRAVERSAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.\./", re.IGNORECASE),  # Parent directory traversal
    re.compile(r"\.\.\\", re.IGNORECASE),  # Windows Parent directory traversal
    re.compile(r"%2e%2e%2f", re.IGNORECASE),  # URL encoded traversal
    re.compile(r"%2e%2e%5c", re.IGNORECASE),  # URL encoded Windows traversal
    re.compile(r"~", re.IGNORECASE),  # Home directory
]


def detect_sql_injection(value: str) -> bool:
    """Check if string contains potential SQL injection patterns.

    Args:
        value: String to check for SQL injection

    Returns:
        True if string appears safe, False if potential injection detected
    """
    value_lower = value.lower()

    return all(not pattern.search(value_lower) for pattern in SQL_INJECTION_PATTERNS)


def detect_xss(value: str) -> bool:
    """Check if string contains potential XSS/script injection patterns.

    Args:
        value: String to check for XSS

    Returns:
        True if string appears safe, False if potential XSS detected
    """
    value_lower = value.lower()

    return all(not pattern.search(value_lower) for pattern in SCRIPT_INJECTION_PATTERNS)


def detect_path_traversal(value: str) -> bool:
    """Check if string contains potential path traversal patterns.

    Args:
        value: String to check for path traversal

    Returns:
        True if string appears safe, False if potential traversal detected
    """
    value_lower = value.lower()

    return all(not pattern.search(value_lower) for pattern in PATH_TRAVERSAL_PATTERNS)
