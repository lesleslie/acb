"""Input sanitization utilities for security-focused validation (Refactored Example).

This module demonstrates how the sanitization could be refactored to leverage
the action functions while maintaining the service layer interface.

This is an example implementation showing how to reduce duplication by using
the action functions as building blocks.
"""

from __future__ import annotations

import re
import urllib.parse

import typing as t

# Import the action functions to leverage them
from acb.actions.sanitize import sanitize as action_sanitize
from acb.services.validation._base import ValidationConfig, ValidationResult


class InputSanitizer:
    """Main input sanitization service."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()
        self._html_sanitizer = HTMLSanitizer(config)
        self._sql_sanitizer = SQLSanitizer(config)
        self._path_sanitizer = PathSanitizer(config)
        self._url_sanitizer = URLSanitizer(config)

    async def sanitize(
        self,
        data: t.Any,
        sanitization_type: str = "auto",
    ) -> ValidationResult:
        """Sanitize data based on type and configuration.

        Args:
            data: Data to sanitize
            sanitization_type: Type of sanitization ('auto', 'html', 'sql', 'path', 'url')

        Returns:
            ValidationResult with sanitized data
        """
        result = ValidationResult(value=data, original_value=data)

        if not isinstance(data, str):
            # Only sanitize string data
            return result

        try:
            if sanitization_type == "auto":
                sanitized_value = await self._sanitize_auto(data, result)
            else:
                sanitized_value = await self._sanitize_specific_type(
                    data,
                    sanitization_type,
                    result,
                )

            result.value = sanitized_value

            # Add general sanitization warning if value changed
            if sanitized_value != data:
                result.add_warning("Input sanitized for security")

        except Exception as e:
            result.add_error(f"Sanitization failed: {e}")

        return result

    async def _sanitize_auto(
        self,
        data: str,
        result: ValidationResult,
    ) -> str:
        """Apply all enabled sanitizers automatically.

        Args:
            data: String data to sanitize
            result: Validation result to accumulate warnings

        Returns:
            Sanitized string
        """
        sanitized_value = data

        if self.config.enable_xss_protection:
            html_result = await self._html_sanitizer.sanitize(sanitized_value)
            sanitized_value = html_result.value
            result.warnings.extend(html_result.warnings)

        if self.config.enable_sql_injection_protection:
            sql_result = await self._sql_sanitizer.sanitize(sanitized_value)
            sanitized_value = sql_result.value
            result.warnings.extend(sql_result.warnings)

        if self.config.enable_path_traversal_protection:
            path_result = await self._path_sanitizer.sanitize(sanitized_value)
            sanitized_value = path_result.value
            result.warnings.extend(path_result.warnings)

        return sanitized_value

    async def _sanitize_specific_type(
        self,
        data: str,
        sanitization_type: str,
        result: ValidationResult,
    ) -> str:
        """Apply specific sanitizer based on type.

        Args:
            data: String data to sanitize
            sanitization_type: Type of sanitization to apply
            result: Validation result to accumulate warnings

        Returns:
            Sanitized string
        """
        # Map sanitization type to sanitizer
        sanitizers: dict[
            str,
            HTMLSanitizer | SQLSanitizer | PathSanitizer | URLSanitizer,
        ] = {
            "html": self._html_sanitizer,
            "sql": self._sql_sanitizer,
            "path": self._path_sanitizer,
            "url": self._url_sanitizer,
        }

        sanitizer = sanitizers.get(sanitization_type)
        if not sanitizer:
            return data

        sanitizer_result = await sanitizer.sanitize(data)
        result.warnings.extend(sanitizer_result.warnings)
        result.errors.extend(sanitizer_result.errors)
        if not sanitizer_result.is_valid:
            result.is_valid = False
        return sanitizer_result.value


class HTMLSanitizer:
    """HTML and XSS sanitization utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    async def sanitize(self, data: str) -> ValidationResult:
        """Sanitize HTML content to prevent XSS attacks."""
        result = ValidationResult(value=data, original_value=data)

        try:
            # Use the action function as the base
            sanitized = action_sanitize.html(data)
            result.value = sanitized

        except Exception as e:
            result.add_error(f"HTML sanitization failed: {e}")

        return result


