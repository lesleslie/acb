"""Unit tests for services.validation._base helpers."""

from __future__ import annotations

import asyncio
import pytest
from typing import Any

from acb.services.validation._base import (
    ValidationMetrics,
    ValidationRegistry,
    ValidationResult,
    ValidationSchema,
)


class _EchoSchema(ValidationSchema):
    async def validate(self, data: Any) -> ValidationResult:
        # simply echo data as valid
        return ValidationResult(is_valid=True, value=data, original_value=data)

    async def compile(self) -> None:
        # no-op compile to satisfy abstract interface
        await asyncio.sleep(0)


@pytest.mark.unit
def test_validation_result_mutators() -> None:
    vr = ValidationResult(field_name="f")
    assert not vr.has_errors()
    assert not vr.has_warnings()
    vr.add_warning("careful")
    assert vr.has_warnings()
    vr.add_error("nope")
    assert vr.has_errors()
    assert vr.is_valid is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validation_schema_compile_and_flags() -> None:
    schema = _EchoSchema("s1")
    assert schema.is_compiled is False
    await schema._ensure_compiled()
    assert schema.is_compiled is True
    # compile_time_ms should be a float
    assert isinstance(schema.compile_time_ms, float) or schema.compile_time_ms is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validation_registry_register_compile_list_remove_clear() -> None:
    reg = ValidationRegistry()
    s1 = _EchoSchema("schema1")
    s2 = _EchoSchema("schema2")
    reg.register(s1)
    reg.register(s2)
    assert set(reg.list_schemas()) == {"schema1", "schema2"}

    # get_schema
    assert reg.get_schema("schema1") is s1
    assert reg.get_schema("missing") is None

    # compiled retrieval compiles on-demand
    compiled = await reg.get_compiled_schema("schema1")
    assert compiled is not None and compiled.is_compiled

    # remove and clear
    reg.remove_schema("schema1")
    assert "schema1" not in reg.list_schemas()
    reg.clear()
    assert reg.list_schemas() == []


@pytest.mark.unit
def test_validation_metrics_flow() -> None:
    m = ValidationMetrics()
    # no operations
    assert m.success_rate == 0.0
    assert m.cache_hit_rate == 0.0

    # record successes/misses
    m.record_validation(success=True, validation_time_ms=2.0, cache_hit=True)
    m.record_validation(success=False, validation_time_ms=5.0, cache_hit=False)
    assert m.total_validations == 2
    assert m.successful_validations == 1
    assert m.failed_validations == 1
    assert m.max_validation_time_ms == 5.0
    # hit rate is 1/2
    assert 0.49 < m.cache_hit_rate < 0.51
    # success rate is 1/2
    assert 0.49 < m.success_rate < 0.51
    d = m.to_dict()
    assert d["total_validations"] == 2
    assert "average_validation_time_ms" in d
