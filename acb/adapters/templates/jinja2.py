from __future__ import annotations

from pathlib import Path

import typing as t
from jinja2 import FileSystemLoader, select_autoescape
from jinja2_async_environment import AsyncEnvironment

from ._base import TemplatesBase, TemplatesBaseSettings
from ._filters import register_default_filters

if t.TYPE_CHECKING:
    from collections.abc import Callable


class Jinja2Templates(TemplatesBase):
    """Async Jinja2 template adapter for ACB projects.

    Features:
    - Async-first rendering via jinja2-async-environment
    - ACB dependency injection integration
    - FileSystemLoader with configurable template directory
    - Custom filter and global registration
    - Auto-escaping for HTML/XML by default

    Example:
        ```python
        from acb.adapters import import_adapter
        from acb.depends import depends

        # Configure via DI
        templates = Jinja2Templates(template_dir="templates")
        depends.set("templates", templates)

        # Render template
        html = await templates.render("index.html", title="Hello World")
        ```
    """

    def __init__(
        self,
        template_dir: Path | str | None = None,
        *,
        enable_async: bool = True,
        autoescape: bool = True,
        cache_size: int = 400,
        auto_reload: bool = True,
        settings: TemplatesBaseSettings | None = None,
    ) -> None:
        """Initialize Jinja2 templates adapter.

        Args:
            template_dir: Directory containing templates (default: ./templates)
            enable_async: Enable async template rendering (default: True)
            autoescape: Enable HTML/XML autoescaping (default: True)
            cache_size: Compiled template cache size (default: 400)
            auto_reload: Auto-reload templates when changed (default: True)
            settings: Optional settings object (overrides other params)
        """
        # Initialize base with settings
        if settings is None:
            settings = TemplatesBaseSettings(
                template_dir=template_dir,
                enable_async=enable_async,
                autoescape=autoescape,
                cache_size=cache_size,
                auto_reload=auto_reload,
            )
        super().__init__(settings)

        # Ensure template directory exists
        template_dir_setting = self.settings.template_dir
        if template_dir_setting is None:
            template_dir_setting = Path.cwd() / "templates"
        self.template_dir = Path(template_dir_setting)
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Configure async Jinja2 environment
        self.env = AsyncEnvironment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=(
                select_autoescape(
                    enabled_extensions=["html", "xml"],
                    default_for_string=True,  # Enable for render_string() too
                    default=True,  # Required for from_string() to escape
                )
                if self.settings.autoescape
                else False
            ),
            enable_async=self.settings.enable_async,
            cache_size=self.settings.cache_size,
            auto_reload=self.settings.auto_reload,
        )

        # Register default filters
        register_default_filters(self)

    async def render(
        self,
        template_name: str,
        context: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> str:
        """Render a template file asynchronously.

        Args:
            template_name: Template filename (relative to template_dir)
            context: Template context dictionary
            **kwargs: Additional context variables

        Returns:
            Rendered template string

        Raises:
            TemplateNotFound: If template file doesn't exist

        Example:
            ```python
            html = await templates.render(
                "user_profile.html",
                user={"name": "Alice", "email": "alice@example.com"},
            )
            ```
        """
        template = await self.env.get_template_async(template_name)
        merged_context = {**(context or {}), **kwargs}

        ctx = template.new_context(merged_context)
        rendering = template.root_render_func(ctx)
        return await self._render_to_string(rendering)

    async def render_string(
        self,
        template_string: str,
        context: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> str:
        """Render a template string asynchronously.

        Args:
            template_string: Jinja2 template string
            context: Template context dictionary
            **kwargs: Additional context variables

        Returns:
            Rendered template string

        Example:
            ```python
            html = await templates.render_string("Hello {{ name }}!", name="World")
            ```
        """
        template = self.env.from_string(template_string)
        merged_context = {**(context or {}), **kwargs}

        ctx = template.new_context(merged_context)
        rendering = template.root_render_func(ctx)
        return await self._render_to_string(rendering)

    async def _render_to_string(self, rendering: t.Any) -> str:
        chunks = await self._collect_render_chunks(rendering)
        return "".join(chunks)

    async def _collect_render_chunks(self, rendering: t.Any) -> list[str]:
        if rendering is None:
            return []
        if isinstance(rendering, str):
            return [rendering]
        if isinstance(rendering, bytes):
            return [rendering.decode()]
        if hasattr(rendering, "__aiter__"):
            return [self._ensure_text(chunk) async for chunk in rendering]
        if hasattr(rendering, "__await__"):
            awaited_result = await rendering
            return await self._collect_render_chunks(awaited_result)
        if hasattr(rendering, "__iter__"):
            return [self._ensure_text(chunk) for chunk in rendering]
        return [self._ensure_text(rendering)]

    def _ensure_text(self, value: t.Any) -> str:
        if isinstance(value, bytes):
            return value.decode()
        return str(value)

    def add_filter(self, name: str, func: Callable[..., t.Any]) -> None:
        """Register a custom template filter.

        Args:
            name: Filter name (used in templates)
            func: Filter function

        Example:
            ```python
            templates.add_filter("uppercase", lambda x: x.upper())
            # Template: {{ name|uppercase }}
            ```
        """
        self.env.filters[name] = func

    def add_global(self, name: str, value: t.Any) -> None:
        """Register a global variable available in all templates.

        Args:
            name: Global variable name
            value: Variable value (can be any type)

        Example:
            ```python
            templates.add_global("site_name", "My Awesome Site")
            # Template: {{ site_name }}
            ```
        """
        self.env.globals[name] = value


# Alias for convenience
TemplatesAdapter = Jinja2Templates

__all__ = ["Jinja2Templates", "TemplatesAdapter", "TemplatesBaseSettings"]
