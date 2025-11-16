"""Unit tests for input sanitization helpers."""

from __future__ import annotations

import pytest

from acb.services.validation._base import ValidationConfig
from acb.services.validation.sanitization import (
    DataSanitizer,
    InputSanitizer,
    PathSanitizer,
    SQLSanitizer,
    URLSanitizer,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_input_sanitizer_auto_and_specific() -> None:
    cfg = ValidationConfig(
        enable_xss_protection=True,
        enable_sql_injection_protection=True,
        enable_path_traversal_protection=True,
    )
    s = InputSanitizer(cfg)
    # auto sanitization should add warnings for script tags and SQL comments
    val = "<script>alert(1)</script> SELECT * FROM users -- comment"
    res = await s.sanitize(val, sanitization_type="auto")
    assert isinstance(res.value, str)
    assert res.warnings  # some warnings emitted

    # specific type: url
    res2 = await s.sanitize("javascript:alert(1)", sanitization_type="url")
    assert not res2.is_valid


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sql_sanitizer_patterns() -> None:
    sql = SQLSanitizer()
    res = await sql.sanitize("SELECT * FROM users; -- drop")
    assert res.warnings  # pattern detected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_path_and_url_sanitizers() -> None:
    ps = PathSanitizer()
    resp = await ps.sanitize("/var//log/../log/app.log")
    assert isinstance(resp.value, str)

    us = URLSanitizer()
    resu = await us.sanitize("http://example.com/?q=<b>x</b>")
    assert resu.warnings  # HTML in query gets sanitized


@pytest.mark.unit
@pytest.mark.asyncio
async def test_data_sanitizer_helpers() -> None:
    ds = DataSanitizer(ValidationConfig(max_string_length=5))
    res_len = await ds.sanitize_string_length("abcdef")
    assert res_len.value == "abcde" and res_len.warnings
    res_ws = await ds.sanitize_whitespace("  a\x00\t b  ")
    assert res_ws.value == "a b"
    res_enc = await ds.sanitize_encoding("abc")
    assert res_enc.value == "abc"
