"""Input validation utilities for ACB framework.

This action provides pure utility functions for validating common input types
including emails, URLs, SQL injection detection, XSS detection, and path traversal detection.
"""

import re
from urllib.parse import urlparse

import typing as t

__all__: list[str] = ["validate"]


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(
        self, message: str, field: str | None = None, value: t.Any = None
    ) -> None:
        super().__init__(message)
        self.field = field
        self.value = value


class Validate:
    """Pure utility functions for input validation."""

    # Common dangerous patterns for security validation
    SQL_INJECTION_PATTERNS = [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        r"(--|\/\*|\*\/)",
        r"(\bor\b.*=.*\bor\b)",
        r"(\band\b.*=.*\band\b)",
        r"(;.*--)",
        r"(\bxp_|\bsp_)",
    ]

    SCRIPT_INJECTION_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e%5c",
        r"~",
    ]

    @staticmethod
    def email(email: str) -> bool:
        """Validate an email address.

        Args:
            email: Email address to validate

        Returns:
            True if email is valid, False otherwise
        """
        pattern = re.compile(  # REGEX OK: email validation
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        )
        return bool(pattern.match(email))

    @staticmethod
    def url(url: str) -> bool:
        """Validate a URL.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def phone(phone: str) -> bool:
        """Validate a phone number.

        Args:
            phone: Phone number to validate

        Returns:
            True if phone number is valid, False otherwise
        """
        # Remove common separators
        cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone)  # REGEX OK: phone number cleaning
        # Check for international or local format
        pattern = re.compile(r"^(\+\d{1,3})?(\d{10,15})$")  # REGEX OK: phone validation
        return bool(pattern.match(cleaned))

    @staticmethod
    def sql_injection(value: str) -> bool:
        """Check if string contains potential SQL injection patterns.

        Args:
            value: String to check for SQL injection

        Returns:
            True if string appears safe, False if potential injection detected
        """
        value_lower = value.lower()

        for pattern in Validate.SQL_INJECTION_PATTERNS:
            if re.search(
                pattern,
                value_lower,
                re.IGNORECASE,
            ):  # REGEX OK: SQL injection detection
                return False

        return True

    @staticmethod
    def xss(value: str) -> bool:
        """Check if string contains potential XSS/script injection patterns.

        Args:
            value: String to check for XSS

        Returns:
            True if string appears safe, False if potential XSS detected
        """
        value_lower = value.lower()

        for pattern in Validate.SCRIPT_INJECTION_PATTERNS:
            if re.search(
                pattern,
                value_lower,
                re.IGNORECASE,
            ):  # REGEX OK: XSS detection
                return False

        return True

    @staticmethod
    def path_traversal(value: str) -> bool:
        """Check if string contains potential path traversal patterns.

        Args:
            value: String to check for path traversal

        Returns:
            True if string appears safe, False if potential traversal detected
        """
        value_lower = value.lower()

        for pattern in Validate.PATH_TRAVERSAL_PATTERNS:
            if re.search(
                pattern,
                value_lower,
                re.IGNORECASE,
            ):  # REGEX OK: path traversal detection
                return False

        return True

    @staticmethod
    def length(
        value: str,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> bool:
        """Validate string length.

        Args:
            value: String to validate
            min_length: Minimum allowed length (optional)
            max_length: Maximum allowed length (optional)

        Returns:
            True if length is valid, False otherwise
        """
        if min_length is not None and len(value) < min_length:
            return False

        return not (max_length is not None and len(value) > max_length)

    @staticmethod
    def pattern(value: str, pattern: str) -> bool:
        """Validate string against regex pattern.

        Args:
            value: String to validate
            pattern: Regex pattern to match against

        Returns:
            True if pattern matches, False otherwise
        """
        try:
            return bool(re.match(pattern, value))  # REGEX OK: pattern matching utility
        except re.error:
            return False

    # Note: Sanitization functions have moved to acb.security.sanitization


# Export an instance
validate = Validate()
