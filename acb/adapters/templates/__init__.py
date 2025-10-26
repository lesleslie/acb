"""ACB Templates Adapter - Async Jinja2 template rendering.

Provides lightweight, async-first Jinja2 template rendering with ACB
dependency injection integration.

Usage:
    ```python
    from acb.adapters.templates import TemplatesAdapter
    from acb.depends import depends

    # Configure
    templates = TemplatesAdapter(template_dir="templates")
    depends.set("templates", templates)

    # Render
    html = await templates.render("index.html", title="Hello")
    ```
"""

from ._base import TemplatesBase, TemplatesBaseSettings
from ._filters import (
    datetime_filter,
    filesize_filter,
    json_filter,
    register_default_filters,
)
from .jinja2 import Jinja2Templates, TemplatesAdapter

__all__ = [
    "TemplatesAdapter",
    "Jinja2Templates",
    "TemplatesBase",
    "TemplatesBaseSettings",
    "register_default_filters",
    "json_filter",
    "datetime_filter",
    "filesize_filter",
]
