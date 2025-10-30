# ACB Templates Adapter

**Async-first Jinja2 template rendering with ACB dependency injection integration**

## Overview

The ACB Templates Adapter provides lightweight, production-ready template rendering for Python projects using Jinja2 with async support. It integrates seamlessly with ACB's dependency injection system and follows the same adapter patterns as other ACB components.

## Features

- ✨ **Async-First Architecture**: Built on `jinja2-async-environment` for true async rendering
- 🔌 **DI Integration**: Native ACB dependency injection support with `depends`
- 📁 **FileSystemLoader**: Load templates from disk with automatic directory creation
- 🎨 **Custom Filters**: Register custom Jinja2 filters and global variables
- 🔒 **Auto-Escaping**: HTML/XML auto-escaping enabled by default for security
- ⚡ **Template Caching**: Built-in Jinja2 cache with configurable size (default: 400)
- 🔄 **Auto-Reload**: Development-friendly template auto-reloading
- 📦 **Default Filters**: Includes `json`, `datetime`, and `filesize` filters out of the box

## Installation

Add the templates dependency group to your project:

```bash
uv add acb --group templates
```

Or add directly to `pyproject.toml`:

```toml
[dependency-groups]
templates = [
    "jinja2>=3.1.6",
    "jinja2-async-environment>=0.14.3",
]
```

## Quick Start

### Basic Usage

```python
from acb.adapters.templates import TemplatesAdapter
from acb.depends import depends

# Initialize with default settings (./templates directory)
templates = TemplatesAdapter()

# Register with DI system
depends.set("templates", templates)

# Render a template
html = await templates.render("index.html", title="Hello World", user="Alice")
```

### With Custom Configuration

```python
from acb.adapters.templates import TemplatesAdapter, TemplatesBaseSettings

# Create custom settings
settings = TemplatesBaseSettings(
    template_dir="custom/templates",
    enable_async=True,
    autoescape=True,
    cache_size=500,
    auto_reload=False,  # Disable for production
)

# Initialize with settings
templates = TemplatesAdapter(settings=settings)
```

### Dependency Injection Pattern

```python
from acb.depends import depends, Inject

# Set up templates in DI container
templates = TemplatesAdapter(template_dir="templates")
depends.set("templates", templates)


# Inject into async functions
@depends.inject
async def render_email(
    user: dict[str, str], templates: Inject["TemplatesAdapter"]
) -> str:
    """Render email template with DI."""
    return await templates.render(
        "email/welcome.html", user=user, site_name="My Awesome Site"
    )


# Use the function
html = await render_email({"name": "Alice", "email": "alice@example.com"})
```

## API Reference

### TemplatesAdapter / Jinja2Templates

Main adapter class for async template rendering.

#### Constructor Parameters

```
TemplatesAdapter(
    template_dir: Path | str | None = None,  # Default: ./templates
    *,
    enable_async: bool = True,
    autoescape: bool = True,
    cache_size: int = 400,
    auto_reload: bool = True,
    settings: TemplatesBaseSettings | None = None
)
```

#### Methods

##### `async render(template_name: str, context: dict | None = None, **kwargs) -> str`

Render a template file asynchronously.

```python
html = await templates.render(
    "user_profile.html",
    user={"name": "Alice", "email": "alice@example.com"},
    title="User Profile",
)
```

##### `async render_string(template_string: str, context: dict | None = None, **kwargs) -> str`

Render a template string asynchronously.

```python
html = await templates.render_string("Hello {{ name }}!", name="World")
```

##### `add_filter(name: str, func: Callable) -> None`

Register a custom template filter.

```python
templates.add_filter("uppercase", lambda x: x.upper())
# In template: {{ name|uppercase }}
```

##### `add_global(name: str, value: Any) -> None`

Register a global variable available in all templates.

```python
templates.add_global("site_name", "My Awesome Site")
# In template: {{ site_name }}
```

## Default Filters

The adapter includes three built-in filters:

### `json` Filter

Convert Python objects to JSON strings.

