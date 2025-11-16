"""Additional unit tests for validation utilities to improve coverage."""

from __future__ import annotations

import asyncio
import pytest
from typing import Any

from acb.services.validation._base import (
    ValidationConfig,
    ValidationLevel,
    ValidationResult,
    ValidationSchema,
)
from acb.services.validation.utils import (
    SchemaValidator,
    ValidationCache,
    ValidationHelper,
    ValidationTimer,
    benchmark_validation,
    combine_validation_results,
    create_validation_config_from_dict,
    create_validation_result,
    get_validation_summary,
    inspect_function_parameters,
)


class _DummySchema(ValidationSchema):
    def __init__(
        self, name: str, valid: bool = True, warnings: int = 0, delay_ms: float = 0.0
    ) -> None:
        super().__init__(name)
        self._valid = valid
        self._warnings = warnings
        self._delay_ms = delay_ms

    async def validate(self, data: Any) -> ValidationResult:
        if self._delay_ms:
            await asyncio.sleep(self._delay_ms / 1000.0)
        result = ValidationResult(is_valid=self._valid, value=data, original_value=data)
        for i in range(self._warnings):
            result.add_warning(f"w{i}")
        return result

    async def compile(self) -> None:  # no-op
        await asyncio.sleep(0)


@pytest.mark.unit
def test_validation_timer_start_stop_and_elapsed() -> None:
    timer = ValidationTimer()
    # stop before start should raise
    with pytest.raises(RuntimeError):
        timer.stop()
    timer.start()
    # elapsed should be >= 0
    assert timer.elapsed_ms >= 0.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validation_timer_context_manager() -> None:
    timer = ValidationTimer()
    async with timer.time_operation() as t:
        assert isinstance(t.elapsed_ms, float)
    # after context manager, elapsed should still be accessible
    assert timer.elapsed_ms >= 0.0


@pytest.mark.unit
def test_create_and_combine_validation_results() -> None:
    r1 = create_validation_result(
        value=1, field_name="a", is_valid=True, warnings=["w"]
    )  # type: ignore[arg-type]
    r2 = create_validation_result(value=2, field_name="b", is_valid=False, errors=["e"])  # type: ignore[arg-type]
    combined = combine_validation_results([r1, r2], field_name="combo")
    assert combined.field_name == "combo"
    assert combined.is_valid is False
    assert len(combined.errors) == 1
    assert len(combined.warnings) == 1


@pytest.mark.unit
def test_is_validation_result_successful_levels() -> None:
    ok = create_validation_result(value=1, is_valid=True)
    ok_with_warning = create_validation_result(value=1, is_valid=True, warnings=["w"])  # type: ignore[arg-type]
    bad = create_validation_result(value=1, is_valid=False, errors=["e"])  # type: ignore[arg-type]

    # STRICT requires valid and no errors
    assert (
        inspect_result := (ok.is_valid and not ok.has_errors())
    ) and inspect_result  # sanity check
    from acb.services.validation.utils import is_validation_result_successful

    assert is_validation_result_successful(ok, ValidationLevel.STRICT) is True
    assert (
        is_validation_result_successful(ok_with_warning, ValidationLevel.STRICT) is True
    )
    assert is_validation_result_successful(bad, ValidationLevel.STRICT) is False

    # LENIENT allows warnings but no errors
    assert (
        is_validation_result_successful(ok_with_warning, ValidationLevel.LENIENT)
        is True
    )
    assert is_validation_result_successful(bad, ValidationLevel.LENIENT) is False

    # PERMISSIVE always passes
    assert is_validation_result_successful(bad, ValidationLevel.PERMISSIVE) is True


@pytest.mark.unit
def test_get_validation_summary_empty_and_nonempty() -> None:
    empty = get_validation_summary([])
    assert empty["total_validations"] == 0
    r_ok = create_validation_result(value="x", is_valid=True, validation_time_ms=2.0)
    r_bad = create_validation_result(
        value="y", is_valid=False, errors=["e"], validation_time_ms=4.0
    )  # type: ignore[arg-type]
    summary = get_validation_summary([r_ok, r_bad])
    assert summary["total_validations"] == 2
    assert summary["successful_validations"] == 1
    assert summary["failed_validations"] == 1
    assert summary["total_errors"] == 1
    assert 2.9 < summary["average_time_ms"] < 3.1


