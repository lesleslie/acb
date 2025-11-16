from pathlib import Path

import typing as t

from acb.config import Config, Settings
from acb.depends import Inject, depends


class TemplatesBaseSettings(Settings):
    """Base settings for templates adapters."""

    template_dir: Path | str | None = None
    enable_async: bool = True
    autoescape: bool = True
    cache_size: int = 400
    auto_reload: bool = True

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)

        # Default template_dir to cwd/templates if not specified
        if self.template_dir is None:
            self.template_dir = Path.cwd() / "templates"
        elif isinstance(self.template_dir, str):
            self.template_dir = Path(self.template_dir)


class TemplatesBase:
    """Base class for template adapters."""

    def __init__(self, settings: TemplatesBaseSettings | None = None) -> None:
        self.settings = settings or TemplatesBaseSettings()

    async def render(
        self,
        template_name: str,
        context: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> str:
        """Render a template file. Must be implemented by subclass."""
        raise NotImplementedError

    async def render_string(
        self,
        template_string: str,
        context: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> str:
        """Render a template string. Must be implemented by subclass."""
        raise NotImplementedError

    def add_filter(self, name: str, func: t.Callable[..., t.Any]) -> None:
        """Register a custom template filter. Must be implemented by subclass."""
        raise NotImplementedError

    def add_global(self, name: str, value: t.Any) -> None:
        """Register a global variable. Must be implemented by subclass."""
        raise NotImplementedError
