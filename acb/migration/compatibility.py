"""Compatibility layers for deprecated interfaces."""

from __future__ import annotations

import warnings

from typing import TypeVar

from acb.depends import depends
from acb.logger import Logger as LoggerAdapter
from acb.migration._base import VersionInfo

logger = depends.get_sync(LoggerAdapter)

T = TypeVar("T")


class CompatibilityLayer:
    """Provides compatibility shims for deprecated interfaces.

    Example:
        >>> compat = CompatibilityLayer(current_version="0.20.0")
        >>> # Use old interface that redirects to new one
        >>> result = compat.old_method(*args, **kwargs)
    """

    def __init__(self, current_version: str | VersionInfo) -> None:
        """Initialize compatibility layer.

        Args:
            current_version: Current ACB version
        """
        if isinstance(current_version, str):
            self.version = VersionInfo.from_string(current_version)
        else:
            self.version = current_version

    def deprecated_config_location(
        self,
        old_path: str,
        new_path: str,
        removed_in: str,
    ) -> None:
        """Warn about deprecated configuration file location.

        Args:
            old_path: Old configuration path
            new_path: New configuration path
            removed_in: Version when support will be removed
        """
        warnings.warn(
            f"Configuration file '{old_path}' is deprecated. "
            f"Please move to '{new_path}'. "
            f"Support will be removed in version {removed_in}.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            f"Deprecated config location: {old_path} -> {new_path} "
            f"(removed in {removed_in})",
        )

    def deprecated_adapter_import(
        self,
        old_import: str,
        new_import: str,
        removed_in: str,
    ) -> None:
        """Warn about deprecated adapter import path.

        Args:
            old_import: Old import path
            new_import: New import path
            removed_in: Version when support will be removed
        """
        warnings.warn(
            f"Import path '{old_import}' is deprecated. "
            f"Please use '{new_import}' instead. "
            f"Support will be removed in version {removed_in}.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            f"Deprecated import: {old_import} -> {new_import} "
            f"(removed in {removed_in})",
        )

    def deprecated_method(
        self,
        old_method: str,
        new_method: str,
        removed_in: str,
    ) -> None:
        """Warn about deprecated method.

        Args:
            old_method: Old method name
            new_method: New method name
            removed_in: Version when support will be removed
        """
        warnings.warn(
            f"Method '{old_method}' is deprecated. "
            f"Please use '{new_method}' instead. "
            f"Support will be removed in version {removed_in}.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            f"Deprecated method: {old_method} -> {new_method} "
            f"(removed in {removed_in})",
        )

    def deprecated_parameter(
        self,
        parameter: str,
        replacement: str | None,
        removed_in: str,
    ) -> None:
        """Warn about deprecated parameter.

        Args:
            parameter: Deprecated parameter name
            replacement: Replacement parameter name (None if removed)
            removed_in: Version when support will be removed
        """
        if replacement:
            msg = (
                f"Parameter '{parameter}' is deprecated. "
                f"Please use '{replacement}' instead. "
                f"Support will be removed in version {removed_in}."
            )
        else:
            msg = (
                f"Parameter '{parameter}' is deprecated and will be ignored. "
                f"Support will be removed in version {removed_in}."
            )

        warnings.warn(msg, DeprecationWarning, stacklevel=2)
        logger.warning(
            f"Deprecated parameter: {parameter} "
            f"-> {replacement or 'removed'} (removed in {removed_in})",
        )


# Version-specific compatibility layers


class V018CompatibilityLayer(CompatibilityLayer):
    """Compatibility layer for ACB 0.18.x -> 0.19.x migration."""

    def __init__(self) -> None:
        super().__init__("0.19.0")

    def old_config_class_pattern(self) -> None:
        """Warn about deprecated Pydantic Config class pattern."""
        self.deprecated_method(
            old_method="class Config: extra = 'forbid'",
            new_method="model_config = ConfigDict(extra='forbid')",
            removed_in="0.20.0",
        )

    def old_cache_interface(self, method: str) -> None:
        """Warn about deprecated cache interface methods.

        Args:
            method: Deprecated method name
        """
        if method == "get_or_set":
            self.deprecated_method(
                old_method="cache.get_or_set()",
                new_method="cache.get() or cache.set()",
                removed_in="0.20.0",
            )
        elif method == "get_many":
            self.deprecated_method(
                old_method="cache.get_many()",
                new_method="cache.multi_get()",
                removed_in="0.20.0",
            )

    def old_config_location(self, filename: str) -> None:
        """Warn about deprecated config file locations.

        Args:
            filename: Configuration filename
        """
        mapping = {
            "config.yaml": "settings/app.yaml",
            "debug.yaml": "settings/debug.yaml",
            ".env": "settings/secrets/.env",
        }

        if filename in mapping:
            self.deprecated_config_location(
                old_path=filename,
                new_path=mapping[filename],
                removed_in="0.20.0",
            )


class V019CompatibilityLayer(CompatibilityLayer):
    """Compatibility layer for ACB 0.19.x -> 0.20.x migration."""

    def __init__(self) -> None:
        super().__init__("0.20.0")

    def old_adapter_pattern(self, adapter: str) -> None:
        """Warn about deprecated adapter patterns.

        Args:
            adapter: Adapter name
        """
        # Placeholder for future deprecations
        logger.debug(f"Checking compatibility for adapter: {adapter}")


# Registry of compatibility layers by version
_COMPATIBILITY_LAYERS: dict[str, type[CompatibilityLayer]] = {
    "0.18": V018CompatibilityLayer,
    "0.19": V019CompatibilityLayer,
}


def get_compatibility_layer(version: str | VersionInfo) -> CompatibilityLayer:
    """Get compatibility layer for specific version.

    Args:
        version: ACB version

    Returns:
        Compatibility layer instance

    Example:
        >>> compat = get_compatibility_layer("0.18.0")
        >>> compat.old_config_class_pattern()  # Emits deprecation warning
    """
    if isinstance(version, str):
        version_info = VersionInfo.from_string(version)
    else:
        version_info = version

    # Get major.minor version key
    version_key = f"{version_info.major}.{version_info.minor}"

    # Try to get specific compatibility layer
    layer_class = _COMPATIBILITY_LAYERS.get(version_key)

    if layer_class:
        return layer_class(version_info)

    # Fallback to generic compatibility layer
    logger.debug(f"No specific compatibility layer for {version_key}, using generic")
    return CompatibilityLayer(version_info)


def register_compatibility_layer(
    version: str,
    layer_class: type[CompatibilityLayer],
) -> None:
    """Register custom compatibility layer for specific version.

    Args:
        version: Version string (e.g., "0.20")
        layer_class: Compatibility layer class
    """
    _COMPATIBILITY_LAYERS[version] = layer_class
    logger.debug(f"Registered compatibility layer for version {version}")
