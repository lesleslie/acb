"""Repository Registry Implementation.

Provides centralized registration and discovery of repositories:
- Repository registration and lookup
- Type-safe repository access
- Dependency injection integration
- Repository lifecycle management
"""

import inspect
from enum import Enum

import contextlib
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, TypeVar

from acb.cleanup import CleanupMixin
from acb.depends import depends

from ._base import RepositoryBase, RepositoryError

T = TypeVar("T", bound="RepositoryBase[Any, Any]")
EntityType = TypeVar("EntityType")
IDType = TypeVar("IDType")


class RepositoryScope(Enum):
    """Repository scope enumeration."""

    SINGLETON = "singleton"  # One instance shared across application
    SCOPED = "scoped"  # One instance per scope (e.g., request)
    TRANSIENT = "transient"  # New instance each time


@dataclass
class RepositoryRegistration:
    """Repository registration information."""

    entity_type: type[Any]
    repository_type: type[RepositoryBase[Any, Any]]
    repository_instance: RepositoryBase[Any, Any] | None = None
    scope: RepositoryScope = RepositoryScope.SINGLETON
    factory: t.Callable[[], RepositoryBase[Any, Any]] | None = None
    initialized: bool = False


class RepositoryRegistryError(RepositoryError):
    """Exception for repository registry operations."""

    def __init__(self, message: str, entity_type: str | None = None) -> None:
        super().__init__(message, entity_type=entity_type, operation="registry")


