"""Tests for basic template rendering functionality."""

from __future__ import annotations

import pytest
from datetime import datetime


class TestBasicRendering:
    """Test basic template rendering operations."""

    @pytest.mark.asyncio
    async def test_render_simple_template(self, templates, sample_template):
        """Test rendering a simple template with variable substitution."""
        result = await templates.render("sample.html", name="World")
        assert result == "Hello World!"

    @pytest.mark.asyncio
    async def test_render_with_context_dict(self, templates, sample_template):
        """Test rendering with context dictionary."""
        context = {"name": "Alice"}
        result = await templates.render("sample.html", context=context)
        assert result == "Hello Alice!"

    @pytest.mark.asyncio
    async def test_render_with_kwargs(self, templates, sample_template):
        """Test rendering with kwargs."""
        result = await templates.render("sample.html", name="Bob")
        assert result == "Hello Bob!"

    @pytest.mark.asyncio
    async def test_render_merges_context_and_kwargs(self, templates, sample_template):
        """Test that context and kwargs are merged."""
        context = {"name": "Charlie"}
        # kwargs should override context
        result = await templates.render("sample.html", context=context, name="David")
        assert result == "Hello David!"

    @pytest.mark.asyncio
    async def test_render_string_basic(self, templates):
        """Test rendering a template string."""
        result = await templates.render_string("Hello {{ name }}!", name="World")
        assert result == "Hello World!"

    @pytest.mark.asyncio
    async def test_render_string_with_context(self, templates):
        """Test rendering string with context dictionary."""
        context = {"greeting": "Hi", "name": "Alice"}
        result = await templates.render_string(
            "{{ greeting }} {{ name }}!", context=context
        )
        assert result == "Hi Alice!"

    @pytest.mark.asyncio
    async def test_template_not_found(self, templates):
        """Test error handling when template doesn't exist."""
        from jinja2 import TemplateNotFound

        with pytest.raises(TemplateNotFound):
            await templates.render("nonexistent.html")

    @pytest.mark.asyncio
    async def test_template_with_no_variables(self, templates, template_dir):
        """Test rendering template with no variables."""
        static_template = template_dir / "static.html"
        static_template.write_text("<h1>Static Content</h1>")

        result = await templates.render("static.html")
        assert result == "<h1>Static Content</h1>"

    @pytest.mark.asyncio
    async def test_template_with_missing_variable(self, templates, sample_template):
        """Test rendering with missing variable (Jinja2 default: renders as empty string)."""
        result = await templates.render("sample.html")
        # Jinja2's default Undefined renders as empty string ''
        assert result == "Hello !"


class TestTemplateInheritance:
    """Test template inheritance and blocks."""

    @pytest.mark.asyncio
    async def test_basic_inheritance(self, templates, complex_template):
        """Test basic template inheritance."""
        from datetime import datetime

        result = await templates.render(
            "child.html",
            title="Test Page",
            description="This is a test",
            created_at=datetime(2025, 1, 25, 14, 30, 0),
            file_size=1536,
            data={"key": "value"},
        )

        assert "<title>Test Page</title>" in result
        assert "<h1>Test Page</h1>" in result
        assert "<p>This is a test</p>" in result
        assert "2025-01-25 14:30:00" in result
        assert "1.5 KiB" in result
        assert '"key": "value"' in result

    @pytest.mark.asyncio
    async def test_email_template_inheritance(self, templates, email_templates):
        """Test email template structure with inheritance."""
        result = await templates.render(
            "email/welcome.html",
            site_name="Test Site",
            year=2025,
            user={"name": "Alice", "email": "alice@example.com"},
            joined_at=datetime(2025, 1, 25),
        )

        assert "Test Site" in result
        assert "Welcome, Alice!" in result
        assert "alice@example.com" in result
        assert "January 25, 2025" in result
        assert "&copy; 2025 Test Site" in result


class TestAutoEscaping:
    """Test HTML auto-escaping behavior."""

    @pytest.mark.asyncio
    async def test_auto_escaping_enabled_by_default(self, templates):
        """Test that auto-escaping is enabled by default."""
        html = "<script>alert('XSS')</script>"
        result = await templates.render_string("{{ content }}", content=html)
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
        assert "<script>" not in result

    @pytest.mark.asyncio
    async def test_safe_filter_disables_escaping(self, templates):
        """Test that |safe filter disables escaping."""
        html = "<strong>Bold</strong>"
        result = await templates.render_string("{{ content|safe }}", content=html)
        assert "<strong>Bold</strong>" in result

    @pytest.mark.asyncio
    async def test_auto_escaping_disabled(self, template_dir):
        """Test templates with auto-escaping disabled."""
        from acb.adapters.templates import TemplatesAdapter

        templates_no_escape = TemplatesAdapter(
            template_dir=template_dir, autoescape=False
        )

        html = "<script>alert('test')</script>"
        result = await templates_no_escape.render_string("{{ content }}", content=html)
        assert "<script>alert('test')</script>" in result
        assert "&lt;script&gt;" not in result


class TestTemplateSettings:
    """Test template adapter initialization and settings."""

    def test_default_settings(self, tmp_path):
        """Test adapter with default settings."""
        from acb.adapters.templates import TemplatesAdapter

        templates = TemplatesAdapter(template_dir=tmp_path / "templates")

        assert templates.settings.enable_async is True
        assert templates.settings.autoescape is True
        assert templates.settings.cache_size == 400
        assert templates.settings.auto_reload is True
        assert templates.template_dir == tmp_path / "templates"

    def test_custom_settings(self, tmp_path):
        """Test adapter with custom settings."""
        from acb.adapters.templates import TemplatesAdapter

        templates = TemplatesAdapter(
            template_dir=tmp_path / "custom",
            enable_async=False,
            autoescape=False,
            cache_size=200,
            auto_reload=False,
        )

        assert templates.settings.enable_async is False
        assert templates.settings.autoescape is False
        assert templates.settings.cache_size == 200
        assert templates.settings.auto_reload is False

    def test_settings_object(self, tmp_path):
        """Test adapter with settings object."""
        from acb.adapters.templates import TemplatesAdapter, TemplatesBaseSettings

        settings = TemplatesBaseSettings(
            template_dir=tmp_path / "templates",
            cache_size=500,
        )

        templates = TemplatesAdapter(settings=settings)
        assert templates.settings.cache_size == 500

    def test_template_directory_created(self, tmp_path):
        """Test that template directory is created if it doesn't exist."""
        from acb.adapters.templates import TemplatesAdapter

        new_dir = tmp_path / "new_templates"
        assert not new_dir.exists()

        TemplatesAdapter(template_dir=new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()
