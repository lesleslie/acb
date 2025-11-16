"""Unit tests for validation helpers and mixin."""

from __future__ import annotations

import re

import pytest

from acb.validation import (
    ValidationMixin,
    create_length_validator,
    create_pattern_validator,
)


@pytest.mark.unit
def test_validate_required_field_and_min_length() -> None:
    vm = ValidationMixin()

    # required field
    with pytest.raises(ValueError) as ei:
        vm.validate_required_field("api_key", "   ", context="Config")
    assert "Config api_key is not set" in str(ei.value)

    # min length
    with pytest.raises(ValueError) as ei2:
        vm.validate_min_length("token", "abc", 5)
    assert "token is too short" in str(ei2.value)


@pytest.mark.unit
def test_validate_url_parts() -> None:
    vm = ValidationMixin()

    # missing host
    with pytest.raises(ValueError):
        vm.validate_url_parts("", port=None, context="Service")

    # invalid port
    with pytest.raises(ValueError):
        vm.validate_url_parts("example.com", port=70000)

    # ok
    vm.validate_url_parts("example.com", port=443)


@pytest.mark.unit
def test_validate_one_of_required() -> None:
    vm = ValidationMixin()

    with pytest.raises(ValueError):
        vm.validate_one_of_required(["a", "b"], [" ", None], context="Auth")

    # mismatch lengths
    with pytest.raises(ValueError):
        vm.validate_one_of_required(["a"], ["x", "y"])

    # ok when one is present
    vm.validate_one_of_required(["a", "b"], ["x", None])


@pytest.mark.unit
def test_create_pattern_validator_and_length_validator() -> None:
    pat = create_pattern_validator(re.compile(r"^sk-\w+$"))
    with pytest.raises(ValueError):
        pat("bad")
    assert pat("sk-abc123") == "sk-abc123"

    lv = create_length_validator(2, 5)
    with pytest.raises(ValueError):
        lv("x")
    with pytest.raises(ValueError):
        lv("toolong")
    assert lv("just") == "just"