```jinja2
{# Basic usage #}
{{ data|json }}

{# Pretty print with indentation #}
{{ data|json(2) }}
```

```python
# Python
data = {"name": "Alice", "age": 30}
```

```json
// Output
{"name": "Alice", "age": 30}
```

### `datetime` Filter

Format datetime objects or ISO strings.

```jinja2
{# Default format: %Y-%m-%d %H:%M:%S #}
{{ timestamp|datetime }}

{# Custom format #}
{{ timestamp|datetime("%B %d, %Y") }}
```

```python
# Python
from datetime import datetime

timestamp = datetime(2025, 1, 25, 14, 30, 0)
```

```html
<!-- Output -->
2025-01-25 14:30:00
January 25, 2025
```

### `filesize` Filter

Format file sizes in human-readable format.

```jinja2
{# Binary units (default): KiB, MiB, GiB #}
{{ file_size|filesize }}

{# Decimal units: KB, MB, GB #}
{{ file_size|filesize(False) }}
```

```python
# Python
file_size = 1536  # bytes
```

```html
<!-- Output -->
1.5 KiB
1.5 KB
```

## Custom Filters Example

```python
from datetime import datetime
from acb.adapters.templates import TemplatesAdapter

templates = TemplatesAdapter()


# Add custom filter for currency formatting
def currency(value: float, symbol: str = "$") -> str:
    """Format value as currency."""
    return f"{symbol}{value:,.2f}"


templates.add_filter("currency", currency)


# Add custom filter for truncation
def truncate(value: str, length: int = 50, suffix: str = "...") -> str:
    """Truncate string to specified length."""
    if len(value) <= length:
        return value
    return value[:length].rsplit(" ", 1)[0] + suffix


templates.add_filter("truncate", truncate)

# Use in template
html = await templates.render(
    "product.html", price=1299.99, description="A very long product description..."
)
```

**Template (`product.html`):**

```jinja2
<div class="product">
    <p class="price">{{ price|currency }}</p>
    <p class="description">{{ description|truncate(30) }}</p>
</div>
```

**Output:**

```html
<div class="product">
    <p class="price">$1,299.99</p>
    <p class="description">A very long product...</p>
</div>
```

## Template Examples

### Email Template with Layout Inheritance

**Base Layout (`templates/email/base.html`):**

```jinja2
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ site_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .header { background: #007bff; color: white; padding: 20px; }
        .content { padding: 20px; }
        .footer { background: #f8f9fa; padding: 10px; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ site_name }}</h1>
    </div>
    <div class="content">
        {% block content %}{% endblock %}
    </div>
    <div class="footer">
        <p>&copy; 2025 {{ site_name }}. All rights reserved.</p>
    </div>
</body>
</html>
```

**Welcome Email (`templates/email/welcome.html`):**

```jinja2
{% extends "email/base.html" %}

{% block content %}
    <h2>Welcome, {{ user.name }}!</h2>
    <p>We're excited to have you on board.</p>
    <p>Your account email: <strong>{{ user.email }}</strong></p>
    <p>Account created: {{ created_at|datetime("%B %d, %Y") }}</p>

    <a href="{{ activation_link }}" style="
        display: inline-block;
        padding: 10px 20px;
        background: #007bff;
        color: white;
        text-decoration: none;
        border-radius: 5px;
    ">Activate Account</a>
{% endblock %}
```

**Usage:**

```python
from datetime import datetime

html = await templates.render(
    "email/welcome.html",
    user={"name": "Alice", "email": "alice@example.com"},
    created_at=datetime.now(),
    activation_link="https://example.com/activate/abc123",
    site_name="My Awesome Site",
)
```

## Configuration Best Practices

### Development Settings

```python
from acb.adapters.templates import TemplatesAdapter

# Development: Enable auto-reload, smaller cache
dev_templates = TemplatesAdapter(
    template_dir="templates",
    enable_async=True,
    autoescape=True,
    cache_size=100,
    auto_reload=True,  # Reload templates on change
)
```

### Production Settings

