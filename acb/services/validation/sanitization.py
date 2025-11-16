"""Input sanitization utilities for security-focused validation.

This module provides comprehensive input sanitization to prevent
XSS attacks, SQL injection, path traversal, and other security vulnerabilities.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path

import typing as t

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

        # Dangerous HTML tags that should be removed
        self.dangerous_tags = {
            "script",
            "iframe",
            "object",
            "embed",
            "form",
            "input",
            "button",
            "textarea",
            "select",
            "option",
            "meta",
            "link",
            "style",
            "base",
            "frame",
            "frameset",
            "applet",
        }

        # Allowed tags for basic formatting (if allowing some HTML)
        self.allowed_tags = {
            "p",
            "br",
            "strong",
            "em",
            "b",
            "i",
            "u",
            "span",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "ol",
            "li",
            "blockquote",
        }

        # Dangerous attributes
        self.dangerous_attributes = {
            "onload",
            "onclick",
            "onmouseover",
            "onmouseout",
            "onfocus",
            "onblur",
            "onchange",
            "onsubmit",
            "onerror",
            "onkeydown",
            "onkeyup",
            "onkeypress",
            "javascript:",
            "vbscript:",
            "data:",
        }

    async def sanitize(self, data: str) -> ValidationResult:
        """Sanitize HTML content to prevent XSS attacks."""
        result = ValidationResult(value=data, original_value=data)

        try:
            sanitized = data

            # Remove dangerous script patterns
            sanitized = await self._remove_script_patterns(sanitized, result)

            # Remove/escape HTML tags
            sanitized = await self._sanitize_html_tags(sanitized, result)

            # Remove dangerous attributes
            sanitized = await self._remove_dangerous_attributes(sanitized, result)

            # HTML entity encoding for remaining content
            sanitized = html.escape(sanitized)

            result.value = sanitized

        except Exception as e:
            result.add_error(f"HTML sanitization failed: {e}")

        return result

    async def _remove_script_patterns(self, data: str, result: ValidationResult) -> str:
        """Remove dangerous script patterns."""
        original = data

        # Remove script tags and content
        data = re.sub(  # REGEX OK: XSS prevention
            r"<script[^>]*>.*?</script>",
            "",
            data,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Remove javascript: and vbscript: URLs
        data = re.sub(
            r'javascript:[^"\']*',
            "",
            data,
            flags=re.IGNORECASE,
        )  # REGEX OK: XSS prevention
        data = re.sub(
            r'vbscript:[^"\']*',
            "",
            data,
            flags=re.IGNORECASE,
        )  # REGEX OK: XSS prevention

        # Remove data: URLs (can contain scripts)
        data = re.sub(
            r'data:[^"\']*',
            "",
            data,
            flags=re.IGNORECASE,
        )  # REGEX OK: XSS prevention

        # Remove event handlers
        data = re.sub(
            r'on\w+\s*=\s*["\'][^"\']*["\']',
            "",
            data,
            flags=re.IGNORECASE,
        )  # REGEX OK: XSS prevention

        if data != original:
            result.add_warning("Dangerous script patterns removed")

        return data

    async def _sanitize_html_tags(self, data: str, result: ValidationResult) -> str:
        """Sanitize HTML tags."""
        original = data

        # For strict sanitization, remove all HTML tags
        if not hasattr(self.config, "allow_html") or not self.config.allow_html:
            data = re.sub(r"<[^>]+>", "", data)  # REGEX OK: HTML tag removal
            if data != original:
                result.add_warning("HTML tags removed")
            return data

        # For permissive sanitization, remove only dangerous tags
        for tag in self.dangerous_tags:
            pattern = rf"<{tag}[^>]*>.*?</{tag}>"
            data = re.sub(
                pattern,
                "",
                data,
                flags=re.IGNORECASE | re.DOTALL,
            )  # REGEX OK: HTML sanitization
            pattern = rf"<{tag}[^>]*/?>"
            data = re.sub(
                pattern,
                "",
                data,
                flags=re.IGNORECASE,
            )  # REGEX OK: HTML sanitization

        if data != original:
            result.add_warning("Dangerous HTML tags removed")

        return data

    async def _remove_dangerous_attributes(
        self,
        data: str,
        result: ValidationResult,
    ) -> str:
        """Remove dangerous HTML attributes."""
        original = data

        for attr in self.dangerous_attributes:
            # Remove attributes with values
            pattern = rf'{attr}\s*=\s*["\'][^"\']*["\']'
            data = re.sub(
                pattern,
                "",
                data,
                flags=re.IGNORECASE,
            )  # REGEX OK: XSS prevention

        if data != original:
            result.add_warning("Dangerous attributes removed")

        return data


class SQLSanitizer:
    """SQL injection prevention utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

        # Dangerous SQL keywords and patterns
        self.sql_keywords = {
            "union",
            "select",
            "insert",
            "update",
            "delete",
            "drop",
            "create",
            "alter",
            "exec",
            "execute",
            "sp_",
            "xp_",
            "declare",
            "cast",
            "convert",
            "char",
            "nchar",
            "varchar",
            "nvarchar",
            "ascii",
            "substring",
            "right",
            "left",
            "openrowset",
            "openquery",
            "opendatasource",
            "bulk",
            "grant",
            "revoke",
            "shutdown",
        }

        self.sql_comment_patterns = [
            r"--",  # SQL line comment  # REGEX OK: SQL injection prevention
            r"/\*.*?\*/",  # SQL block comment  # REGEX OK: SQL injection prevention
            r"#",  # MySQL comment  # REGEX OK: SQL injection prevention
        ]

        self.sql_injection_patterns = [
            r"\b(union|select|insert|update|delete|drop|create|alter)\s+",  # REGEX OK: SQL injection prevention
            r'[\'";]',  # Quote characters  # REGEX OK: SQL injection prevention
            r'\s+(or|and)\s+[\d\w\'"]',  # OR/AND conditions  # REGEX OK: SQL injection prevention
            r'=\s*[\'"]?[\'"]?',  # Empty equals  # REGEX OK: SQL injection prevention
            r"\b1\s*=\s*1\b",  # Always true condition  # REGEX OK: SQL injection prevention
            r"\b0\s*=\s*0\b",  # Always true condition  # REGEX OK: SQL injection prevention
            r'[\'"]\s*;\s*',  # Statement termination  # REGEX OK: SQL injection prevention
        ]

    async def sanitize(self, data: str) -> ValidationResult:
        """Sanitize input to prevent SQL injection."""
        result = ValidationResult(value=data, original_value=data)

        try:
            sanitized = data

            # Remove SQL comments
            sanitized = await self._remove_sql_comments(sanitized, result)

            # Detect and handle SQL injection patterns
            sanitized = await self._handle_sql_patterns(sanitized, result)

            # Escape single quotes (basic protection)
            sanitized = sanitized.replace("'", "''")

            result.value = sanitized

        except Exception as e:
            result.add_error(f"SQL sanitization failed: {e}")

        return result

    async def _remove_sql_comments(self, data: str, result: ValidationResult) -> str:
        """Remove SQL comment patterns."""
        original = data

        for pattern in self.sql_comment_patterns:
            if pattern == r"/\*.*?\*/":
                # Block comments
                data = re.sub(
                    pattern,
                    "",
                    data,
                    flags=re.DOTALL,
                )  # REGEX OK: SQL injection prevention
            else:
                # Line comments
                data = re.sub(
                    pattern + r".*$",
                    "",
                    data,
                    flags=re.MULTILINE,
                )  # REGEX OK: SQL injection prevention

        if data != original:
            result.add_warning("SQL comment patterns removed")

        return data

    async def _handle_sql_patterns(self, data: str, result: ValidationResult) -> str:
        """Handle dangerous SQL injection patterns."""
        # Check for dangerous patterns
        dangerous_found = False
        for pattern in self.sql_injection_patterns:
            if re.search(
                pattern,
                data,
                re.IGNORECASE,
            ):  # REGEX OK: SQL injection prevention
                dangerous_found = True
                break

        # Check for dangerous keywords
        words = data.lower().split()
        for word in words:
            if word in self.sql_keywords:
                dangerous_found = True
                break

        if dangerous_found:
            result.add_warning("Potential SQL injection patterns detected")
            # For safety, we could reject the input entirely or sanitize more aggressively
            # Here we'll just flag it but continue processing

        return data


