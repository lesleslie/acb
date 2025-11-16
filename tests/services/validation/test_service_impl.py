"""Unit tests for ValidationService validate and validate_many."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typing import Any

from acb.services.validation._base import (
    ValidationConfig,
    ValidationResult,
    ValidationSchema,
)
from acb.services.validation.service import ValidationService


class _Schema(ValidationSchema):
    def __init__(
        self,
        name: str,
        *,
        valid: bool = True,
        value: Any | None = None,
        raise_exc: bool = False,
    ) -> None:
        super().__init__(name)
        self._valid = valid
        self._value = value
        self._raise = raise_exc

    async def validate(
        self, data: Any, field_name: str | None = None
    ) -> ValidationResult:  # type: ignore[override]
        if self._raise:
            raise RuntimeError("boom")
        val = self._value if self._value is not None else data
        res = ValidationResult(
            field_name=field_name, value=val, original_value=data, is_valid=self._valid
        )
        if not self._valid:
            res.add_error("bad")
        return res

    async def compile(self) -> None:  # type: ignore[override]
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_basic_sanitization(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = ValidationService()
    svc.logger = MagicMock()
    cfg = ValidationConfig(enable_sanitization=True, enable_xss_protection=True)
    # Force a noticeable elapsed time for performance calc, but keep threshold high to avoid warning
    monkeypatch.setattr(
        "acb.services.validation.service.time.perf_counter", lambda: 0.0
    )
    res = await svc.validate("<b>x</b>", schema=None, config=cfg)
    assert isinstance(res.value, str)
    # Expect at least the HTML tags removed warning
    assert any("HTML tags removed" in w for w in res.warnings)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_basic_limits_and_depth() -> None:
    svc = ValidationService()
    svc.logger = MagicMock()
    # Long string error
    cfg = ValidationConfig(max_string_length=3)
    res_len = await svc.validate("abcd", schema=None, config=cfg)
    assert not res_len.is_valid
    assert any("String too long" in e for e in res_len.errors)

    # Dict depth error
    cfg2 = ValidationConfig(max_dict_depth=1)
    res_depth = await svc.validate({"a": {"b": {"c": 1}}}, schema=None, config=cfg2)
    assert not res_depth.is_valid
    assert any("Dictionary too deep" in e for e in res_depth.errors)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_with_schema_and_sanitization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = ValidationService()
    svc.logger = MagicMock()
    cfg = ValidationConfig(enable_sanitization=True, enable_xss_protection=True)
    schema = _Schema("s", valid=True, value="<i>ok</i>")

    # Make duration large to exercise timing but set threshold 0 to trigger warning path
    # Use a monotonic increasing perf_counter for start/end timing
    t = {"v": 0.0}

    def _pc() -> float:
        t["v"] += 1.0
        return t["v"]

    monkeypatch.setattr("acb.services.validation.service.time.perf_counter", _pc)
    # Lower perf threshold to 0 to ensure a warning call occurs
    svc._performance_monitoring_enabled = True
    svc._performance_threshold_ms = 0.0

    res = await svc.validate("unused", schema=schema, config=cfg, field_name="field")
    assert res.is_valid
    assert res.field_name == "field"
    # Sanitization should remove tags and warn
    assert any("HTML tags removed" in w for w in res.warnings)
    # Logger.warning should be called due to perf threshold
    assert svc.logger.warning.called


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_with_schema_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = ValidationService()
    svc.logger = MagicMock()
    schema = _Schema("s", raise_exc=True)
    res = await svc.validate(
        "x", schema=schema, config=ValidationConfig(), field_name="f"
    )
    assert not res.is_valid
    assert any("Validation exception:" in e for e in res.errors)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_many_labels_and_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = ValidationService()
    svc.logger = MagicMock()
    schema = _Schema("s", valid=True)
    data = ["a", "b"]
    res_list = await svc.validate_many(data, schema=schema, config=ValidationConfig())
    assert len(res_list) == 2
    assert res_list[0].field_name == "item_0"
    assert res_list[1].field_name == "item_1"
