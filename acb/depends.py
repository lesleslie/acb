import typing as t
from bevy import Inject, auto_inject, get_container
from contextlib import suppress


# Sentinel object for dependency injection markers
class _DependencyMarker:
    """Sentinel object to mark parameters for dependency injection."""

    def __repr__(self) -> str:
        return "<DependencyMarker>"


_DEPENDENCY_SENTINEL = _DependencyMarker()


@t.runtime_checkable
class DependsProtocol(t.Protocol):
    @staticmethod
    def inject(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]: ...
    @staticmethod
    def set(
        class_: t.Any, instance: t.Any = None, module: str | None = None
    ) -> t.Any: ...
    @staticmethod
    def get(category: t.Any, module: str | None = None) -> t.Any: ...
    @staticmethod
    async def get_async(category: t.Any, module: str | None = None) -> t.Any: ...
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
    def set(class_: t.Any, instance: t.Any = None, module: str | None = None) -> t.Any:
        """Register a class/instance in the dependency container.

        Returns the instance that was registered.
        """
        if instance is None:
            instance = class_()
            get_container().add(class_, instance, qualifier=module)
            return instance if not module else (instance, module)
        get_container().add(class_, instance, qualifier=module)
        return instance if not module else (instance, module)

    async def get(self, category: t.Any, module: str | None = None) -> t.Any:
        """Get dependency asynchronously.

        This method is async for proper async initialization of adapters.
        Alias for get_async() for convenience.
        """
        return await Depends.get_async(category, module)

    @staticmethod
    def get_sync(category: t.Any, module: str | None = None) -> t.Any:
        """Get dependency instance synchronously.

        Args:
            category: The dependency category (string) or class to retrieve
            module: The dependency module (string) to retrieve

        Returns:
            The dependency instance

        Note:
            For adapter dependencies that require async initialization,
            use get_async() instead.
        """
        return _get_dependency_sync(category, module)

    @staticmethod
    async def get_async(category: t.Any, module: str | None = None) -> t.Any:
        """Get dependency instance asynchronously.

        This is needed for adapter dependencies that require async initialization.

        Args:
            category: The dependency category (string) or class to retrieve
            module: The dependency module (string) to retrieve

        Returns:
            The dependency instance
        """
        if isinstance(category, str):
            # First try the container cache
            with suppress(Exception):
                result = get_container().get(category, qualifier=module)
                if result is not None:
                    return result

            # Import adapter asynchronously - handle import errors
            try:
                class_ = await _get_adapter_class_async(category)
                return get_container().get(class_, qualifier=module)
            except Exception:
                # If adapter import fails, raise the expected RuntimeError
                msg = (
                    f"Adapter '{category}' requires async initialization. "
                    f"Use 'await depends.get_async(\"{category}\")' instead."
                )
                raise RuntimeError(msg)

        return get_container().get(category, qualifier=module)

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        """Support using depends as a callable for backward compatibility.

        Returns a sentinel marker that can be used as a default parameter value.
        For new code, prefer using Inject[T] type annotations instead.
        """
        return _DEPENDENCY_SENTINEL

    @staticmethod
    def clear() -> None:
        """Clear the dependency container (testing helper).

        Some tests register temporary dependencies (e.g., a mock logger).
        Provide a best-effort cleanup hook that resets or clears the
        underlying Bevy container when available. If the container does not
        expose a reset/clear API, this is a no-op.
        """
        try:
            container = get_container()
        except Exception:
            return

        # Try common container reset/clear operations, ignoring failures.
        with suppress(Exception):
            # Newer Bevy releases may expose `reset()`
            container.reset()  # type: ignore[attr-defined]
            return
        with suppress(Exception):
            # Older variants may expose `clear()`
            container.clear()  # type: ignore[attr-defined]


def _get_dependency_sync(category: t.Any, module: str | None = None) -> t.Any:
    """Get dependency synchronously (for non-adapter dependencies)."""
    if isinstance(category, str):
        # Try the container cache first
        with suppress(Exception):
            result = get_container().get(category, qualifier=module)
            if result is not None:
                return result

        # For string categories that aren't cached, we need async initialization
        # This should only happen for adapters, which should use get_async()
        msg = (
            f"Adapter '{category}' requires async initialization. "
            f"Use 'await depends.get_async(\"{category}\")' instead."
        )
        raise RuntimeError(msg)

    return get_container().get(category, qualifier=module)


async def _get_adapter_class_async(category: str) -> t.Any:
    """Get adapter class with async import.

    Note: lru_cache removed as it doesn't work with async functions.
    Caching happens at the container level instead.
    """
    from .adapters import _import_adapter

    return await _import_adapter(category)


depends = Depends()

# Export Inject for type annotations
__all__ = ["depends", "fast_depends", "Inject", "Depends"]


async def fast_depends(category: t.Any, module: str | None = None) -> t.Any:
    """High-performance dependency injection.

    This function provides direct dependency lookup without any
    introspection or special handling.

    Example:
        cache = await fast_depends("cache")
        sql = await fast_depends("sql", "sqlite"))

    Args:
        category: The dependency category or class to retrieve
        module: The dependency module (string) to retrieve

    Returns:
        The dependency instance

    Note:
        This is now just an alias for depends.get() since we've removed
        the stack introspection overhead.
    """
    return await depends.get(category, module)
