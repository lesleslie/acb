"""Unit tests for the async Jinja2 templates adapter."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import asyncio
import pytest

from acb.adapters.templates.jinja2 import Jinja2Templates


@pytest.fixture()
def tmp_templates(tmp_path: Path) -> Path:
    tdir = tmp_path / "templates"
    tdir.mkdir()
    (tdir / "hello.html").write_text("Hello {{ name }}!")
    (tdir / "mixed.html").write_text("A:{{ a }} B:{{ b }}")
    return tdir


@pytest.mark.unit
async def test_render_file(tmp_templates: Path) -> None:
    tpl = Jinja2Templates(template_dir=tmp_templates)
    out = await tpl.render("hello.html", {"name": "World"})
    assert out == "Hello World!"


@pytest.mark.unit
async def test_render_file_merge_context(tmp_templates: Path) -> None:
    tpl = Jinja2Templates(template_dir=tmp_templates)
    out = await tpl.render("mixed.html", {"a": 1}, b=2)
    assert out == "A:1 B:2"


@pytest.mark.unit
async def test_render_string_basic() -> None:
    tpl = Jinja2Templates(template_dir=Path("nonexistent"))
    out = await tpl.render_string("Hi {{ who }}", who="there")
    assert out == "Hi there"


@pytest.mark.unit
async def test_collect_render_chunks_variants() -> None:
    tpl = Jinja2Templates(template_dir=Path("nonexistent"))

    # str and bytes
    assert await tpl._collect_render_chunks("x") == ["x"]
    assert await tpl._collect_render_chunks(b"y") == ["y"]

    # awaitable returning str
    async def _aw() -> str:
        await asyncio.sleep(0)
        return "z"

    assert await tpl._collect_render_chunks(_aw()) == ["z"]

    # async iterator
    async def _agen() -> AsyncGenerator[str]:
        for part in ("a", "b", "c"):
            await asyncio.sleep(0)
            yield part

    assert await tpl._collect_render_chunks(_agen()) == ["a", "b", "c"]
