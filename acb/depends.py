from typing import Any, Callable, Protocol, cast, runtime_checkable

from bevy import dependency, get_repository
from bevy import inject as inject_dependency


@runtime_checkable
class DependsProtocol(Protocol):
    """Protocol defining the interface for dependency injection functionality."""

    @staticmethod
    def inject(func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to automatically inject dependencies into functions.

        Args:
            func: The function to inject dependencies into

        Returns:
            The decorated function with automatic dependency injection
        """
        ...

    @staticmethod
    def set(class_: Any) -> Any:
        """Register a dependency into the dependency repository.

        Args:
            class_: The class to register as a dependency

        Returns:
            The registered instance
        """
        ...

    @staticmethod
    def get(class_: Any) -> Any:
        """Retrieve an instance of a registered dependency.

        Args:
            class_: The class or string name of the adapter to retrieve

        Returns:
            An instance of the requested dependency
        """
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make the Depends instance callable to use in dependency injection.

        Returns:
            A dependency marker for the injection system
        """
        ...


class Depends:
    """Dependency injection class for ACB.

    This class provides methods for registering, retrieving, and injecting
    dependencies throughout the application.
    """

    @staticmethod
    def inject(func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to automatically inject dependencies into functions.

        Args:
            func: The function to inject dependencies into

        Returns:
            The decorated function with automatic dependency injection
        """
        return inject_dependency(func)

    @staticmethod
    def set(class_: Any) -> Any:
        """Register a dependency into the dependency repository.

        Args:
            class_: The class to register as a dependency

        Returns:
            The registered instance
        """
        return get_repository().set(class_, class_())

    @staticmethod
    def get(class_: Any) -> Any:
        """Retrieve an instance of a registered dependency.

        Args:
            class_: The class or string name of the adapter to retrieve

        Returns:
            An instance of the requested dependency
        """
        if isinstance(class_, str):
            from acb.adapters import import_adapter

            class_ = import_adapter(class_)
        return cast(class_, get_repository().get(class_))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make the Depends instance callable to use in dependency injection.

        Returns:
            A dependency marker for the injection system
        """
        return dependency()


depends = Depends()