class PathSanitizer:
    """Path traversal prevention utilities."""

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

        self.dangerous_path_patterns = [
            r"\.\./",  # Parent directory traversal  # REGEX OK: Path traversal prevention
            r"\.\.\.",  # Directory traversal  # REGEX OK: Path traversal prevention
            r"~/",  # Home directory  # REGEX OK: Path traversal prevention
            r"/etc/",  # System directories  # REGEX OK: Path traversal prevention
            r"/proc/",  # Process directories  # REGEX OK: Path traversal prevention
            r"/sys/",  # System directories  # REGEX OK: Path traversal prevention
            r"\\",  # Windows path separators  # REGEX OK: Path traversal prevention
            r"\x00",  # Null bytes  # REGEX OK: Path traversal prevention
        ]

    async def sanitize(self, data: str) -> ValidationResult:
        """Sanitize file paths to prevent directory traversal."""
        result = ValidationResult(value=data, original_value=data)

        try:
            sanitized = data

            # Remove dangerous path patterns
            for pattern in self.dangerous_path_patterns:
                if re.search(
                    pattern,
                    sanitized,
                    re.IGNORECASE,
                ):  # REGEX OK: Path traversal prevention
                    result.add_warning(f"Dangerous path pattern detected: {pattern}")
                    sanitized = re.sub(
                        pattern,
                        "",
                        sanitized,
                        flags=re.IGNORECASE,
                    )  # REGEX OK: Path traversal prevention

            # Normalize path using pathlib (safer than os.path)
            try:
                path = Path(sanitized)
                # Convert to string and ensure it doesn't go outside allowed areas
                normalized = str(path.resolve())

                # Basic check: ensure path doesn't contain parent traversal
                if ".." in normalized or normalized.startswith("/"):
                    result.add_warning("Path normalized for security")
                    # Keep just the filename
                    sanitized = path.name
                else:
                    sanitized = normalized

            except Exception:
                # If path normalization fails, just use filename
                try:
                    sanitized = Path(sanitized).name
                    result.add_warning("Path reduced to filename for security")
                except Exception:
                    result.add_error("Invalid path format")

            result.value = sanitized

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

            # Remove potential XSS in URL parameters
            if "?" in sanitized:
                url_parts = sanitized.split("?", 1)
                base_url = url_parts[0]
                query_string = url_parts[1]

                # Basic sanitization of query parameters
                query_string = re.sub(
                    r"<[^>]*>",
                    "",
                    query_string,
                )  # Remove HTML tags  # REGEX OK: XSS prevention
                query_string = html.escape(query_string)  # Escape HTML entities

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

        # Remove null bytes and other control characters
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
