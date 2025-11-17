"""Unit tests for validation results and utilities."""

from __future__ import annotations

import pytest

from acb.services.validation._base import ValidationResult
from acb.services.validation.results import (
    ValidationError,
    ValidationReport,
    ValidationResultBuilder,
)
from acb.services.validation.utils import (
    ValidationCache,
    ValidationHelper,
    ValidationTimer,
    combine_validation_results,
    create_validation_config_from_dict,
    create_validation_result,
    inspect_function_parameters,
)


@pytest.mark.unit
def test_validation_report_and_builder() -> None:
    r1 = ValidationResult(field_name="a", is_valid=True, value=1, original_value=1)
    r2 = ValidationResult(field_name="b", is_valid=False, value=2, original_value=2)
    r2.errors.append("bad")
    r2.warnings.append("warn")
    r1.validation_time_ms = 5.0
    r2.validation_time_ms = 7.0

    rep = ValidationReport(results=[r1, r2])
    assert rep.is_valid is False
    assert rep.has_errors is True
    assert rep.has_warnings is True
    assert rep.error_count == 1
    assert rep.warning_count == 1
    assert rep.average_validation_time_ms == pytest.approx(6.0)
    assert rep.max_validation_time_ms == 7.0
    assert rep.get_errors_by_field()["b"] == ["bad"]

    summary = rep.to_summary()
    assert "FAILED" in summary
    assert "Errors:" in summary

    # builder
    b = ValidationResultBuilder()
    b.add_result(r1).add_result(r2)
    built = b.build()
    assert built.error_count == 1
    with pytest.raises(ValidationError):
        b.build_and_raise_on_error()


@pytest.mark.unit
def test_utils_timer_and_create_and_combine_and_config() -> None:
    t = ValidationTimer()
    with pytest.raises(RuntimeError):
        t.stop()
    t.start()
    assert t.elapsed_ms >= 0.0
    assert t.stop() >= 0.0

    r = create_validation_result(
        value="x", field_name="f", is_valid=False, errors=["e"]
    )
    assert r.field_name == "f" and not r.is_valid and r.errors == ["e"]

    r2 = create_validation_result(value="y")
    combo = combine_validation_results([r, r2], field_name="combo")
    assert (
        combo.field_name == "combo" and combo.is_valid is False and "e" in combo.errors
    )

    cfg = create_validation_config_from_dict({"level": "lenient"})
    assert cfg.level.name == "LENIENT"


@pytest.mark.unit
def test_utils_helpers_and_cache() -> None:
    H = ValidationHelper
    assert H.is_empty(None)
    assert H.is_empty("")
    assert H.is_string_like("x") and not H.is_string_like(1)
    assert H.is_numeric(3.14) and not H.is_numeric("1")
    assert H.is_iterable([1, 2]) and not H.is_iterable("s")

    data = {"a": {"b": 1}}
    assert H.get_nested_value(data, "a.b") == 1
    H.set_nested_value(data, "a.c", 2)
    assert data["a"]["c"] == 2
    flat = H.flatten_dict({"a": {"b": 1, "c": 2}})
    assert flat == {"a.b": 1, "a.c": 2}

    # Cache
    cache = ValidationCache(max_size=2, ttl_seconds=3600)
    res = create_validation_result(value=1)
    cache.set({"x": 1}, res, schema_name="s")
    assert cache.get({"x": 1}, schema_name="s") is res
    assert cache.size() == 1
    cache.clear()
    assert cache.size() == 0


@pytest.mark.unit
def test_inspect_function_parameters() -> None:
    async def f(a: int, b: str = "x") -> int:
        return 1

    info = inspect_function_parameters(f)
    assert info["is_async"] is True
    params = info["parameters"]
    ann = params["a"]["annotation"]
    assert ann is int or ann == "int"
    assert params["b"]["has_default"] is True