class SQLSanitizer:
    """SQL injection prevention utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    async def sanitize(self, data: str) -> ValidationResult:
        """Sanitize input to prevent SQL injection."""
        result = ValidationResult(value=data, original_value=data)

        try:
            # Use the action function as the base
            sanitized = action_sanitize.sql(data)
            result.value = sanitized

        except Exception as e:
            result.add_error(f"SQL sanitization failed: {e}")

        return result


class PathSanitizer:
    """Path traversal prevention utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    async def sanitize(self, data: str) -> ValidationResult:
        """Sanitize file paths to prevent directory traversal."""
        result = ValidationResult(value=data, original_value=data)

        try:
            # Use the action function as the base
            # Note: We need to convert string to Path since action takes Path | str
            sanitized_path = action_sanitize.path(data)
            result.value = str(sanitized_path)

        except Exception as e:
            result.add_error(f"Path sanitization failed: {e}")

        return result


class URLSanitizer:
    """URL sanitization utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

        self.allowed_schemes = {"http", "https", "ftp", "ftps", "mailto"}
        self.dangerous_schemes = {"javascript", "vbscript", "data", "file"}

    async def sanitize(self, data: str) -> ValidationResult:
        """Sanitize URLs to prevent malicious redirects and XSS."""
        result = ValidationResult(value=data, original_value=data)

        try:
            # Parse URL
            parsed = urllib.parse.urlparse(data)

            # Check scheme
            if parsed.scheme.lower() in self.dangerous_schemes:
                result.add_error(f"Dangerous URL scheme: {parsed.scheme}")
                return result

            if parsed.scheme and parsed.scheme.lower() not in self.allowed_schemes:
                result.add_warning(f"Unusual URL scheme: {parsed.scheme}")

            # URL encode the URL to prevent injection
            sanitized = urllib.parse.quote(data, safe=":/?#[]@!$&'()*+,;=")

            # Remove potential XSS in URL parameters using the action's approach
            if "?" in sanitized:
                url_parts = sanitized.split("?", 1)
                base_url = url_parts[0]
                query_string = url_parts[1]

                # Use action's HTML sanitization on query parameters
                query_string = action_sanitize.html(query_string)

                sanitized = f"{base_url}?{query_string}"

            result.value = sanitized

            if sanitized != data:
                result.add_warning("URL sanitized for security")

        except Exception as e:
            result.add_error(f"URL sanitization failed: {e}")

        return result


class DataSanitizer:
    """General data sanitization utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    async def sanitize_string_length(
        self,
        data: str,
        max_length: int | None = None,
    ) -> ValidationResult:
        """Sanitize string length to prevent DoS attacks."""
        result = ValidationResult(value=data, original_value=data)

        max_len = max_length or self.config.max_string_length

        if len(data) > max_len:
            result.value = data[:max_len]
            result.add_warning(f"String truncated to {max_len} characters")

        return result

    async def sanitize_whitespace(self, data: str) -> ValidationResult:
        """Sanitize whitespace characters."""
        result = ValidationResult(value=data, original_value=data)

        # Use action's approach to sanitize whitespace
        # The action doesn't have this function, so we'll implement it here
        sanitized = re.sub(
            r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]",
            "",
            data,
        )  # REGEX OK: Control character sanitization

        # Normalize whitespace
        sanitized = re.sub(
            r"\s+",
            " ",
            sanitized,
        ).strip()  # REGEX OK: Whitespace normalization

        result.value = sanitized

        if sanitized != data:
            result.add_warning("Whitespace normalized")

        return result

    async def sanitize_encoding(self, data: str) -> ValidationResult:
        """Sanitize character encoding issues."""
        result = ValidationResult(value=data, original_value=data)

        try:
            # Ensure proper UTF-8 encoding
            sanitized = data.encode("utf-8", errors="replace").decode("utf-8")

            result.value = sanitized

            if sanitized != data:
                result.add_warning("Character encoding sanitized")

        except Exception as e:
            result.add_error(f"Encoding sanitization failed: {e}")

        return result