```python
from acb.adapters.templates import TemplatesAdapter

# Production: Disable auto-reload, larger cache
prod_templates = TemplatesAdapter(
    template_dir="templates",
    enable_async=True,
    autoescape=True,
    cache_size=500,
    auto_reload=False,  # Never reload for performance
)
```

### Using Environment Variables

```python
import os
from pathlib import Path
from acb.adapters.templates import TemplatesAdapter

templates = TemplatesAdapter(
    template_dir=os.getenv("TEMPLATE_DIR", "templates"),
    auto_reload=os.getenv("ENV") == "development",
    cache_size=int(os.getenv("TEMPLATE_CACHE_SIZE", "400")),
)
```

## Integration Examples

### With FastAPI

```python
from fastapi import FastAPI, Depends
from acb.adapters.templates import TemplatesAdapter
from acb.depends import depends, Inject

app = FastAPI()

# Set up templates
templates = TemplatesAdapter(template_dir="templates")
depends.set("templates", templates)


@app.get("/")
@depends.inject
async def home(templates: Inject["TemplatesAdapter"]):
    """Render homepage."""
    html = await templates.render("index.html", title="Home")
    return {"html": html}


@app.get("/user/{user_id}")
@depends.inject
async def user_profile(user_id: int, templates: Inject["TemplatesAdapter"]):
    """Render user profile."""
    # Fetch user from database
    user = {"id": user_id, "name": "Alice", "email": "alice@example.com"}
    html = await templates.render("user_profile.html", user=user)
    return {"html": html}
```

### With FastHTML / HTMX

```python
from fasthtml import FastHTML, serve
from acb.adapters.templates import TemplatesAdapter
from acb.depends import depends

app = FastHTML()
templates = TemplatesAdapter(template_dir="templates")
depends.set("templates", templates)


@app.get("/partial/user/{user_id}")
async def user_partial(user_id: int):
    """Return HTMX partial."""
    templates = depends.get("templates")
    user = {"id": user_id, "name": "Alice"}
    return await templates.render("partials/user_card.html", user=user)
```

### Standalone CLI Tool

```python
import asyncio
from acb.adapters.templates import TemplatesAdapter


async def generate_report():
    """Generate HTML report."""
    templates = TemplatesAdapter(template_dir="report_templates")

    data = {
        "title": "Monthly Report",
        "generated_at": datetime.now(),
        "metrics": [
            {"name": "Users", "value": 1234},
            {"name": "Revenue", "value": 56789.99},
        ],
    }

    html = await templates.render("report.html", **data)

    # Save to file
    with open("report.html", "w") as f:
        f.write(html)

    print("✅ Report generated: report.html")


if __name__ == "__main__":
    asyncio.run(generate_report())
```

## Testing Templates

### Unit Test Example

```python
import pytest
from acb.adapters.templates import TemplatesAdapter
from pathlib import Path


@pytest.fixture
async def templates(tmp_path):
    """Create templates adapter with temp directory."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    # Create test template
    (template_dir / "test.html").write_text("Hello {{ name }}!")

    return TemplatesAdapter(template_dir=template_dir)


@pytest.mark.asyncio
async def test_render_basic(templates):
    """Test basic template rendering."""
    result = await templates.render("test.html", name="World")
    assert result == "Hello World!"


@pytest.mark.asyncio
async def test_render_string(templates):
    """Test string template rendering."""
    result = await templates.render_string("{{ value|json }}", value={"key": "data"})
    assert '"key": "data"' in result


@pytest.mark.asyncio
async def test_custom_filter(templates):
    """Test custom filter registration."""
    templates.add_filter("double", lambda x: x * 2)
    result = await templates.render_string("{{ value|double }}", value=5)
    assert result == "10"
```

## Performance Considerations

### Template Caching

The adapter uses Jinja2's built-in caching mechanism. Templates are compiled once and cached in memory.

```python
# Default cache size: 400 compiled templates
templates = TemplatesAdapter(cache_size=400)

# Increase for large applications
templates = TemplatesAdapter(cache_size=1000)

# Disable caching (not recommended)
templates = TemplatesAdapter(cache_size=0)
```

### Async Benefits

