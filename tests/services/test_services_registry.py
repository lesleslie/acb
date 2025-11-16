"""Tests for ACB services registry functionality."""

import pytest

from acb.services._base import ServiceBase, ServiceConfig, ServiceStatus
from acb.services.registry import (
    ServiceNotFoundError,
    ServiceRegistry,
    get_registry,
    get_service,
    initialize_services,
    register_service,
    shutdown_services,
)


class TestServiceRegistry:
    """Test the ServiceRegistry class."""

    def setup_method(self):
        """Setup for each test method."""
        # Reset global registry state
        import acb.services.registry

        acb.services.registry._registry = None

    @pytest.mark.asyncio
    async def test_registry_service_registration(self):
        """Test basic service registration."""
        registry = ServiceRegistry()

        class TestService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

        service = TestService()
        config = ServiceConfig(service_id="test", name="Test Service")

        await registry.register_service(service, config)

        assert "test" in registry.list_services()
        retrieved_service = registry.get_service("test")
        assert retrieved_service is service

        retrieved_config = registry.get_service_config("test")
        assert retrieved_config.service_id == "test"
        assert retrieved_config.name == "Test Service"

    @pytest.mark.asyncio
    async def test_registry_service_unregistration(self):
        """Test service unregistration."""
        registry = ServiceRegistry()

        class TestService(ServiceBase):
            async def _initialize(self):
                self.init_called = True

            async def _shutdown(self):
                self.shutdown_called = True

        service = TestService()
        config = ServiceConfig(service_id="test", name="Test Service")

        await registry.register_service(service, config)
        await service.initialize()  # Initialize the service

        # Unregister
        await registry.unregister_service("test")

        assert "test" not in registry.list_services()
        with pytest.raises(ServiceNotFoundError):
            registry.get_service("test")

        # Should have called shutdown
        assert hasattr(service, "shutdown_called")

    @pytest.mark.asyncio
    async def test_registry_service_not_found(self):
        """Test ServiceNotFoundError for non-existent services."""
        registry = ServiceRegistry()

        with pytest.raises(ServiceNotFoundError) as exc_info:
            registry.get_service("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.service_id == "nonexistent"

        with pytest.raises(ServiceNotFoundError):
            registry.get_service_config("nonexistent")

    @pytest.mark.asyncio
    async def test_registry_initialize_all_services(self):
        """Test initializing all registered services."""
        registry = ServiceRegistry()

        class Service1(ServiceBase):
            def __init__(self):
                super().__init__(
                    ServiceConfig(service_id="service1", name="Service 1", priority=10)
                )

            async def _initialize(self):
                self.initialized = True

            async def _shutdown(self):
                pass

        class Service2(ServiceBase):
            def __init__(self):
                super().__init__(
                    ServiceConfig(service_id="service2", name="Service 2", priority=20)
                )

            async def _initialize(self):
                self.initialized = True

            async def _shutdown(self):
                pass

        service1 = Service1()
        service2 = Service2()

        await registry.register_service(service1)
        await registry.register_service(service2)

        await registry.initialize_all()

        assert service1.status == ServiceStatus.ACTIVE
        assert service2.status == ServiceStatus.ACTIVE
        assert hasattr(service1, "initialized")
        assert hasattr(service2, "initialized")

    @pytest.mark.asyncio
    async def test_registry_shutdown_all_services(self):
        """Test shutting down all services."""
        registry = ServiceRegistry()

        class TestService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                self.shutdown_called = True

        service = TestService()
        await registry.register_service(service)
        await registry.initialize_all()

        await registry.shutdown_all()

        assert service.status == ServiceStatus.STOPPED
        assert hasattr(service, "shutdown_called")

    @pytest.mark.asyncio
    async def test_registry_services_by_status(self):
        """Test getting services by status."""
        registry = ServiceRegistry()

        class ActiveService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

        class InactiveService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

        active_service = ActiveService()
        inactive_service = InactiveService()

        await registry.register_service(
            active_service, ServiceConfig(service_id="active", name="Active")
        )
        await registry.register_service(
            inactive_service, ServiceConfig(service_id="inactive", name="Inactive")
        )

        await active_service.initialize()

        active_services = registry.get_services_by_status("active")
        inactive_services = registry.get_services_by_status("inactive")

        assert len(active_services) == 1
        assert active_services[0] is active_service
        assert len(inactive_services) == 1
        assert inactive_services[0] is inactive_service

    @pytest.mark.asyncio
    async def test_registry_health_status(self):
        """Test getting health status of all services."""
        registry = ServiceRegistry()

        class HealthyService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

            async def _health_check(self):
                return {"status": "ok"}

        class UnhealthyService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

            async def _health_check(self):
                raise RuntimeError("Service unhealthy")

        healthy_service = HealthyService()
        unhealthy_service = UnhealthyService()

        await registry.register_service(
            healthy_service, ServiceConfig(service_id="healthy", name="Healthy")
        )
        await registry.register_service(
            unhealthy_service, ServiceConfig(service_id="unhealthy", name="Unhealthy")
        )

        await registry.initialize_all()

        health_status = await registry.get_health_status()

        assert health_status["total_services"] == 2
        assert health_status["healthy_services"] == 1
        assert health_status["overall_healthy"] is False
        # Errors list is only populated when service.health_check() raises an uncaught exception
        # Since ServiceBase catches all exceptions, errors list will be empty
        # but the unhealthy service will have healthy: False in the services dict

        assert "healthy" in health_status["services"]
        assert "unhealthy" in health_status["services"]
        assert health_status["services"]["healthy"]["healthy"] is True
        assert health_status["services"]["unhealthy"]["healthy"] is False

    @pytest.mark.asyncio
    async def test_registry_dependency_ordering(self):
        """Test that services are initialized in dependency order."""
        registry = ServiceRegistry()
        initialization_order = []

        class DatabaseService(ServiceBase):
            def __init__(self):
                super().__init__(
                    ServiceConfig(
                        service_id="database", name="Database Service", priority=10
                    )
                )

            async def _initialize(self):
                initialization_order.append("database")

            async def _shutdown(self):
                pass

        class CacheService(ServiceBase):
            def __init__(self):
                super().__init__(
                    ServiceConfig(
                        service_id="cache",
                        name="Cache Service",
                        dependencies=["database"],
                        priority=20,
                    )
                )

            async def _initialize(self):
                initialization_order.append("cache")

            async def _shutdown(self):
                pass

        class WebService(ServiceBase):
            def __init__(self):
                super().__init__(
                    ServiceConfig(
                        service_id="web",
                        name="Web Service",
                        dependencies=["database", "cache"],
                        priority=30,
                    )
                )

            async def _initialize(self):
                initialization_order.append("web")

            async def _shutdown(self):
                pass

        # Register in reverse order to test dependency resolution
        await registry.register_service(WebService())
        await registry.register_service(CacheService())
        await registry.register_service(DatabaseService())

        await registry.initialize_all()

        # Should initialize in dependency order: database -> cache -> web
        assert initialization_order == ["database", "cache", "web"]

    @pytest.mark.asyncio
    async def test_registry_context_manager(self):
        """Test registry as async context manager."""
        registry = ServiceRegistry()

        class TestService(ServiceBase):
            async def _initialize(self):
                self.init_called = True

            async def _shutdown(self):
                self.shutdown_called = True

        service = TestService()
        await registry.register_service(service)

        async with registry:
            assert service.status == ServiceStatus.ACTIVE
            assert hasattr(service, "init_called")

        # After context exit
        assert service.status == ServiceStatus.STOPPED
        assert hasattr(service, "shutdown_called")

    @pytest.mark.asyncio
    async def test_global_registry_functions(self):
        """Test global registry convenience functions."""
        # Reset global state
        import acb.services.registry

        acb.services.registry._registry = None

        class GlobalService(ServiceBase):
            async def _initialize(self):
                self.init_called = True

            async def _shutdown(self):
                self.shutdown_called = True

        service = GlobalService()
        config = ServiceConfig(service_id="global_test", name="Global Test")

        # Test global functions
        await register_service(service, config)

        registry = get_registry()
        assert "global_test" in registry.list_services()

        retrieved_service = await get_service("global_test")
        assert retrieved_service is service

        await initialize_services()
        assert service.status == ServiceStatus.ACTIVE

        await shutdown_services()
        assert service.status == ServiceStatus.STOPPED
