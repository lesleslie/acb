"""Pytest fixtures for templates adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import typing as t

if t.TYPE_CHECKING:
    from acb.adapters.templates import TemplatesAdapter


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    """Create temporary template directory."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    return template_dir


@pytest.fixture
def templates(template_dir: Path) -> TemplatesAdapter:
    """Create templates adapter with temp directory."""
    from acb.adapters.templates import TemplatesAdapter

    return TemplatesAdapter(template_dir=template_dir)


@pytest.fixture
def sample_template(template_dir: Path) -> Path:
    """Create sample template file."""
    template_file = template_dir / "sample.html"
    template_file.write_text("Hello {{ name }}!")
    return template_file


@pytest.fixture
def complex_template(template_dir: Path) -> Path:
    """Create complex template with filters and inheritance."""
    base_template = template_dir / "base.html"
    base_template.write_text(
        """<!DOCTYPE html>
<html>
<head><title>{% block title %}Default{% endblock %}</title></head>
<body>
{% block content %}{% endblock %}
</body>
</html>"""
    )

    child_template = template_dir / "child.html"
    child_template.write_text(
        """{% extends "base.html" %}
{% block title %}{{ title }}{% endblock %}
{% block content %}
<h1>{{ title }}</h1>
<p>{{ description }}</p>
<p>Created: {{ created_at|datetime }}</p>
<p>Size: {{ file_size|filesize }}</p>
<pre>{{ data|json(2) }}</pre>
{% endblock %}"""
    )

    return child_template


@pytest.fixture
def email_templates(template_dir: Path) -> Path:
    """Create email template structure."""
    email_dir = template_dir / "email"
    email_dir.mkdir()

    base = email_dir / "base.html"
    base.write_text(
        """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<div class="header">{{ site_name }}</div>
<div class="content">{% block content %}{% endblock %}</div>
<div class="footer">&copy; {{ year }} {{ site_name }}</div>
</body>
</html>"""
    )

    welcome = email_dir / "welcome.html"
    welcome.write_text(
        """{% extends "email/base.html" %}
{% block content %}
<h2>Welcome, {{ user.name }}!</h2>
<p>Email: {{ user.email }}</p>
<p>Joined: {{ joined_at|datetime("%B %d, %Y") }}</p>
{% endblock %}"""
    )

    return email_dir
