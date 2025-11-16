"""Tests for template filters."""

from __future__ import annotations

import pytest
from datetime import datetime


class TestDefaultFilters:
    """Test default ACB template filters."""

    @pytest.mark.asyncio
    async def test_json_filter_basic(self, templates):
        """Test json filter with simple data."""
        data = {"name": "Alice", "age": 30}
        result = await templates.render_string("{{ data|json }}", data=data)
        assert '"name": "Alice"' in result
        assert '"age": 30' in result

    @pytest.mark.asyncio
    async def test_json_filter_with_indent(self, templates):
        """Test json filter with indentation."""
        data = {"key": "value"}
        result = await templates.render_string("{{ data|json(2) }}", data=data)
        assert '{\n  "key": "value"\n}' in result

    @pytest.mark.asyncio
    async def test_json_filter_list(self, templates):
        """Test json filter with list data."""
        data = [1, 2, 3, 4]
        result = await templates.render_string("{{ data|json }}", data=data)
        assert "[1, 2, 3, 4]" in result

    @pytest.mark.asyncio
    async def test_json_filter_nested(self, templates):
        """Test json filter with nested data."""
        data = {
            "user": {"name": "Alice", "email": "alice@example.com"},
            "items": [1, 2, 3],
        }
        result = await templates.render_string("{{ data|json }}", data=data)
        assert "alice@example.com" in result
        assert "[1, 2, 3]" in result

    @pytest.mark.asyncio
    async def test_datetime_filter_default_format(self, templates):
        """Test datetime filter with default format."""
        dt = datetime(2025, 1, 25, 14, 30, 45)
        result = await templates.render_string("{{ dt|datetime }}", dt=dt)
        assert result.strip() == "2025-01-25 14:30:45"

    @pytest.mark.asyncio
    async def test_datetime_filter_custom_format(self, templates):
        """Test datetime filter with custom format."""
        dt = datetime(2025, 1, 25, 14, 30, 45)
        result = await templates.render_string('{{ dt|datetime("%B %d, %Y") }}', dt=dt)
        assert result.strip() == "January 25, 2025"

    @pytest.mark.asyncio
    async def test_datetime_filter_iso_string(self, templates):
        """Test datetime filter with ISO string input."""
        iso_string = "2025-01-25T14:30:45"
        result = await templates.render_string("{{ dt|datetime }}", dt=iso_string)
        assert "2025-01-25 14:30:45" in result

    @pytest.mark.asyncio
    async def test_datetime_filter_time_only(self, templates):
        """Test datetime filter with time-only format."""
        dt = datetime(2025, 1, 25, 14, 30, 45)
        result = await templates.render_string('{{ dt|datetime("%H:%M:%S") }}', dt=dt)
        assert result.strip() == "14:30:45"

    @pytest.mark.asyncio
    async def test_filesize_filter_bytes(self, templates):
        """Test filesize filter with bytes."""
        result = await templates.render_string("{{ size|filesize }}", size=512)
        assert result.strip() == "512.0 B"

    @pytest.mark.asyncio
    async def test_filesize_filter_kib(self, templates):
        """Test filesize filter with KiB."""
        result = await templates.render_string("{{ size|filesize }}", size=1536)
        assert result.strip() == "1.5 KiB"

    @pytest.mark.asyncio
    async def test_filesize_filter_mib(self, templates):
        """Test filesize filter with MiB."""
        size = 2.5 * 1024 * 1024  # 2.5 MiB
        result = await templates.render_string("{{ size|filesize }}", size=size)
        assert result.strip() == "2.5 MiB"

    @pytest.mark.asyncio
    async def test_filesize_filter_gib(self, templates):
        """Test filesize filter with GiB."""
        size = 3.7 * 1024 * 1024 * 1024  # 3.7 GiB
        result = await templates.render_string("{{ size|filesize }}", size=size)
        assert result.strip() == "3.7 GiB"

    @pytest.mark.asyncio
    async def test_filesize_filter_decimal_units(self, templates):
        """Test filesize filter with decimal (KB) units."""
        result = await templates.render_string("{{ size|filesize(False) }}", size=1500)
        assert result.strip() == "1.5 KB"

    @pytest.mark.asyncio
    async def test_filesize_filter_float_input(self, templates):
        """Test filesize filter with float input."""
        result = await templates.render_string("{{ size|filesize }}", size=1536.5)
        assert "1.5 KiB" in result


