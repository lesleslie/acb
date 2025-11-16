"""Validation helpers for Pydantic models and ACB Settings.

Provides a ValidationMixin and small validator factories to keep models tidy.
This module intentionally focuses on model/Settings integration rather than
pure value checks (which live under acb.actions.validate).
"""

from __future__ import annotations

import re

import typing as t

T = t.TypeVar("T")


class ValidationMixin:
    """Reusable validation methods for Settings and Pydantic models.

    Includes common validation patterns:
    - Required field validation (non-empty strings)
    - Minimum length validation
    - Simple host/port checks
    - Composite one-of-required validation
    """

    @staticmethod
    def validate_required_field(
        field_name: str,
        value: str | None,
        *,
        context: str | None = None,
    ) -> None:
        if not value or not value.strip():
            prefix = f"{context} " if context else ""
            msg = f"{prefix}{field_name} is not set in configuration"
            raise ValueError(msg)

    @staticmethod
    def validate_min_length(
        field_name: str,
        value: str,
        min_length: int,
        *,
        context: str | None = None,
    ) -> None:
        if len(value) < min_length:
            prefix = f"{context} " if context else ""
            msg = (
                f"{prefix}{field_name} is too short. "
                f"Required: {min_length} characters, got: {len(value)}"
            )
            raise ValueError(msg)

    @staticmethod
    def validate_url_parts(
        host: str | None,
        *,
        port: int | None = None,
        context: str | None = None,
    ) -> None:
        if not host or not host.strip():
            prefix = f"{context} " if context else ""
            msg = f"{prefix}host is not set in configuration"
            raise ValueError(msg)
        if port is not None and (not isinstance(port, int) or port < 1 or port > 65535):
            prefix = f"{context} " if context else ""
            msg = f"{prefix}port must be between 1 and 65535, got: {port}"
            raise ValueError(msg)

    @staticmethod
    def validate_one_of_required(
        field_names: list[str],
        values: list[t.Any],
        *,
        context: str | None = None,
    ) -> None:
        if len(field_names) != len(values):
            raise ValueError("field_names and values must have same length")
        has_value = any(v is not None and str(v).strip() for v in values)
        if not has_value:
            prefix = f"{context}: " if context else ""
            fields = ", ".join(field_names)
            msg = f"{prefix}At least one of [{fields}] is required"
            raise ValueError(msg)


def create_pattern_validator(pattern: str | re.Pattern[str]) -> t.Callable[[str], str]:
    r"""Return a Pydantic field validator enforcing a regex pattern.

    Example:
        _validate_api_key = field_validator("api_key")(create_pattern_validator(r"^sk-\w+$"))
    """
    regex = (
        re.compile(pattern) if isinstance(pattern, str) else pattern
    )  # REGEX OK: Dynamic pattern validator - caller provides pattern, used for field validation

    def _validate(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Expected string")
        if not regex.match(value):  # REGEX OK: Using pre-compiled pattern from above
            raise ValueError("Value does not match required pattern")
        return value

    return _validate


def create_length_validator(
    min_length: int | None = None,
    max_length: int | None = None,
) -> t.Callable[[str], str]:
    """Return a Pydantic field validator enforcing length boundaries."""

    def _validate(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Expected string")
        if min_length is not None and len(value) < min_length:
            raise ValueError(f"Minimum length is {min_length}")
        if max_length is not None and len(value) > max_length:
            raise ValueError(f"Maximum length is {max_length}")
        return value

    return _validate