@pytest.mark.unit
def test_validation_helper_utilities() -> None:
    h = ValidationHelper()
    assert h.is_empty(None)
    assert h.is_empty("")
    assert not h.is_empty("x")
    assert h.is_numeric(1)
    assert h.is_numeric(1.0)
    assert not h.is_numeric("1")
    assert h.is_string_like(b"b") and h.is_string_like("s")
    assert h.is_iterable([1, 2, 3]) and not h.is_iterable("str")

    data: dict[str, Any] = {"a": {"b": {"c": 1}}}
    assert h.get_nested_value(data, "a.b.c") == 1
    assert h.get_nested_value(data, "a.x", default=42) == 42
    h.set_nested_value(data, "a.b.d", 2)
    assert data["a"]["b"]["d"] == 2
    flat = h.flatten_dict({"a": {"b": 1}, "c": 2})
    assert flat == {"a.b": 1, "c": 2}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schema_validator_multiple_and_best_match() -> None:
    s_ok = _DummySchema("ok", valid=True, warnings=0, delay_ms=0)
    s_warn = _DummySchema("warn", valid=True, warnings=2, delay_ms=0)
    s_bad = _DummySchema("bad", valid=False)

    sv = SchemaValidator(ValidationConfig())

    results = await sv.validate_against_multiple_schemas(
        {"x": 1}, [s_bad, s_ok, s_warn]
    )
    assert len(results) == 3
    assert results[1].is_valid is True

    # require_all_pass False should short-circuit on first valid
    results_short = await sv.validate_against_multiple_schemas(
        {"x": 1}, [s_bad, s_ok, s_warn], require_all_pass=False
    )
    assert len(results_short) == 2  # stops when s_ok passes

    best_schema, best_result = await sv.find_best_matching_schema(
        {"x": 1}, [s_warn, s_ok]
    )
    assert best_schema is s_ok and best_result is not None and best_result.is_valid


@pytest.mark.unit
def test_validation_cache_basic_and_expiry() -> None:
    cache = ValidationCache(max_size=3, ttl_seconds=-1)  # immediate expiry
    r = create_validation_result(value=1)
    cache.set({"x": 1}, r, schema_name="s")
    # immediately expired due to ttl=-1
    assert cache.get({"x": 1}, schema_name="s") is None

    # size/count and clear
    cache = ValidationCache(max_size=2, ttl_seconds=3600)
    cache.set(1, r)
    cache.set(2, r)
    assert cache.size() == 2
    cache.clear()
    assert cache.size() == 0


@pytest.mark.unit
def test_inspect_function_parameters() -> None:
    def sample(a: int, b: str = "x", *args: Any, **kwargs: Any) -> bool:
        return True

    info = inspect_function_parameters(sample)
    params = info["parameters"]
    # Annotations may be stringified depending on from __future__ import annotations
    ann = params["a"]["annotation"]
    assert ann is int or str(ann).endswith("int")
    assert params["b"]["has_default"] is True
    ret_ann = info["return_annotation"]
    assert ret_ann is bool or str(ret_ann).endswith("bool")
    assert info["is_async"] is False


@pytest.mark.unit
def test_create_validation_config_from_dict() -> None:
    cfg = create_validation_config_from_dict({"level": "lenient"})
    assert cfg.level is ValidationLevel.LENIENT
    cfg2 = create_validation_config_from_dict({"level": "unknown"})
    assert cfg2.level is ValidationLevel.STRICT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_benchmark_validation_smoke() -> None:
    async def validate_ok(_: Any) -> ValidationResult:
        return create_validation_result(value=True)

    result = await benchmark_validation(validate_ok, [1, 2], iterations=2)
    # basic keys exist and counts add up
    assert result["total_validations"] == 4
    assert all(
        k in result
        for k in (
            "min_time_ms",
            "max_time_ms",
            "avg_time_ms",
            "median_time_ms",
            "p95_time_ms",
            "p99_time_ms",
        )
    )
