"""Tests for input sanitization utilities."""

import pytest
from acb.services.validation._base import ValidationConfig
from acb.services.validation.sanitization import (
    InputSanitizer,
    HTMLSanitizer,
    SQLSanitizer,
    PathSanitizer,
    URLSanitizer,
    DataSanitizer,
)


class TestInputSanitizer:
    """Tests for InputSanitizer."""

    @pytest.fixture
    def sanitizer(self) -> InputSanitizer:
        """Create InputSanitizer instance."""
        config = ValidationConfig(
            enable_xss_protection=True,
            enable_sql_injection_protection=True,
            enable_path_traversal_protection=True
        )
        return InputSanitizer(config)

    async def test_auto_sanitization(self, sanitizer: InputSanitizer) -> None:
        """Test automatic sanitization."""
        dangerous_input = "<script>alert('xss')</script>SELECT * FROM users;"

        result = await sanitizer.sanitize(dangerous_input, "auto")

        assert result.is_valid is True
        # XSS tags should be removed
        assert "<script>" not in result.value
        # Single quotes should be escaped
        assert "''" in result.value or "alert" not in result.value
        # Warnings should be generated for detected threats
        assert len(result.warnings) > 0

    async def test_html_only_sanitization(self, sanitizer: InputSanitizer) -> None:
        """Test HTML-only sanitization."""
        html_input = "<script>alert('xss')</script><p>Hello</p>"

        result = await sanitizer.sanitize(html_input, "html")

        assert result.is_valid is True
        assert "<script>" not in result.value
        # HTML should be escaped
        assert "&lt;" in result.value or "Hello" in result.value

    async def test_sql_only_sanitization(self, sanitizer: InputSanitizer) -> None:
        """Test SQL-only sanitization."""
        sql_input = "'; DROP TABLE users; --"

        result = await sanitizer.sanitize(sql_input, "sql")

        assert result.is_valid is True
        assert len(result.warnings) > 0

    async def test_path_only_sanitization(self, sanitizer: InputSanitizer) -> None:
        """Test path-only sanitization."""
        path_input = "../../etc/passwd"

        result = await sanitizer.sanitize(path_input, "path")

        assert result.is_valid is True
        assert ".." not in result.value
        assert len(result.warnings) > 0

    async def test_url_only_sanitization(self, sanitizer: InputSanitizer) -> None:
        """Test URL-only sanitization."""
        url_input = "javascript:alert('xss')"

        result = await sanitizer.sanitize(url_input, "url")

        assert result.is_valid is False or len(result.warnings) > 0

    async def test_non_string_input(self, sanitizer: InputSanitizer) -> None:
        """Test sanitization with non-string input."""
        result = await sanitizer.sanitize(123, "auto")

        assert result.is_valid is True
        assert result.value == 123
        assert len(result.warnings) == 0


class TestHTMLSanitizer:
    """Tests for HTMLSanitizer."""

    @pytest.fixture
    def html_sanitizer(self) -> HTMLSanitizer:
        """Create HTMLSanitizer instance."""
        return HTMLSanitizer()

    async def test_remove_script_tags(self, html_sanitizer: HTMLSanitizer) -> None:
        """Test removal of script tags."""
        html_input = "<script>alert('xss')</script><p>Hello</p>"

        result = await html_sanitizer.sanitize(html_input)

        assert result.is_valid is True
        assert "<script>" not in result.value
        assert "alert" not in result.value
        assert len(result.warnings) > 0

    async def test_remove_javascript_urls(self, html_sanitizer: HTMLSanitizer) -> None:
        """Test removal of javascript: URLs."""
        html_input = '<a href="javascript:alert(\'xss\')">Click me</a>'

        result = await html_sanitizer.sanitize(html_input)

        assert result.is_valid is True
        assert "javascript:" not in result.value
        assert len(result.warnings) > 0

    async def test_remove_event_handlers(self, html_sanitizer: HTMLSanitizer) -> None:
        """Test removal of event handlers."""
        html_input = '<div onclick="alert(\'xss\')">Click me</div>'

        result = await html_sanitizer.sanitize(html_input)

        assert result.is_valid is True
        assert "onclick" not in result.value
        assert len(result.warnings) > 0

    async def test_html_entity_encoding(self, html_sanitizer: HTMLSanitizer) -> None:
        """Test HTML entity encoding."""
        html_input = "<p>This & that</p>"

        result = await html_sanitizer.sanitize(html_input)

        assert result.is_valid is True
        assert "&lt;" in result.value or "&amp;" in result.value

    async def test_remove_dangerous_attributes(self, html_sanitizer: HTMLSanitizer) -> None:
        """Test removal of dangerous attributes."""
        html_input = '<img src="image.jpg" onerror="alert(\'xss\')">'

        result = await html_sanitizer.sanitize(html_input)

        assert result.is_valid is True
        assert "onerror" not in result.value


