"""Tests for async rendering functionality."""

from __future__ import annotations

import asyncio
import pytest


class TestAsyncRendering:
    """Test async-specific rendering features."""

    @pytest.mark.asyncio
    async def test_concurrent_renders(self, templates, sample_template):
        """Test rendering multiple templates concurrently."""
        names = ["Alice", "Bob", "Charlie", "David"]

        tasks = [templates.render("sample.html", name=name) for name in names]

        results = await asyncio.gather(*tasks)

        assert len(results) == 4
        assert results[0] == "Hello Alice!"
        assert results[1] == "Hello Bob!"
        assert results[2] == "Hello Charlie!"
        assert results[3] == "Hello David!"

    @pytest.mark.asyncio
    async def test_concurrent_string_renders(self, templates):
        """Test rendering multiple template strings concurrently."""
        data = [
            ("{{ x }} + {{ y }} = {{ x + y }}", {"x": 1, "y": 2}),
            ("{{ name|upper }}", {"name": "test"}),
            ("{{ items|length }}", {"items": [1, 2, 3, 4, 5]}),
        ]

        tasks = [
            templates.render_string(template, **context) for template, context in data
        ]

        results = await asyncio.gather(*tasks)

        assert results[0].strip() == "1 + 2 = 3"
        assert results[1].strip() == "TEST"
        assert results[2].strip() == "5"

    @pytest.mark.asyncio
    async def test_async_filter_execution(self, templates):
        """Test that filters work correctly in async context."""
        from datetime import datetime

        dt = datetime(2025, 1, 25, 14, 30, 0)
        result = await templates.render_string("{{ dt|datetime }}", dt=dt)

        assert "2025-01-25" in result

    @pytest.mark.asyncio
    async def test_large_concurrent_load(self, templates, template_dir):
        """Test handling many concurrent renders."""
        # Create a simple template
        template_file = template_dir / "concurrent.html"
        template_file.write_text("Result: {{ value }}")

        # Render 100 templates concurrently
        tasks = [templates.render("concurrent.html", value=i) for i in range(100)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        assert results[0] == "Result: 0"
        assert results[50] == "Result: 50"
        assert results[99] == "Result: 99"

    @pytest.mark.asyncio
    async def test_nested_async_calls(self, templates):
        """Test nested async template rendering."""

        async def render_inner():
            return await templates.render_string("Inner: {{ value }}", value=42)

        async def render_outer():
            inner_result = await render_inner()
            return await templates.render_string(
                "Outer: {{ inner }}", inner=inner_result
            )

        result = await render_outer()
        assert "Outer: Inner: 42" in result


class TestAsyncPerformance:
    """Test async performance characteristics."""

    @pytest.mark.asyncio
    async def test_template_caching(self, templates, template_dir):
        """Test that templates are cached after first load."""
        template_file = template_dir / "cached.html"
        template_file.write_text("Cached: {{ value }}")

        # First render - should load and cache
        result1 = await templates.render("cached.html", value=1)
        assert result1 == "Cached: 1"

        # Modify template file
        template_file.write_text("Modified: {{ value }}")

        # Second render with auto_reload=True should show modified version
        result2 = await templates.render("cached.html", value=2)

        if templates.settings.auto_reload:
            assert result2 == "Modified: 2"
        else:
            assert result2 == "Cached: 2"

    @pytest.mark.asyncio
    async def test_cache_disabled_reload(self, template_dir):
        """Test template reloading with auto_reload disabled."""
        from acb.adapters.templates import TemplatesAdapter

        templates_no_reload = TemplatesAdapter(
            template_dir=template_dir, auto_reload=False
        )

        template_file = template_dir / "no_reload.html"
        template_file.write_text("Original: {{ value }}")

        result1 = await templates_no_reload.render("no_reload.html", value=1)
        assert result1 == "Original: 1"

        # Modify template
        template_file.write_text("Modified: {{ value }}")

        # Should still use cached version
        result2 = await templates_no_reload.render("no_reload.html", value=2)
        assert result2 == "Original: 2"  # Still using cached template

    @pytest.mark.asyncio
    async def test_cache_size_limit(self, template_dir):
        """Test template cache size limit."""
        from acb.adapters.templates import TemplatesAdapter

        templates_small_cache = TemplatesAdapter(
            template_dir=template_dir, cache_size=2
        )

        # Create 3 templates
        for i in range(3):
            (template_dir / f"template{i}.html").write_text(f"Template {i}")

        # Render all 3 templates
        await templates_small_cache.render("template0.html")
        await templates_small_cache.render("template1.html")
        await templates_small_cache.render("template2.html")

        # All should render correctly (cache eviction happens automatically)
        result = await templates_small_cache.render("template0.html")
        assert result == "Template 0"


class TestAsyncEdgeCases:
    """Test edge cases in async rendering."""

    @pytest.mark.asyncio
    async def test_empty_template(self, templates, template_dir):
        """Test rendering empty template."""
        empty = template_dir / "empty.html"
        empty.write_text("")

        result = await templates.render("empty.html")
        assert result == ""

    @pytest.mark.asyncio
    async def test_template_with_only_whitespace(self, templates, template_dir):
        """Test rendering template with only whitespace."""
        whitespace = template_dir / "whitespace.html"
        whitespace.write_text("   \n\n   \t   ")

        result = await templates.render("whitespace.html")
        assert result.strip() == ""

    @pytest.mark.asyncio
    async def test_unicode_content(self, templates):
        """Test rendering templates with unicode content."""
        template = "{{ greeting }} 世界! {{ emoji }}"
        result = await templates.render_string(template, greeting="你好", emoji="🌍")

        assert "你好 世界! 🌍" in result

    @pytest.mark.asyncio
    async def test_special_characters_escaped(self, templates):
        """Test that special HTML characters are escaped."""
        content = "< > & \" '"
        result = await templates.render_string("{{ content }}", content=content)

        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result

    @pytest.mark.asyncio
    async def test_very_large_template(self, templates, template_dir):
        """Test rendering very large template."""
        large_content = "{{ value }}\n" * 10000
        large = template_dir / "large.html"
        large.write_text(large_content)

        result = await templates.render("large.html", value="X")
        assert result.count("X") == 10000

    @pytest.mark.asyncio
    async def test_deeply_nested_inheritance(self, templates, template_dir):
        """Test deeply nested template inheritance."""
        # Create base template
        (template_dir / "level0.html").write_text(
            "{% block content %}Level 0{% endblock %}"
        )

        # Create 5 levels of inheritance
        for i in range(1, 6):
            content = (
                f'{{% extends "level{i - 1}.html" %}}\n'
                f"{{% block content %}}Level {i}{{% endblock %}}"
            )
            (template_dir / f"level{i}.html").write_text(content)

        result = await templates.render("level5.html")
        assert "Level 5" in result
