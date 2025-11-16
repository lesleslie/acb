"""Shared discovery logic for events, services, and test providers.

This module provides common discovery patterns to eliminate code duplication
across the three discovery systems and reduce cognitive complexity.
"""

import inspect
from pathlib import Path

import typing as t
from typing import Protocol


class RegistryDescriptor(Protocol):
    """Protocol for registry descriptors (Service, TestProvider, EventHandlerDescriptor)."""

    name: str
    category: str
    enabled: bool


class RegistryConfig:
    """Configuration for registry-based import systems.

    Attributes:
        get_descriptor: Function to get descriptor by category
        try_import: Function to try importing by category and optional name
        get_all_descriptors: Function to get all available descriptors
        not_found_exception: Exception type to raise when not found
    """

    def __init__(
        self,
        get_descriptor: t.Callable[[str], t.Any] | None = None,
        try_import: t.Callable[[str, str | None], type[t.Any] | None] | None = None,
        get_all_descriptors: t.Callable[[], list[t.Any]] | None = None,
        not_found_exception: type[Exception] | None = None,
    ) -> None:
        """Initialize registry configuration.

        Args:
            get_descriptor: Function to get descriptor by category
            try_import: Function to try importing by category and optional name
            get_all_descriptors: Function to get all available descriptors
            not_found_exception: Exception type to raise when not found
        """
        self._get_descriptor = get_descriptor
        self._try_import = try_import
        self._get_all_descriptors = get_all_descriptors
        self._not_found_exception = not_found_exception or Exception

    def get_descriptor(self, category: str) -> t.Any:
        """Get descriptor by category."""
        if self._get_descriptor is None:
            msg = "get_descriptor not configured"
            raise RuntimeError(msg)
        return self._get_descriptor(category)

    def try_import(
        self,
        category: str,
        name: str | None = None,
    ) -> type[t.Any] | None:
        """Try importing by category and optional name."""
        if self._try_import is None:
            msg = "try_import not configured"
            raise RuntimeError(msg)
        return self._try_import(category, name)

    def get_all_descriptors(self) -> list[t.Any]:
        """Get all available descriptors."""
        if self._get_all_descriptors is None:
            msg = "get_all_descriptors not configured"
            raise RuntimeError(msg)
        return self._get_all_descriptors()

    @property
    def not_found_exception(self) -> type[Exception]:
        """Get the not found exception type."""
        return self._not_found_exception


def _import_single_category(
    category: str,
    config: RegistryConfig,
) -> type[t.Any]:
    """Import a single category from registry.

    Args:
        category: Category to import
        config: Registry configuration

    Returns:
        Imported class

    Raises:
        config.not_found_exception: If category not found or not enabled

    Complexity: 3
    """
    descriptor = config.get_descriptor(category)
    if not descriptor:
        raise config.not_found_exception(
            f"Not found or not enabled: {category}",
        )

    result = config.try_import(category, descriptor.name)
    if result is None:
        raise config.not_found_exception(
            f"Not found or not enabled: {category}",
        )
    return result


def _import_multiple_categories(
    categories: list[str],
    config: RegistryConfig,
) -> tuple[type[t.Any], ...] | type[t.Any]:
    """Import multiple categories from registry.

    Args:
        categories: List of categories to import
        config: Registry configuration

    Returns:
        Tuple of classes or single class if only one category

    Raises:
        config.not_found_exception: If any category not found

    Complexity: 4
    """
    results = []
    for category in categories:
        result = config.try_import(category)
        if not result:
            raise config.not_found_exception(
                f"Not found or not enabled: {category}",
            )
        results.append(result)

    return tuple(results) if len(results) > 1 else results[0]


def _extract_variable_name(frame: t.Any) -> str | None:
    """Extract variable name from frame safely.

    Args:
        frame: Inspection frame

    Returns:
        Variable name or None

    Complexity: 5
    """
    if not frame or not frame.f_back:
        return None

    try:
        filename = frame.f_back.f_code.co_filename
        line_number = frame.f_back.f_lineno

        if not Path(filename).exists():
            return None

        with open(filename) as f:
            lines = f.readlines()
            if line_number > len(lines):
                return None

            line = lines[line_number - 1].strip()
            if "=" not in line:
                return None

            return line.split("=")[0].strip().lower()

    except (OSError, IndexError, AttributeError):
        return None


def _match_variable_to_category(
    var_name: str,
    descriptors: list[t.Any],
) -> str | None:
    """Match variable name to registry category.

    Args:
        var_name: Variable name from source
        descriptors: Available descriptors

    Returns:
        Matched category or None

    Complexity: 3
    """
    for descriptor in descriptors:
        if descriptor.category in var_name or descriptor.name in var_name:
            return descriptor.category
    return None


def _auto_detect_from_context(config: RegistryConfig) -> type[t.Any]:
    """Auto-detect category from calling context.

    Args:
        config: Registry configuration

    Returns:
        Imported class

    Raises:
        ValueError: If category cannot be determined
        config.not_found_exception: If determined category not available

    Complexity: 6
    """
    frame = inspect.currentframe()
    var_name = _extract_variable_name(frame)

    if not var_name:
        msg = "Could not determine category from context"
        raise ValueError(msg)

    descriptors = config.get_all_descriptors()
    category = _match_variable_to_category(var_name, descriptors)

    if not category:
        msg = "Could not determine category from context"
        raise ValueError(msg)

    result = config.try_import(category)
    if not result:
        raise config.not_found_exception(
            f"Not found or not enabled: {category}",
        )
    return result


def import_from_registry(
    categories: str | list[str] | None,
    config: RegistryConfig,
) -> t.Any:
    """Import from registry with unified logic.

    This function provides the core import logic shared across all discovery
    systems (events, services, testing). It handles:
    - Single category import
    - Multiple category import
    - Auto-detection from calling context

    Args:
        categories: Category, list of categories, or None for auto-detect
        config: Registry configuration defining behavior

    Returns:
        Class or tuple of classes depending on input

    Raises:
        ValueError: If invalid type or cannot auto-detect
        config.not_found_exception: If category not found or not enabled

    Complexity: 5
    """
    if isinstance(categories, str):
        return _import_single_category(categories, config)

    if categories is None:
        return _auto_detect_from_context(config)

    # Must be list[str] at this point based on type annotation
    if not isinstance(categories, list):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = f"Invalid categories type: {type(categories)}"
        raise ValueError(msg)

    return _import_multiple_categories(categories, config)