class TestSQLSanitizer:
    """Tests for SQLSanitizer."""

    @pytest.fixture
    def sql_sanitizer(self) -> SQLSanitizer:
        """Create SQLSanitizer instance."""
        return SQLSanitizer()

    async def test_remove_sql_comments(self, sql_sanitizer: SQLSanitizer) -> None:
        """Test removal of SQL comments."""
        sql_input = "SELECT * FROM users; -- DROP TABLE users"

        result = await sql_sanitizer.sanitize(sql_input)

        assert result.is_valid is True
        assert "--" not in result.value
        assert len(result.warnings) > 0

    async def test_detect_sql_injection_patterns(self, sql_sanitizer: SQLSanitizer) -> None:
        """Test detection of SQL injection patterns."""
        sql_input = "'; DROP TABLE users; --"

        result = await sql_sanitizer.sanitize(sql_input)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("sql injection" in warning.lower() for warning in result.warnings)

    async def test_escape_single_quotes(self, sql_sanitizer: SQLSanitizer) -> None:
        """Test escaping of single quotes."""
        sql_input = "It's a test"

        result = await sql_sanitizer.sanitize(sql_input)

        assert result.is_valid is True
        assert "''" in result.value  # Single quote should be escaped

    async def test_detect_dangerous_keywords(self, sql_sanitizer: SQLSanitizer) -> None:
        """Test detection of dangerous SQL keywords."""
        sql_input = "union select password from users"

        result = await sql_sanitizer.sanitize(sql_input)

        assert result.is_valid is True
        # Should detect dangerous patterns
        assert len(result.warnings) > 0

    async def test_remove_block_comments(self, sql_sanitizer: SQLSanitizer) -> None:
        """Test removal of SQL block comments."""
        sql_input = "SELECT /* malicious comment */ * FROM users"

        result = await sql_sanitizer.sanitize(sql_input)

        assert result.is_valid is True
        assert "/*" not in result.value and "*/" not in result.value


class TestPathSanitizer:
    """Tests for PathSanitizer."""

    @pytest.fixture
    def path_sanitizer(self) -> PathSanitizer:
        """Create PathSanitizer instance."""
        return PathSanitizer()

    async def test_remove_directory_traversal(self, path_sanitizer: PathSanitizer) -> None:
        """Test removal of directory traversal patterns."""
        path_input = "../../etc/passwd"

        result = await path_sanitizer.sanitize(path_input)

        assert result.is_valid is True
        assert ".." not in result.value
        assert len(result.warnings) > 0

    async def test_remove_home_directory_reference(self, path_sanitizer: PathSanitizer) -> None:
        """Test removal of home directory references."""
        path_input = "~/sensitive_file"

        result = await path_sanitizer.sanitize(path_input)

        assert result.is_valid is True
        assert "~/" not in result.value
        assert len(result.warnings) > 0

    async def test_remove_system_directories(self, path_sanitizer: PathSanitizer) -> None:
        """Test removal of system directory references."""
        path_input = "/etc/passwd"

        result = await path_sanitizer.sanitize(path_input)

        assert result.is_valid is True
        assert "/etc/" not in result.value
        assert len(result.warnings) > 0

    async def test_remove_null_bytes(self, path_sanitizer: PathSanitizer) -> None:
        """Test removal of null bytes."""
        path_input = "file.txt\x00.exe"

        result = await path_sanitizer.sanitize(path_input)

        assert result.is_valid is True
        assert "\x00" not in result.value

    async def test_path_normalization(self, path_sanitizer: PathSanitizer) -> None:
        """Test path normalization."""
        path_input = "valid/file/path.txt"

        result = await path_sanitizer.sanitize(path_input)

        assert result.is_valid is True
        # Should be normalized but still valid
        assert "path.txt" in result.value


