import typing as t
from contextlib import suppress
from functools import lru_cache

from bevy import auto_inject, get_container, injectable


@t.runtime_checkable
class DependsProtocol(t.Protocol):
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]: ...
    @staticmethod
    def set(class_: t.Any, instance: t.Any = None) -> t.Any: ...
    @staticmethod
    def get(category: t.Any) -> t.Any: ...
    @staticmethod
    async def get_async(category: t.Any) -> t.Any: ...
    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any: ...


class Depends:
    """Dependency injection manager for ACB.

    This class provides a clean interface for dependency injection without
    relying on fragile runtime introspection or blocking async calls.
    """

    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        """Decorator to inject dependencies into a function."""
        return t.cast("t.Callable[..., t.Any]", auto_inject(func))

    @staticmethod
    def set(class_: t.Any, instance: t.Any = None) -> t.Any:
        """Register a class/instance in the dependency container."""
        if instance is None:
            return get_container().add(class_, class_())
        return get_container().add(class_, instance)

    @staticmethod
    def get(category: t.Any) -> t.Any:
        """Get dependency instance by category or class.

        Args:
            category: The dependency category (string) or class to retrieve

        Returns:
            The dependency instance

        Note:
            For adapter dependencies that require async initialization,
            use get_async() instead.
        """
        return _get_dependency_sync(category)

    @staticmethod
    async def get_async(category: t.Any) -> t.Any:
        """Get dependency instance asynchronously.

        This is needed for adapter dependencies that require async initialization.

        Args:
            category: The dependency category (string) or class to retrieve

        Returns:
            The dependency instance
        """
        if isinstance(category, str):
            # First try the container cache
            with suppress(Exception):
                result = get_container().get(category)
                if result is not None:
                    return result

            # Import adapter asynchronously
            class_ = await _get_adapter_class_async(category)
            return get_container().get(class_)

        return get_container().get(category)

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        """Support using depends as a callable for bevy compatibility."""
        return injectable()


def _get_dependency_sync(category: t.Any) -> t.Any:
    """Get dependency synchronously (for non-adapter dependencies)."""
    if isinstance(category, str):
        # Try the container cache first
        with suppress(Exception):
            result = get_container().get(category)
            if result is not None:
                return result

        # For string categories that aren't cached, we need async initialization
        # This should only happen for adapters, which should use get_async()
        msg = (
            f"Adapter '{category}' requires async initialization. "
            f"Use 'await depends.get_async(\"{category}\")' instead."
        )
        raise RuntimeError(msg)

    return get_container().get(category)


@lru_cache(maxsize=256)
async def _get_adapter_class_async(category: str) -> t.Any:
    """Get adapter class with async import."""
    from .adapters import _import_adapter

    return await _import_adapter(category)


depends = Depends()


def fast_depends(category: t.Any) -> t.Any:
    """High-performance dependency injection.

    This function provides direct dependency lookup without any
    introspection or special handling.

    Example:
        cache = fast_depends("cache")
        sql = fast_depends("sql")

    Args:
        category: The dependency category or class to retrieve

    Returns:
        The dependency instance

    Note:
        This is now just an alias for depends.get() since we've removed
        the stack introspection overhead.
    """
    return depends.get(category)
