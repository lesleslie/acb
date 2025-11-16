"""Tests for dependency injection integration."""

from __future__ import annotations

import pytest

from acb.adapters.templates import TemplatesAdapter
from acb.depends import Inject, depends


class TestDependencyInjection:
    """Test ACB dependency injection integration."""

    @pytest.mark.asyncio
    async def test_templates_with_depends(self, templates):
        """Test setting templates adapter in depends."""
        depends.set(TemplatesAdapter, templates)

        retrieved = await depends.get(TemplatesAdapter)
        assert retrieved is templates

    def test_inject_decorator(self, templates, sample_template):
        """Test injecting templates via @depends.inject."""
        depends.set(TemplatesAdapter, templates)

        @depends.inject
        async def render_greeting(name: str, templates: Inject[TemplatesAdapter]):
            return await templates.render("sample.html", name=name)

        import asyncio

        result = asyncio.run(render_greeting("Alice"))
        assert result == "Hello Alice!"

    @pytest.mark.asyncio
    async def test_multiple_di_instances(self, template_dir):
        """Test using multiple template adapters via DI."""
        # Create two separate template directories
        emails_dir = template_dir / "emails"
        emails_dir.mkdir()
        (emails_dir / "test.html").write_text("Email: {{ msg }}")

        reports_dir = template_dir / "reports"
        reports_dir.mkdir()
        (reports_dir / "test.html").write_text("Report: {{ msg }}")

        # Set up two adapters with different keys
        email_templates = TemplatesAdapter(template_dir=emails_dir)
        report_templates = TemplatesAdapter(template_dir=reports_dir)

        depends.set("email_templates", email_templates)
        depends.set("report_templates", report_templates)

        # Verify they're independent
        assert (await depends.get("email_templates")) is email_templates
        assert (await depends.get("report_templates")) is report_templates
        assert (await depends.get("email_templates")) is not (
            await depends.get("report_templates")
        )

    def test_settings_injection(self, template_dir):
        """Test that settings use DI for Config."""
        from acb.adapters.templates import TemplatesBaseSettings

        # Settings should work without explicit config
        settings = TemplatesBaseSettings(template_dir=template_dir)

        assert settings.template_dir == template_dir
        assert settings.enable_async is True
        assert settings.autoescape is True


class TestSettingsConfiguration:
    """Test settings configuration patterns."""

    def test_settings_defaults(self):
        """Test default settings values."""
        from pathlib import Path

        from acb.adapters.templates import TemplatesBaseSettings

        settings = TemplatesBaseSettings()

        assert settings.template_dir == Path.cwd() / "templates"
        assert settings.enable_async is True
        assert settings.autoescape is True
        assert settings.cache_size == 400
        assert settings.auto_reload is True

    def test_settings_custom_values(self, template_dir):
        """Test settings with custom values."""
        from acb.adapters.templates import TemplatesBaseSettings

        settings = TemplatesBaseSettings(
            template_dir=template_dir,
            enable_async=False,
            autoescape=False,
            cache_size=100,
            auto_reload=False,
        )

        assert settings.template_dir == template_dir
        assert settings.enable_async is False
        assert settings.autoescape is False
        assert settings.cache_size == 100
        assert settings.auto_reload is False

    def test_settings_path_conversion(self):
        """Test that string paths are converted to Path objects."""
        from pathlib import Path

        from acb.adapters.templates import TemplatesBaseSettings

        settings = TemplatesBaseSettings(template_dir="custom/templates")

        assert isinstance(settings.template_dir, Path)
        assert settings.template_dir == Path("custom/templates")

    def test_adapter_with_settings_object(self, template_dir):
        """Test adapter initialization with settings object."""
        from acb.adapters.templates import TemplatesAdapter, TemplatesBaseSettings

        settings = TemplatesBaseSettings(template_dir=template_dir, cache_size=500)

        templates = TemplatesAdapter(settings=settings)

        assert templates.settings is settings
        assert templates.settings.cache_size == 500
        assert templates.template_dir == template_dir

    def test_adapter_settings_override(self, template_dir):
        """Test that adapter constructor params create settings."""
        templates = TemplatesAdapter(
            template_dir=template_dir,
            cache_size=300,
            auto_reload=False,
        )

        assert templates.settings.template_dir == template_dir
        assert templates.settings.cache_size == 300
        assert templates.settings.auto_reload is False


class TestDIPatterns:
    """Test common DI usage patterns."""

    @pytest.mark.asyncio
    async def test_function_level_injection(self, templates, sample_template):
        """Test injecting templates at function level."""
        from acb.depends import depends

        depends.set(TemplatesAdapter, templates)

        @depends.inject
        async def generate_html(
            title: str, content: str, templates: Inject[TemplatesAdapter]
        ):
            return await templates.render_string(
                "<h1>{{ title }}</h1><p>{{ content }}</p>",
                title=title,
                content=content,
            )

        result = await generate_html("Test", "Content")
        assert "<h1>Test</h1>" in result
        assert "<p>Content</p>" in result

    @pytest.mark.asyncio
    async def test_class_method_injection(self, templates):
        """Test injecting templates into class methods."""
        from acb.depends import depends

        depends.set(TemplatesAdapter, templates)

        class EmailService:
            @depends.inject
            async def render_email(
                self, subject: str, templates: Inject[TemplatesAdapter]
            ):
                return await templates.render_string(
                    "Subject: {{ subject }}", subject=subject
                )

        service = EmailService()
        result = await service.render_email("Test Email")
        assert "Subject: Test Email" in result

    @pytest.mark.asyncio
    async def test_di_override_pattern(self, templates, template_dir):
        """Test DI override pattern for testing."""
        # Set default templates
        depends.set(TemplatesAdapter, templates)

        # Create mock templates for testing
        mock_dir = template_dir / "mock"
        mock_dir.mkdir()
        mock_templates = TemplatesAdapter(template_dir=mock_dir)

        # Override in DI (just set again, ACB allows overwriting)
        depends.set("templates", mock_templates)

        assert (await depends.get("templates")) is mock_templates
        assert (await depends.get("templates")) is not templates

    @pytest.mark.asyncio
    async def test_multiple_injections(self, templates):
        """Test function with multiple DI injections."""
        from acb.depends import depends

        depends.set(TemplatesAdapter, templates)

        @depends.inject
        async def render_with_config(
            app_name: str, templates: Inject[TemplatesAdapter]
        ):
            return await templates.render_string(
                "App: {{ app_name }}", app_name=app_name
            )

        result = await render_with_config("Test App")
        assert "App: Test App" in result
