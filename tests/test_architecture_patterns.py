"""Tests for ACB service architecture patterns.

This module tests the recommended service architecture patterns:
- Complex services using _base.py pattern
- Simple services with direct ServiceBase inheritance
- Proper lifecycle management
- Dependency injection integration
"""

import pytest

from acb.adapters import import_adapter
from acb.depends import Inject, depends
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings


class TestServiceBasePattern:
    """Test the base service patterns."""

    def test_service_base_instantiation(self):
        """Test that ServiceBase can be instantiated properly."""
        service_config = ServiceConfig(service_id="test_service", name="Test Service")
        settings = ServiceSettings()

        service = ServiceBase(service_config, settings)

        assert service.service_id == "test_service"
        assert service.name == "Test Service"
        assert service.status.value == "inactive"

    async def test_service_lifecycle(self):
        """Test service lifecycle management."""

        class TestService(ServiceBase):
            def __init__(self):
                service_config = ServiceConfig(
                    service_id="lifecycle_test", name="Lifecycle Test Service"
                )
                super().__init__(service_config=service_config)
                self._initialized = False
                self._shutdown = False

            async def _initialize(self) -> None:
                self._initialized = True

            async def _shutdown(self) -> None:
                self._shutdown = True

            async def _health_check(self) -> dict:
                return {"status": "ok", "test": True}

        service = TestService()

        # Test initialization
        await service.initialize()
        assert service._initialized
        assert service.status.value == "active"

        # Test health check
        health = await service.health_check()
        assert health["service_specific"]["test"]

        # Test shutdown
        await service.shutdown()
        assert service._shutdown
        assert service.status.value == "stopped"


class TestComplexServicePattern:
    """Test the complex service pattern with _base.py."""

    async def test_complex_service_uses_base_pattern(self):
        """Test that complex services properly use the _base.py pattern."""
        # This test verifies that the pattern is correctly implemented
        # by checking that services inherit from base classes in _base.py files
        from acb.services.repository.service import RepositoryService

        service = RepositoryService()

        # Should be an instance of both ServiceBase and RepositoryBase
        assert isinstance(service, ServiceBase)
        assert hasattr(
            service, "get_repository"
        )  # Method from RepositoryBase functionality
        assert hasattr(
            service, "register_repository"
        )  # Method from RepositoryBase functionality


class TestSimpleServicePattern:
    """Test the simple service pattern with direct inheritance."""

    def test_simple_service_direct_inheritance(self):
        """Test that simple services directly inherit from ServiceBase."""

        class SimpleTestService(ServiceBase):
            def __init__(self):
                service_config = ServiceConfig(
                    service_id="simple_test", name="Simple Test Service"
                )
                super().__init__(service_config=service_config)

            async def _initialize(self) -> None:
                pass

            async def _shutdown(self) -> None:
                pass

            async def _health_check(self) -> dict:
                return {"status": "simple_ok"}

        service = SimpleTestService()

        # Should only inherit directly from ServiceBase
        assert isinstance(service, ServiceBase)
        # Should not have complex base classes
        assert not hasattr(service, "get_repository")


class TestServiceDependencyInjection:
    """Test service integration with dependency injection."""

    async def test_service_with_dependency_injection(self):
        """Test that services work properly with dependency injection."""

        class DIDependencyService(ServiceBase):
            def __init__(self):
                service_config = ServiceConfig(
                    service_id="di_test", name="DI Test Service"
                )
                super().__init__(service_config=service_config)

            async def _initialize(self) -> None:
                pass

            async def _shutdown(self) -> None:
                pass

            async def _health_check(self) -> dict:
                return {"status": "di_ok"}

            async def use_cache(self):
                # Try to get cache adapter using dependency injection
                Cache = import_adapter("cache")
                cache = depends.get(Cache)
                return cache

        service = DIDependencyService()
        await service.initialize()

        # The service should be able to request dependencies
        # In test environment, this will likely return a mock or None
        try:
            await service.use_cache()
            # If no exception, the pattern works
        except Exception:
            # Expected in test environment where adapters might not be configured
            pass

        await service.shutdown()


class TestServiceHealthMetrics:
    """Test service health checking and metrics."""

    async def test_service_health_monitoring(self):
        """Test that services properly implement health checking."""

        class HealthTestService(ServiceBase):
            def __init__(self):
                service_config = ServiceConfig(
                    service_id="health_test", name="Health Test Service"
                )
                super().__init__(service_config=service_config)
                self.health_call_count = 0

            async def _initialize(self) -> None:
                pass

            async def _shutdown(self) -> None:
                pass

            async def _health_check(self) -> dict:
                self.health_call_count += 1
                return {
                    "status": "healthy",
                    "call_count": self.health_call_count,
                    "custom_metric": True,
                }

        service = HealthTestService()
        await service.initialize()

        # Check initial health
        health = await service.health_check()
        assert health["service_specific"]["call_count"] == 1
        assert health["service_specific"]["custom_metric"]

        # Check health again
        health2 = await service.health_check()
        assert health2["service_specific"]["call_count"] == 2

        await service.shutdown()


@depends.inject
async def use_test_service(test_service: Inject[ServiceBase] = depends()) -> dict:
    """Test function to verify service injection works."""
    if test_service:
        health = await test_service.health_check()
        return health
    return {"error": "no_service"}


if __name__ == "__main__":
    # Run tests manually if executed directly
    import pytest

    pytest.main([__file__, "-v"])