class TestURLSanitizer:
    """Tests for URLSanitizer."""

    @pytest.fixture
    def url_sanitizer(self) -> URLSanitizer:
        """Create URLSanitizer instance."""
        return URLSanitizer()

    async def test_dangerous_scheme_rejection(self, url_sanitizer: URLSanitizer) -> None:
        """Test rejection of dangerous URL schemes."""
        dangerous_url = "javascript:alert('xss')"

        result = await url_sanitizer.sanitize(dangerous_url)

        assert result.is_valid is False
        assert any("dangerous url scheme" in error.lower() for error in result.errors)

    async def test_allowed_scheme_acceptance(self, url_sanitizer: URLSanitizer) -> None:
        """Test acceptance of allowed URL schemes."""
        safe_url = "https://example.com"

        result = await url_sanitizer.sanitize(safe_url)

        assert result.is_valid is True

    async def test_unusual_scheme_warning(self, url_sanitizer: URLSanitizer) -> None:
        """Test warning for unusual but not dangerous schemes."""
        unusual_url = "custom://example.com"

        result = await url_sanitizer.sanitize(unusual_url)

        assert result.is_valid is True
        assert len(result.warnings) > 0

    async def test_url_encoding(self, url_sanitizer: URLSanitizer) -> None:
        """Test URL encoding for safety."""
        url_with_special_chars = "https://example.com/path with spaces"

        result = await url_sanitizer.sanitize(url_with_special_chars)

        assert result.is_valid is True
        if result.value != url_with_special_chars:
            assert len(result.warnings) > 0

    async def test_query_parameter_sanitization(self, url_sanitizer: URLSanitizer) -> None:
        """Test sanitization of query parameters."""
        url_with_xss = "https://example.com?param=<script>alert('xss')</script>"

        result = await url_sanitizer.sanitize(url_with_xss)

        assert result.is_valid is True
        assert "<script>" not in result.value


class TestDataSanitizer:
    """Tests for DataSanitizer."""

    @pytest.fixture
    def data_sanitizer(self) -> DataSanitizer:
        """Create DataSanitizer instance."""
        return DataSanitizer()

    async def test_string_length_sanitization(self, data_sanitizer: DataSanitizer) -> None:
        """Test string length sanitization."""
        long_string = "a" * 1000

        result = await data_sanitizer.sanitize_string_length(long_string, max_length=10)

        assert result.is_valid is True
        assert len(result.value) == 10
        assert len(result.warnings) > 0

    async def test_whitespace_sanitization(self, data_sanitizer: DataSanitizer) -> None:
        """Test whitespace sanitization."""
        messy_string = "  hello\t\tworld  \n  test  "

        result = await data_sanitizer.sanitize_whitespace(messy_string)

        assert result.is_valid is True
        assert result.value == "hello world test"
        assert len(result.warnings) > 0

    async def test_remove_control_characters(self, data_sanitizer: DataSanitizer) -> None:
        """Test removal of control characters."""
        string_with_control = "hello\x00\x01world\x7f"

        result = await data_sanitizer.sanitize_whitespace(string_with_control)

        assert result.is_valid is True
        assert "\x00" not in result.value
        assert "\x01" not in result.value
        assert "\x7f" not in result.value

    async def test_encoding_sanitization(self, data_sanitizer: DataSanitizer) -> None:
        """Test character encoding sanitization."""
        # This test might be system-dependent
        valid_string = "hello world"

        result = await data_sanitizer.sanitize_encoding(valid_string)

        assert result.is_valid is True
        assert result.value == valid_string
