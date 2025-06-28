import asyncio
import typing as t
from contextlib import suppress
from functools import wraps
from importlib import import_module
from weakref import WeakKeyDictionary

__all__ = ["handle"]


class Handle:
    """Handle common patterns like imports, suppression, and resource management."""

    def __init__(self) -> None:
        self._lazy_imports: dict[str, t.Any] = {}
        self._resource_cleanups: WeakKeyDictionary[
            t.Any, list[t.Callable[[], t.Any]]
        ] = WeakKeyDictionary[t.Any, list[t.Callable[[], t.Any]]]()

    def suppress(self, *exceptions: type[Exception]):
        """Context manager for exception suppression.

        Args:
            *exceptions: Exception types to suppress

        Returns:
            Context manager that suppresses specified exceptions

        Example:
            with handle.suppress(ImportError, ModuleNotFoundError):
                import optional_module
        """
        return suppress(*exceptions)

    def lazy_import(self, module_path: str, attr: str | None = None):
        """Lazy import with circular dependency resolution.

        Args:
            module_path: Full module path to import
            attr: Optional attribute to get from module

        Returns:
            Callable that imports on first access

        Example:
            Logger = handle.lazy_import("acb.logger", "Logger")
            config = handle.lazy_import("acb.config")
        """
        cache_key = f"{module_path}.{attr}" if attr else module_path

        if cache_key in self._lazy_imports:
            return self._lazy_imports[cache_key]

        # Define retry function inside the scope to avoid attribute access issues
        def _retry_import(
            mod_path: str, attr_name: str | None, original_error: Exception
        ) -> t.Any:
            try:
                module = import_module(mod_path)
                result = getattr(module, attr_name) if attr_name else module
                self._lazy_imports[cache_key] = result
                return result
            except Exception:
                raise original_error

        def _import() -> t.Any:
            try:
                module = import_module(module_path)
                if attr:
                    return getattr(module, attr)
                return module
            except (ImportError, AttributeError):
                # Return a placeholder that will retry on next access
                return lambda: _retry_import(module_path, attr, exc)

        # Cache the import function, not the result
        import_func = _import
        self._lazy_imports[cache_key] = import_func
        return import_func

    def resource_manager(
        self, cleanup_method: str = "close"
    ) -> t.Callable[
        [t.Callable[..., t.Awaitable[t.Any]]], t.Callable[..., t.Awaitable[t.Any]]
    ]:
        """Decorator for automatic resource lifecycle management.

        Args:
            cleanup_method: Method name to call for cleanup (default: "close")

        Returns:
            Decorator that adds automatic resource cleanup

        Example:
            @handle.resource_manager("cleanup")
            async def _ensure_client(self):
                return SomeClient()
        """

        def decorator(
            func: t.Callable[..., t.Awaitable[t.Any]],
        ) -> t.Callable[..., t.Awaitable[t.Any]]:
            @wraps(func)
            async def wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
                # Get or create resource
                resource = await func(self, *args, **kwargs)

                # Register cleanup if not already registered
                if self not in self._resource_cleanups:
                    self._resource_cleanups[self] = []

                # Add this resource to cleanup list
                if hasattr(resource, cleanup_method):
                    cleanup_func = getattr(resource, cleanup_method)
                    if cleanup_func not in self._resource_cleanups[self]:
                        self._resource_cleanups[self].append(cleanup_func)

                return resource

            return wrapper

        return decorator

    def error_boundary(
        self, boundary_type: str = "adapter"
    ) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
        """Standardized error handling decorator.

        Args:
            boundary_type: Type of error boundary (adapter, connection, etc.)

        Returns:
            Decorator that provides standardized error handling

        Example:
            @handle.error_boundary("connection")
            async def connect(self):
                # Connection logic with standard error handling
        """

        def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            @wraps(func)
            async def wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    # Log error with context
                    if hasattr(self, "logger"):
                        self.logger.error(
                            f"{boundary_type.title()} error in {func.__name__}: {e}"
                        )

                    # Re-raise with enhanced context
                    error_class = type(e)
                    enhanced_message = (
                        f"{boundary_type.title()} {func.__name__} failed: {e}"
                    )
                    raise error_class(enhanced_message) from e

            # For sync functions
            if not asyncio.iscoroutinefunction(func):

                @wraps(func)
                def sync_wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
                    try:
                        return func(self, *args, **kwargs)
                    except Exception as e:
                        if hasattr(self, "logger"):
                            self.logger.error(
                                f"{boundary_type.title()} error in {func.__name__}: {e}"
                            )
                        error_class = type(e)
                        enhanced_message = (
                            f"{boundary_type.title()} {func.__name__} failed: {e}"
                        )
                        raise error_class(enhanced_message) from e

                return sync_wrapper

            return wrapper

        return decorator

    def connection_pool(
        self,
        pool_type: str = "generic",
        max_connections: int = 10,
        health_check_interval: int = 300,
        max_idle_time: int = 3600,
    ) -> t.Callable[
        [t.Callable[..., t.Awaitable[t.Any]]], t.Callable[..., t.Awaitable[t.Any]]
    ]:
        """Enhanced connection pooling with health checks and cleanup.

        Args:
            pool_type: Type of connection pool
            max_connections: Maximum number of connections
            health_check_interval: Seconds between health checks
            max_idle_time: Maximum seconds a connection can be idle

        Returns:
            Decorator that adds enhanced connection pooling

        Example:
            @handle.connection_pool("redis", max_connections=5, health_check_interval=60)
            async def get_connection(self):
                # Connection logic with enhanced pooling
        """

        def decorator(
            func: t.Callable[..., t.Awaitable[t.Any]],
        ) -> t.Callable[..., t.Awaitable[t.Any]]:
            pool_cache: dict[str, dict[str, t.Any]] = {}

            @wraps(func)
            async def wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
                import asyncio
                import time

                pool_key = f"{pool_type}_{id(self)}"

                if pool_key not in pool_cache:
                    # Create enhanced connection pool
                    pool_cache[pool_key] = {
                        "connections": [],
                        "in_use": set(),
                        "max_size": max_connections,
                        "created_times": {},
                        "last_used": {},
                        "last_health_check": time.time(),
                        "health_check_interval": health_check_interval,
                        "max_idle_time": max_idle_time,
                        "waiting_queue": asyncio.Queue(),
                    }

                pool = pool_cache[pool_key]
                current_time = time.time()

                # Perform periodic health check
                if (
                    current_time - pool["last_health_check"]
                    > pool["health_check_interval"]
                ):
                    await self._cleanup_idle_connections(pool, current_time)
                    pool["last_health_check"] = current_time

                # Try to get available connection
                available = [c for c in pool["connections"] if c not in pool["in_use"]]

                if available:
                    connection = available[0]
                    pool["in_use"].add(connection)
                    pool["last_used"][id(connection)] = current_time
                    return connection

                # Create new connection if under limit
                if len(pool["connections"]) < max_connections:
                    try:
                        connection = await func(self, *args, **kwargs)
                        pool["connections"].append(connection)
                        pool["in_use"].add(connection)
                        pool["created_times"][id(connection)] = current_time
                        pool["last_used"][id(connection)] = current_time
                        return connection
                    except Exception as e:
                        # Connection creation failed
                        raise RuntimeError(
                            f"Failed to create {pool_type} connection: {e}"
                        ) from e

                # Pool exhausted - wait for available connection
                try:
                    # Wait up to 30 seconds for a connection to become available
                    await asyncio.wait_for(pool["waiting_queue"].get(), timeout=30.0)
                    # Recursively try again after waiting
                    return await wrapper(self, *args, **kwargs)
                except TimeoutError:
                    raise RuntimeError(
                        f"Connection pool exhausted for {pool_type} - timeout waiting for connection"
                    )

            return wrapper

        return decorator

    async def _cleanup_idle_connections(
        self, pool: dict[str, t.Any], current_time: float
    ) -> None:
        """Remove idle connections from pool to free resources."""
        connections_to_remove = []

        for connection in pool["connections"]:
            conn_id = id(connection)
            if conn_id in pool["last_used"]:
                idle_time = current_time - pool["last_used"][conn_id]
                if (
                    idle_time > pool["max_idle_time"]
                    and connection not in pool["in_use"]
                ):
                    connections_to_remove.append(connection)

        # Clean up idle connections
        for connection in connections_to_remove:
            pool["connections"].remove(connection)
            conn_id = id(connection)
            pool["created_times"].pop(conn_id, None)
            pool["last_used"].pop(conn_id, None)

            # Close connection if it has close method
            if hasattr(connection, "close"):
                with suppress(Exception):
                    if asyncio.iscoroutinefunction(connection.close):
                        await connection.close()
                    else:
                        connection.close()

    def release_connection(self, pool_type: str, _: int, connection: t.Any) -> None:
        """Release a connection back to the pool."""
        # This would be called by context managers or explicit release
        # Implementation depends on how connections are tracked
        pass

    async def cleanup_resources(self, obj: t.Any) -> None:
        """Manually trigger cleanup for an object's resources.

        Args:
            obj: Object to cleanup resources for

        Example:
            await handle.cleanup_resources(adapter_instance)
        """
        if obj in self._resource_cleanups:
            cleanup_funcs = self._resource_cleanups[obj]
            for cleanup_func in cleanup_funcs:
                try:
                    if asyncio.iscoroutinefunction(cleanup_func):
                        await cleanup_func()
                    else:
                        cleanup_func()
                except Exception as e:
                    # Log cleanup errors but don't raise
                    if hasattr(obj, "logger"):
                        obj.logger.warning(f"Error during resource cleanup: {e}")

            # Clear the cleanup list
            del self._resource_cleanups[obj]

    def retry(
        self, max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0
    ) -> t.Callable[
        [t.Callable[..., t.Awaitable[t.Any]]], t.Callable[..., t.Awaitable[t.Any]]
    ]:
        """Retry decorator with exponential backoff.

        Args:
            max_attempts: Maximum number of retry attempts
            delay: Initial delay between retries in seconds
            backoff: Backoff multiplier for delay

        Returns:
            Decorator that adds retry logic

        Example:
            @handle.retry(max_attempts=5, delay=0.5)
            async def unreliable_operation(self):
                # Operation that might fail
        """

        def decorator(
            func: t.Callable[..., t.Awaitable[t.Any]],
        ) -> t.Callable[..., t.Awaitable[t.Any]]:
            @wraps(func)
            async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                last_exception = None
                current_delay = delay

                for attempt in range(max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e

                        if attempt == max_attempts - 1:
                            # Last attempt, re-raise
                            raise

                        # Wait before retry
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

                # This should never be reached, but just in case
                if last_exception:
                    raise last_exception

            return wrapper

        return decorator


# Export the action instance
handle = Handle()