The async architecture allows for concurrent template rendering without blocking:

```python
import asyncio


async def render_multiple():
    """Render multiple templates concurrently."""
    tasks = [
        templates.render("email/welcome.html", user=user1),
        templates.render("email/welcome.html", user=user2),
        templates.render("email/welcome.html", user=user3),
    ]
    results = await asyncio.gather(*tasks)
    return results
```

### Auto-Reload in Production

Disable auto-reload in production to avoid filesystem checks:

```python
# Development
dev_templates = TemplatesAdapter(auto_reload=True)

# Production
prod_templates = TemplatesAdapter(auto_reload=False)
```

## Troubleshooting

### Template Not Found

```python
# Error: TemplateNotFound: index.html

# Solution: Check template directory
templates = TemplatesAdapter(template_dir="templates")
print(templates.template_dir)  # Verify path

# Ensure file exists
from pathlib import Path

assert (Path(templates.template_dir) / "index.html").exists()
```

### Import Errors

```python
# Error: ModuleNotFoundError: No module named 'jinja2_async_environment'

# Solution: Install templates dependency group
# uv add acb --group templates
```

### Auto-Escaping Issues

```python
# Problem: HTML tags are escaped in output

# Jinja2 auto-escaping is enabled by default for security
templates = TemplatesAdapter(autoescape=True)  # Default

# To render HTML as-is, use |safe filter in template:
# {{ html_content|safe }}

# Or disable auto-escaping (not recommended):
templates = TemplatesAdapter(autoescape=False)
```

## Comparison to Other Solutions

### vs. Plain Jinja2

**ACB Templates Adapter Benefits:**

- ✅ Async-first architecture (async/await support)
- ✅ Dependency injection integration
- ✅ Default filters included
- ✅ Automatic directory creation
- ✅ Consistent with other ACB adapters

**Plain Jinja2:**

- ❌ Sync-only by default
- ❌ Manual DI setup
- ❌ No default filters
- ❌ Manual configuration

### vs. FastBlocks Templates

**ACB Templates Adapter:**

- ✅ Lightweight (400 lines vs 37,000+)
- ✅ Simple API, focused on rendering
- ✅ No external service dependencies
- ❌ No Redis caching
- ❌ No HTMY integration

**FastBlocks Templates:**

- ✅ Redis caching support
- ✅ HTMY integration
- ✅ Cloud storage backends
- ❌ Much more complex
- ❌ Higher resource requirements

## Architecture

The templates adapter follows ACB's standard adapter pattern:

```
acb/adapters/templates/
├── __init__.py              # Public API exports
├── _base.py                 # Base classes and settings
├── _filters.py              # Default filter functions
├── jinja2.py                # Main Jinja2 adapter implementation
└── README.md                # This file
```

### Class Hierarchy

```
TemplatesBase (abstract base class)
    └── Jinja2Templates (concrete implementation)
            └── TemplatesAdapter (alias)

TemplatesBaseSettings (settings with DI)
```

### Dependencies

**Core Dependencies:**

- `jinja2>=3.1.6` - Template engine
- `jinja2-async-environment>=0.14.3` - Async rendering support

**ACB Dependencies:**

- `acb.config.Settings` - Settings base class
- `acb.depends.depends` - Dependency injection

## Contributing

When contributing to the templates adapter:

1. **Follow ACB patterns**: Use existing adapters (cache, logger) as reference
1. **Type hints required**: All functions must have type annotations
1. **Async-first**: Use `async/await` for all I/O operations
1. **Test coverage**: Maintain ≥85% coverage
1. **Documentation**: Update README for new features

## License

Part of the ACB (Asynchronous Component Base) framework.

## Support

For issues, questions, or contributions:

- **GitHub Issues**: [acb/issues](https://github.com/lesleslie/acb/issues)
- **Documentation**: [acb.readthedocs.io](https://acb.readthedocs.io)
- **Email**: les@wedgwoodwebworks.com

______________________________________________________________________

**Version**: 0.26.0 (ACB Templates Adapter)
**Last Updated**: 2025-01-25