class RepositoryRegistry(CleanupMixin):
    """Registry for managing repository instances.

    Provides centralized registration and lookup of repositories with
    support for dependency injection, lifecycle management, and
    type-safe access patterns.
    """

    def __init__(self) -> None:
        super().__init__()
        self._registrations: dict[type[Any], RepositoryRegistration] = {}
        self._instances: dict[type[Any], RepositoryBase[Any, Any]] = {}
        self._scoped_instances: dict[
            str, dict[type[Any], RepositoryBase[Any, Any]]
        ] = {}
        self._current_scope: str | None = None

    def register(
        self,
        entity_type: type[EntityType],
        repository_type: type[RepositoryBase[EntityType, Any]],
        scope: RepositoryScope = RepositoryScope.SINGLETON,
        factory: t.Callable[[], RepositoryBase[Any, Any]] | None = None,
    ) -> None:
        """Register a repository for an entity type.

        Args:
            entity_type: The entity type this repository handles
            repository_type: The repository class
            scope: Repository scope (singleton, scoped, transient)
            factory: Optional factory function for creating instances
        """
        if entity_type in self._registrations:
            existing = self._registrations[entity_type]
            if existing.repository_type != repository_type:
                entity_name = getattr(entity_type, "__name__", str(entity_type))
                existing_name = getattr(
                    existing.repository_type, "__name__", str(existing.repository_type)
                )
                repo_name = getattr(repository_type, "__name__", str(repository_type))
                msg = (
                    f"Repository for {entity_name} already registered with different type: "
                    f"{existing_name} vs {repo_name}"
                )
                raise RepositoryRegistryError(
                    msg,
                    entity_type=entity_name,
                )

        registration = RepositoryRegistration(
            entity_type=entity_type,
            repository_type=repository_type,
            scope=scope,
            factory=factory,
        )

        self._registrations[entity_type] = registration

        # Register with dependency injection if it's a singleton
        if scope == RepositoryScope.SINGLETON:
            depends.set(repository_type)

    def register_instance(
        self,
        entity_type: type[EntityType],
        repository_instance: RepositoryBase[EntityType, Any],
    ) -> None:
        """Register a pre-created repository instance.

        Args:
            entity_type: The entity type this repository handles
            repository_instance: The repository instance
        """
        registration = RepositoryRegistration(
            entity_type=entity_type,
            repository_type=type(repository_instance),
            repository_instance=repository_instance,
            scope=RepositoryScope.SINGLETON,
            initialized=True,
        )

        self._registrations[entity_type] = registration
        self._instances[entity_type] = repository_instance

        # Register with dependency injection
        depends.set(type(repository_instance), repository_instance)

    def get(self, entity_type: type[EntityType]) -> RepositoryBase[EntityType, Any]:
        """Get repository for entity type.

        Args:
            entity_type: The entity type

        Returns:
            Repository instance

        Raises:
            RepositoryRegistryError: If repository not registered
        """
        if entity_type not in self._registrations:
            entity_name = getattr(entity_type, "__name__", str(entity_type))
            msg = f"No repository registered for entity type: {entity_name}"
            raise RepositoryRegistryError(
                msg,
                entity_type=entity_name,
            )

        registration = self._registrations[entity_type]

        if registration.scope == RepositoryScope.SINGLETON:
            return self._get_singleton_instance(registration)
        if registration.scope == RepositoryScope.SCOPED:
            return self._get_scoped_instance(registration)
        if registration.scope == RepositoryScope.TRANSIENT:
            return self._create_instance(registration)
        entity_name = getattr(entity_type, "__name__", str(entity_type))
        msg = f"Unsupported repository scope: {registration.scope}"
        raise RepositoryRegistryError(
            msg,
            entity_type=entity_name,
        )

    def get_by_name(self, entity_name: str) -> RepositoryBase[Any, Any]:
        """Get repository by entity name.

        Args:
            entity_name: Name of the entity type

        Returns:
            Repository instance

        Raises:
            RepositoryRegistryError: If repository not found
        """
        for entity_type in self._registrations:
            if entity_type.__name__ == entity_name:
                return self.get(entity_type)

        msg = f"No repository registered for entity name: {entity_name}"
        raise RepositoryRegistryError(
            msg,
            entity_type=entity_name,
        )

    def try_get(
        self,
        entity_type: type[EntityType],
    ) -> RepositoryBase[EntityType, Any] | None:
        """Try to get repository for entity type.

        Args:
            entity_type: The entity type

        Returns:
            Repository instance or None if not registered
        """
        try:
            return self.get(entity_type)
        except RepositoryRegistryError:
            return None

    def is_registered(self, entity_type: type[EntityType]) -> bool:
        """Check if repository is registered for entity type.

        Args:
            entity_type: The entity type

        Returns:
            True if registered, False otherwise
        """
        return entity_type in self._registrations

    def list_registrations(self) -> dict[str, dict[str, Any]]:
        """List all repository registrations.

        Returns:
            Dictionary of registrations by entity name
        """
        result = {}
        for entity_type, registration in self._registrations.items():
            result[entity_type.__name__] = {
                "entity_type": entity_type.__name__,
                "repository_type": registration.repository_type.__name__,
                "scope": registration.scope.value,
                "initialized": registration.initialized,
                "has_factory": registration.factory is not None,
            }
        return result

    def auto_register_repositories(self, module_or_package: Any) -> int:
        """Auto-register repositories from a module or package.

        Args:
            module_or_package: Module or package to scan for repositories

        Returns:
            Number of repositories registered
        """
        registered_count = 0

        # Get all classes from the module
        if hasattr(module_or_package, "__dict__"):
            classes = [
                obj
                for obj in module_or_package.__dict__.values()
                if inspect.isclass(obj) and issubclass(obj, RepositoryBase)
            ]
        else:
            classes = []

        for repo_class in classes:
            # Extract entity type from repository class
            entity_type = self._extract_entity_type(repo_class)
            if entity_type:
                with suppress(RepositoryRegistryError):
                    self.register(entity_type, repo_class)
                    registered_count += 1

        return registered_count

    def create_scope(self, scope_id: str) -> str:
        """Create a new scope for scoped repositories.

        Args:
            scope_id: Unique identifier for the scope

        Returns:
            The scope ID
        """
        if scope_id not in self._scoped_instances:
            self._scoped_instances[scope_id] = {}
        return scope_id

    def set_current_scope(self, scope_id: str | None) -> None:
        """Set the current scope for scoped repositories.

        Args:
            scope_id: Scope ID to set as current, or None for global scope
        """
        self._current_scope = scope_id

    async def clear_scope(self, scope_id: str) -> None:
        """Clear all instances for a scope.

        Args:
            scope_id: Scope ID to clear
        """
        if scope_id in self._scoped_instances:
            # Clean up instances
            for instance in self._scoped_instances[scope_id].values():
                if hasattr(instance, "cleanup"):
                    with contextlib.suppress(Exception):
                        await instance.cleanup()

            del self._scoped_instances[scope_id]

    def _get_singleton_instance(
        self,
        registration: RepositoryRegistration,
    ) -> RepositoryBase[Any, Any]:
        """Get singleton repository instance."""
        if registration.repository_instance:
            return registration.repository_instance

        if registration.entity_type in self._instances:
            return self._instances[registration.entity_type]

        # Create new instance
        instance = self._create_instance(registration)
        self._instances[registration.entity_type] = instance
        registration.repository_instance = instance
        registration.initialized = True

        return instance

    def _get_scoped_instance(
        self,
        registration: RepositoryRegistration,
    ) -> RepositoryBase[Any, Any]:
        """Get scoped repository instance."""
        scope_id = self._current_scope or "default"

        if scope_id not in self._scoped_instances:
            self._scoped_instances[scope_id] = {}

        scoped_instances = self._scoped_instances[scope_id]

        if registration.entity_type in scoped_instances:
            return scoped_instances[registration.entity_type]

        # Create new instance for this scope
        instance = self._create_instance(registration)
        scoped_instances[registration.entity_type] = instance

        return instance

    def _create_instance(
        self, registration: RepositoryRegistration
    ) -> RepositoryBase[Any, Any]:
        """Create repository instance."""
        if registration.factory:
            return registration.factory()

        # Use dependency injection to create instance
        try:
            return t.cast(
                RepositoryBase[Any, Any],
                depends.get_sync(registration.repository_type),
            )
        except Exception:
            # Fall back to direct instantiation
            return registration.repository_type(registration.entity_type)

    def _extract_entity_type(
        self,
        repository_class: type[RepositoryBase[Any, Any]],
    ) -> type[Any] | None:
        """Extract entity type from repository class annotations."""
        # Try to get generic type arguments
        if hasattr(repository_class, "__orig_bases__"):
            for base in repository_class.__orig_bases__:
                if hasattr(base, "__args__") and len(base.__args__) >= 1:
                    return base.__args__[0]

        # Try to get from __init__ method
        if hasattr(repository_class, "__init__"):
            signature = inspect.signature(repository_class.__init__)
            for param in signature.parameters.values():
                if (
                    param.name == "entity_type"
                    and param.annotation != inspect.Parameter.empty
                ):
                    return param.annotation

        return None

    async def _cleanup_resources(self) -> None:
        """Clean up all repository instances."""
        # Clean up singleton instances
        for instance in self._instances.values():
            if hasattr(instance, "cleanup"):
                with contextlib.suppress(Exception):
                    await instance.cleanup()

        # Clean up scoped instances
        for scope_instances in self._scoped_instances.values():
            for instance in scope_instances.values():
                if hasattr(instance, "cleanup"):
                    with contextlib.suppress(Exception):
                        await instance.cleanup()

        self._instances.clear()
        self._scoped_instances.clear()
        self._registrations.clear()


# Global registry instance
_global_registry: RepositoryRegistry | None = None


def get_registry() -> RepositoryRegistry:
    """Get the global repository registry.

    Returns:
        Global repository registry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = RepositoryRegistry()
        # Register the registry itself with DI
        depends.set(RepositoryRegistry, _global_registry)
    return _global_registry


def register_repository(
    entity_type: type[EntityType],
    repository_type: type[RepositoryBase[EntityType, Any]],
    scope: RepositoryScope = RepositoryScope.SINGLETON,
) -> None:
    """Register a repository in the global registry.

    Args:
        entity_type: The entity type
        repository_type: The repository class
        scope: Repository scope
    """
    registry = get_registry()
    registry.register(entity_type, repository_type, scope)


def get_repository[EntityType](
    entity_type: type[EntityType],
) -> RepositoryBase[EntityType, Any]:
    """Get repository from global registry.

    Args:
        entity_type: The entity type

    Returns:
        Repository instance
    """
    registry = get_registry()
    return registry.get(entity_type)
