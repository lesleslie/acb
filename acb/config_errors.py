"""Common error types and error handling utilities for ACB configuration system.

This module defines shared exception classes and error handling patterns
to reduce duplication across the configuration system.
"""

from typing import Any


class ConfigError(Exception):
    """Base exception for configuration-related errors."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        config_section: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.config_section = config_section


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""


class ConfigFieldError(ConfigError):
    """Raised when there are issues with specific configuration fields."""

    def __init__(
        self,
        field_name: str,
        field_type: str | type,
        actual_type: str | type | None = None,
        message: str | None = None,
    ) -> None:
        self.field_name = field_name
        self.field_type = field_type
        self.actual_type = actual_type

        if message:
            error_msg = message
        elif actual_type:
            error_msg = f"Field '{field_name}' must be {field_type}, got {actual_type}"
        else:
            error_msg = f"Field '{field_name}' has incorrect type {field_type}"

        super().__init__(error_msg, field_name=field_name)


class ConfigPathError(ConfigError):
    """Raised when there are issues with configuration paths."""

    def __init__(self, path: str | object, message: str | None = None) -> None:
        self.path = path
        error_msg = message or f"Invalid configuration path: {path}"
        super().__init__(error_msg)


class ConfigValueError(ConfigError):
    """Raised when configuration values are invalid."""

    def __init__(self, field_name: str, value: Any, message: str | None = None) -> None:
        self.field_name = field_name
        self.value = value

        error_msg = message or f"Invalid value for '{field_name}': {value}"

        super().__init__(error_msg)


class ConfigMissingError(ConfigError):
    """Raised when required configuration is missing."""

    def __init__(self, field_name: str, context: str | None = None) -> None:
        self.field_name = field_name
        if context:
            error_msg = f"Required configuration '{field_name}' is missing in {context}"
        else:
            error_msg = f"Required configuration '{field_name}' is missing"

        super().__init__(error_msg, field_name=field_name)


def raise_field_error(
    field_name: str,
    expected_type: str | type,
    actual_value: Any,
) -> None:
    """Raise a standardized field error with consistent messaging."""
    actual_type = type(actual_value).__name__ if actual_value is not None else "None"
    raise ConfigFieldError(field_name, expected_type, actual_type)


def raise_missing_config_error(field_name: str, context: str | None = None) -> None:
    """Raise a standardized missing configuration error."""
    raise ConfigMissingError(field_name, context)


def raise_path_error(path: str, operation: str = "access") -> None:
    """Raise a standardized path error with consistent messaging."""
    raise ConfigPathError(path, f"Failed to {operation} path: {path}")


def validate_path_field(obj: object, field_name: str) -> None:
    """Validate that a field is a Path instance, raising a standard error if not."""
    from pathlib import Path

    if not hasattr(obj, field_name):
        raise ConfigMissingError(field_name, context=obj.__class__.__name__)

    value = getattr(obj, field_name)
    if not isinstance(value, Path):
        raise_field_error(field_name, "Path", value)


def validate_field_exists(
    obj: object,
    field_name: str,
    expected_type: type | None = None,
) -> Any:
    """Validate that a field exists and optionally check its type."""
    if not hasattr(obj, field_name):
        raise ConfigMissingError(field_name, context=obj.__class__.__name__)

    value = getattr(obj, field_name)

    if expected_type and not isinstance(value, expected_type):
        raise_field_error(field_name, expected_type.__name__, value)

    return value
