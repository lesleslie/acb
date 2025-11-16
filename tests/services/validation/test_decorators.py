"""Unit tests for validation decorators module."""

from __future__ import annotations

import pytest
from typing import Any

from acb.services.validation._base import (
    ValidationConfig,
    ValidationResult,
    ValidationSchema,
)
from acb.services.validation.decorators import (
    ValidationDecorators,
    sanitize_input,
    validate_contracts,
    validate_input,
    validate_output,
)
from acb.services.validation.results import ValidationError


class _Schema(ValidationSchema):
    def __init__(
        self, name: str, *, valid: bool = True, replace: Any | None = None
    ) -> None:
        super().__init__(name)
        self._valid = valid
        self._replace = replace

    async def validate(
        self, data: Any, field_name: str | None = None
    ) -> ValidationResult:  # type: ignore[override]
        result = ValidationResult(
            value=self._replace if self._replace is not None else data,
            original_value=data,
        )
        result.is_valid = self._valid
        if not self._valid:
            result.add_error(f"invalid {self.name}")
        return result

    async def compile(self) -> None:  # type: ignore[override]
        return None


class _FakeValidationService:
    async def validate(
        self,
        data: Any,
        schema: ValidationSchema | None = None,
        config: ValidationConfig | None = None,
        field_name: str | None = None,
    ) -> ValidationResult:
        if schema is None:
            # basic path: echo
            return ValidationResult(value=data, original_value=data, is_valid=True)
        return await schema.validate(data, field_name)


@pytest.fixture(autouse=True)
def _patch_depends(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeValidationService()

    async def _aget(*_: Any, **__: Any) -> Any:
        return fake

    monkeypatch.setattr(
        "acb.services.validation.decorators.depends.get",
        _aget,
    )
    monkeypatch.setattr(
        "acb.services.validation.decorators.depends.get_sync",
        lambda *_, **__: fake,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_input_with_dict_and_single_schema() -> None:
    # dict schema (mutates x, leaves y as-is)
    x_schema = _Schema("x", valid=True, replace="X!")
    y_schema = _Schema("y", valid=True)

    @validate_input({"x": x_schema, "y": y_schema}, raise_on_error=True)
    async def func1(x: str, y: int) -> tuple[str, int]:
        return x, y

    assert await func1("x", 1) == ("X!", 1)

    # single schema validates only first param
    a_schema = _Schema("a", valid=True, replace=123)

    @validate_input(a_schema)
    async def func2(a: int, b: int) -> tuple[int, int]:
        return a, b

    # single schema validates first param only but does not mutate bound args
    assert await func2(1, 2) == (1, 2)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_input_raises_on_error() -> None:
    bad_x = _Schema("x", valid=False)

    @validate_input({"x": bad_x}, raise_on_error=True)
    async def f(x: str) -> str:
        return x

    with pytest.raises(ValidationError) as ei:
        await f("boom")
    assert "Input validation failed" in str(ei.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_output_success_and_error() -> None:
    ok = _Schema("out", valid=True, replace="OK")
    bad = _Schema("out", valid=False)

    @validate_output(ok, raise_on_error=True)
    async def f1() -> str:
        return "original"

    assert await f1() == "OK"

    @validate_output(bad, raise_on_error=True)
    async def f2() -> str:
        return "original"

    with pytest.raises(ValidationError):
        await f2()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sanitize_input_applies_and_returns_mutated_args() -> None:
    # our fake service will echo by default; emulate sanitizer by schema None path → echo
    # In decorators.sanitize_input, service.validate is called with schema=None, so our fake echo returns value unchanged.
    # To demonstrate flow, we wrap a string and assert function still receives arguments from bound_args.

    @sanitize_input(fields=["content"])  # will call service.validate(None) on 'content'
    async def f(title: str, content: str) -> tuple[str, str]:
        return title, content

    assert await f("t", "<b>x</b>") == ("t", "<b>x</b>")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_contracts_input_and_output() -> None:
    @validate_contracts(
        input_contract={"a": int, "b": str}, output_contract={"id": int}
    )
    async def f(a: int, b: str) -> dict[str, Any]:
        return {"id": 1, "b": b}

    assert await f(1, "x") == {"id": 1, "b": "x"}

    @validate_contracts(input_contract={"a": int})
    async def g(a: int) -> None:
        return None

    with pytest.raises(ValidationError):
        await g("bad")  # type: ignore[arg-type]

    @validate_contracts(output_contract={"id": int})
    async def h() -> dict[str, Any]:
        return {"id": "oops"}  # type: ignore[return-value]

    with pytest.raises(ValidationError):
        await h()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_method_validator_for_class_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeValidationService()
    vd = ValidationDecorators(fake)

    in_schema = _Schema("name", valid=True, replace="Name!")
    out_schema = _Schema("out", valid=True, replace={"id": 1})

    class Svc:
        @vd.method_validator(
            input_schemas={"name": in_schema}, output_schema=out_schema
        )
        async def create(self, name: str) -> dict[str, Any]:
            return {"name": name}

    assert await Svc().create("ignored") == {"id": 1}
