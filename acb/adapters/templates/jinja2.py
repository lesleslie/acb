from __future__ import annotations

import typing as t
from pathlib import Path

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
        self.template_dir = Path(self.settings.template_dir)
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

        # Use root_render_func directly for jinja2-async-environment compatibility
        # This is required for template inheritance to work properly
        ctx = template.new_context(merged_context)
        result = []
        rendering = template.root_render_func(ctx)

        # Handle different rendering result types (from jinja2-async-environment pattern)
        if hasattr(rendering, "__aiter__"):
            # It's an async generator - iterate directly
            async for chunk in rendering:
                result.append(chunk)
        elif hasattr(rendering, "__await__"):
            # It's a coroutine - await it first
            awaited_result = await rendering
            if awaited_result is not None:
                if hasattr(awaited_result, "__aiter__"):
                    # The awaited result is an async generator
                    async for chunk in awaited_result:
                        result.append(chunk)
                else:
                    # The awaited result is a simple value
                    result.append(str(awaited_result))
        elif hasattr(rendering, "__iter__") and not isinstance(rendering, str):
            # It's a regular iterator
            for chunk in rendering:
                result.append(chunk)
        elif rendering is not None:
            # It's a simple value
            result.append(str(rendering))

        return "".join(result)

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

        # Use root_render_func directly for jinja2-async-environment compatibility
        ctx = template.new_context(merged_context)
        result = []
        rendering = template.root_render_func(ctx)

        # Handle different rendering result types (from jinja2-async-environment pattern)
        if hasattr(rendering, "__aiter__"):
            # It's an async generator - iterate directly
            async for chunk in rendering:
                result.append(chunk)
        elif hasattr(rendering, "__await__"):
            # It's a coroutine - await it first
            awaited_result = await rendering
            if awaited_result is not None:
                if hasattr(awaited_result, "__aiter__"):
                    # The awaited result is an async generator
                    async for chunk in awaited_result:
                        result.append(chunk)
                else:
                    # The awaited result is a simple value
                    result.append(str(awaited_result))
        elif hasattr(rendering, "__iter__") and not isinstance(rendering, str):
            # It's a regular iterator
            for chunk in rendering:
                result.append(chunk)
        elif rendering is not None:
            # It's a simple value
            result.append(str(rendering))

        return "".join(result)

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