class TestCustomFilters:
    """Test custom filter registration."""

    @pytest.mark.asyncio
    async def test_add_filter_simple(self, templates):
        """Test adding a simple custom filter."""
        templates.add_filter("uppercase", lambda x: x.upper())

        result = await templates.render_string("{{ name|uppercase }}", name="alice")
        assert result.strip() == "ALICE"

    @pytest.mark.asyncio
    async def test_add_filter_with_params(self, templates):
        """Test adding filter with parameters."""

        def repeat(value: str, times: int = 2) -> str:
            return value * times

        templates.add_filter("repeat", repeat)

        result = await templates.render_string("{{ text|repeat(3) }}", text="Hi")
        assert result.strip() == "HiHiHi"

    @pytest.mark.asyncio
    async def test_add_filter_chainable(self, templates):
        """Test chaining multiple filters."""
        templates.add_filter("double", lambda x: x * 2)
        templates.add_filter("increment", lambda x: x + 1)

        result = await templates.render_string("{{ num|double|increment }}", num=5)
        assert result.strip() == "11"  # (5 * 2) + 1

    @pytest.mark.asyncio
    async def test_override_default_filter(self, templates):
        """Test overriding a default filter."""

        def custom_json(value, **kwargs):
            return "CUSTOM_JSON"

        templates.add_filter("json", custom_json)

        result = await templates.render_string("{{ data|json }}", data={"key": "val"})
        assert result.strip() == "CUSTOM_JSON"

    @pytest.mark.asyncio
    async def test_filter_with_none_value(self, templates):
        """Test filter handling None values."""

        def safe_upper(value):
            return value.upper() if value else ""

        templates.add_filter("safe_upper", safe_upper)

        result = await templates.render_string("{{ name|safe_upper }}", name=None)
        assert result.strip() == ""


class TestGlobalVariables:
    """Test global variable registration."""

    @pytest.mark.asyncio
    async def test_add_global_string(self, templates):
        """Test adding global string variable."""
        templates.add_global("site_name", "Test Site")

        result = await templates.render_string("{{ site_name }}")
        assert result.strip() == "Test Site"

    @pytest.mark.asyncio
    async def test_add_global_number(self, templates):
        """Test adding global number variable."""
        templates.add_global("max_items", 100)

        result = await templates.render_string("{{ max_items }}")
        assert result.strip() == "100"

    @pytest.mark.asyncio
    async def test_add_global_dict(self, templates):
        """Test adding global dictionary variable."""
        config = {"debug": True, "version": "1.0"}
        templates.add_global("config", config)

        result = await templates.render_string("{{ config.version }}")
        assert result.strip() == "1.0"

    @pytest.mark.asyncio
    async def test_add_global_function(self, templates):
        """Test adding global function."""

        def get_year():
            return 2025

        templates.add_global("current_year", get_year)

        result = await templates.render_string("{{ current_year() }}")
        assert result.strip() == "2025"

    @pytest.mark.asyncio
    async def test_global_override_context(self, templates):
        """Test that context can override globals."""
        templates.add_global("name", "Global")

        result = await templates.render_string("{{ name }}", name="Context")
        assert result.strip() == "Context"


class TestFilterEdgeCases:
    """Test edge cases and error handling in filters."""

    @pytest.mark.asyncio
    async def test_json_filter_with_datetime(self, templates):
        """Test json filter with datetime objects (using default=str)."""
        dt = datetime(2025, 1, 25)
        result = await templates.render_string("{{ data|json }}", data={"date": dt})
        assert "2025-01-25" in result

    @pytest.mark.asyncio
    async def test_datetime_filter_invalid_string(self, templates):
        """Test datetime filter with invalid string."""
        result = await templates.render_string("{{ dt|datetime }}", dt="not a datetime")
        assert result.strip() == "not a datetime"

    @pytest.mark.asyncio
    async def test_filesize_filter_zero(self, templates):
        """Test filesize filter with zero bytes."""
        result = await templates.render_string("{{ size|filesize }}", size=0)
        assert result.strip() == "0.0 B"

    @pytest.mark.asyncio
    async def test_filesize_filter_negative(self, templates):
        """Test filesize filter with negative value."""
        result = await templates.render_string("{{ size|filesize }}", size=-1024)
        assert "KiB" in result  # Should handle negative values

    @pytest.mark.asyncio
    async def test_multiple_filters_combined(self, templates):
        """Test combining default filters."""
        data = {"items": [1, 2, 3]}
        template = "{{ data|json }}"
        result = await templates.render_string(template, data=data)
        assert '"items": [1, 2, 3]' in result
