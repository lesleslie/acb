"""Unit tests for output contract and response validation."""

from __future__ import annotations

import pytest

from acb.services.validation._base import ValidationConfig
from acb.services.validation.output import (
    OutputContract,
    OutputType,
    OutputValidator,
    ResponseValidator,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_output_validator_dict_contract_and_types() -> None:
    ov = OutputValidator(ValidationConfig(strict_types=True, allow_extra_fields=False))
    contract = OutputContract(
        name="c1",
        output_type=OutputType.DICT,
        required_fields=["id", "name"],
        optional_fields=["extra"],
        field_types={"id": int, "name": str},
        allow_extra_fields=False,
        strict_types=True,
    )

    data_ok = {"id": 1, "name": "x"}
    res_ok = await ov.validate_output(data_ok, contract)
    assert res_ok.is_valid

    data_bad = {"id": "1", "name": 2, "oops": True}
    res_bad = await ov.validate_output(data_bad, contract)
    assert not res_bad.is_valid
    assert any("Missing" not in e for e in res_bad.errors)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_output_validator_list_scalar_and_custom() -> None:
    ov = OutputValidator(ValidationConfig())
    list_contract = OutputContract(
        name="l",
        output_type=OutputType.LIST,
        min_length=1,
        max_length=2,
    )
    res_list = await ov.validate_output([1, 2, 3], list_contract)
    assert not res_list.is_valid
    assert any("long" in e for e in res_list.errors)

    scalar_contract = OutputContract(
        name="s",
        output_type=OutputType.SCALAR,
        field_types={"value": int},
        strict_types=True,
        min_length=None,
        max_length=None,
    )
    res_scalar = await ov.validate_output("not-int", scalar_contract)
    assert not res_scalar.is_valid

    # custom validator
    custom_contract = OutputContract(
        name="cust",
        output_type=OutputType.CUSTOM,
        custom_validators=[lambda v: isinstance(v, dict) and v.get("ok") is True],
    )
    res_custom = await ov.validate_output({"ok": True}, custom_contract)
    assert res_custom.is_valid
    res_custom_bad = await ov.validate_output({"ok": False}, custom_contract)
    assert not res_custom_bad.is_valid


@pytest.mark.unit
@pytest.mark.asyncio
async def test_response_validator_basic_paths() -> None:
    rv = ResponseValidator(ValidationConfig())
    ok = await rv.validate_http_response(
        {"status": 200, "body": "x"}, expected_status_codes=[200]
    )
    assert ok.is_valid
    bad_status = await rv.validate_http_response(
        {"status": 500, "body": "x"}, expected_status_codes=[200]
    )
    assert not bad_status.is_valid
    missing_body = await rv.validate_http_response({"status": 200})
    assert not missing_body.is_valid
    hdrs_bad = await rv.validate_http_response(
        {"status": 200, "body": "x", "headers": []}
    )
    assert not hdrs_bad.is_valid

    # API error response
    er_ok = await rv.validate_api_error_response({"error": "x"})
    assert er_ok.is_valid
    er_bad = await rv.validate_api_error_response({})
    assert not er_bad.is_valid
