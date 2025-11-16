from __future__ import annotations

import re

import pytest

from acb.validation import (
    ValidationMixin,
    create_length_validator,
    create_pattern_validator,
)


class TestValidationMixin:
    def test_required_field(self) -> None:
        ValidationMixin.validate_required_field("api_key", "value")
        with pytest.raises(ValueError):
            ValidationMixin.validate_required_field("api_key", "")

    def test_min_length(self) -> None:
        ValidationMixin.validate_min_length("name", "abcd", 3)
        with pytest.raises(ValueError):
            ValidationMixin.validate_min_length("name", "ab", 3)

    def test_url_parts(self) -> None:
        ValidationMixin.validate_url_parts("localhost", port=8080)
        with pytest.raises(ValueError):
            ValidationMixin.validate_url_parts("", port=8080)
        with pytest.raises(ValueError):
            ValidationMixin.validate_url_parts("localhost", port=70000)

    def test_one_of_required(self) -> None:
        ValidationMixin.validate_one_of_required(["a", "b"], [None, "x"])
        with pytest.raises(ValueError):
            ValidationMixin.validate_one_of_required(["a", "b"], [None, None])


class TestValidatorFactories:
    def test_pattern_validator(self) -> None:
        validator = create_pattern_validator(re.compile(r"^sk-\w+$"))
        assert validator("sk-abc") == "sk-abc"
        with pytest.raises(ValueError):
            validator("nope")

    def test_pattern_validator_non_string(self) -> None:
        validator = create_pattern_validator(re.compile(r"^sk-\w+$"))
        with pytest.raises(ValueError, match="Expected string"):
            validator(123)  # type: ignore[arg-type]

    def test_length_validator(self) -> None:
        validator = create_length_validator(2, 4)
        assert validator("abc") == "abc"
        with pytest.raises(ValueError):
            validator("a")
        with pytest.raises(ValueError):
            validator("abcde")

    def test_length_validator_non_string(self) -> None:
        validator = create_length_validator(2, 4)
        with pytest.raises(ValueError, match="Expected string"):
            validator(123)  # type: ignore[arg-type]
