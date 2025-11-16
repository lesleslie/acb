"""Integration tests for health monitoring with ACB adapters and services."""

from unittest.mock import Mock

import pytest

from acb.services import (
    HealthCheckMixin,
    HealthCheckResult,
    HealthCheckType,
    HealthService,
    HealthStatus,
    get_registry,
    setup_services,
)
from acb.services._base import ServiceBase, ServiceConfig


class HealthAwareAdapter(HealthCheckMixin):
    """Mock adapter that implements health checking."""

    def __init__(
        self, adapter_name: str = "test_adapter", connection_healthy: bool = True
    ):
        super().__init__()
        self._adapter_name = adapter_name
        self._connection_healthy = connection_healthy
        self._client = None

    @property
    def component_id(self) -> str:
        return f"{self._adapter_name}_adapter"

    @property
    def component_name(self) -> str:
        return f"{self._adapter_name.title()} Adapter"

    async def _perform_health_check(
        self, check_type: HealthCheckType
    ) -> HealthCheckResult:
        """Simulate adapter health check."""
        if check_type == HealthCheckType.DEPENDENCY:
            # Check if external service is available
            status = (
                HealthStatus.HEALTHY
                if self._connection_healthy
                else HealthStatus.CRITICAL
            )
            message = (
                "External service available"
                if self._connection_healthy
                else "External service unavailable"
            )
        elif check_type == HealthCheckType.READINESS:
            # Check if adapter is ready to serve requests
            status = HealthStatus.HEALTHY if self._client else HealthStatus.UNHEALTHY
            message = "Adapter ready" if self._client else "Adapter not initialized"
        else:  # LIVENESS, STARTUP, RESOURCE
            status = HealthStatus.HEALTHY
            message = "Adapter is alive"

        return HealthCheckResult(
            component_id=self.component_id,
            component_name=self.component_name,
            status=status,
            check_type=check_type,
            message=message,
            details={
                "adapter_type": self._adapter_name,
                "client_initialized": self._client is not None,
                "connection_healthy": self._connection_healthy,
            },
        )

    async def initialize(self):
        """Simulate adapter initialization."""
        self._client = Mock()  # Simulate client connection


class HealthAwareService(ServiceBase, HealthCheckMixin):
    """Mock service that depends on adapters and implements health checking."""

    def __init__(self, service_id: str = "health_aware_service"):
        config = ServiceConfig(
            service_id=service_id,
            name="Health Aware Service",
            dependencies=["test_adapter"],
        )
        super().__init__(config)
        HealthCheckMixin.__init__(self)

        self._adapters: list[HealthAwareAdapter] = []
        self._processing_requests = False

    def add_adapter(self, adapter: HealthAwareAdapter):
        """Add an adapter dependency."""
        self._adapters.append(adapter)

    async def _initialize(self):
        """Initialize service and adapters."""
        for adapter in self._adapters:
            await adapter.initialize()
        self._processing_requests = True

    async def _shutdown(self):
        """Shutdown service."""
        self._processing_requests = False

    async def _perform_health_check(
        self, check_type: HealthCheckType
    ) -> HealthCheckResult:
        """Comprehensive health check including adapter dependencies."""
        if check_type == HealthCheckType.DEPENDENCY:
            # Check all adapter dependencies
            adapter_statuses = []
            for adapter in self._adapters:
                adapter_result = await adapter.perform_health_check(
                    HealthCheckType.DEPENDENCY
                )
                adapter_statuses.append(adapter_result.is_healthy)

            all_healthy = all(adapter_statuses)
            status = HealthStatus.HEALTHY if all_healthy else HealthStatus.CRITICAL
            message = (
                "All dependencies healthy"
                if all_healthy
                else "Some dependencies unhealthy"
            )

            return HealthCheckResult(
                component_id=self.component_id,
                component_name=self.component_name,
                status=status,
                check_type=check_type,
                message=message,
                details={
                    "dependency_count": len(self._adapters),
                    "healthy_dependencies": sum(adapter_statuses),
                    "service_processing": self._processing_requests,
                },
            )

        elif check_type == HealthCheckType.READINESS:
            # Service is ready if it's processing and adapters are ready
            adapter_statuses = []
            for adapter in self._adapters:
                adapter_result = await adapter.perform_health_check(
                    HealthCheckType.READINESS
                )
                adapter_statuses.append(adapter_result.is_healthy)

            ready = self._processing_requests and all(adapter_statuses)

            status = HealthStatus.HEALTHY if ready else HealthStatus.UNHEALTHY
            message = "Service ready" if ready else "Service not ready"

            return HealthCheckResult(
                component_id=self.component_id,
                component_name=self.component_name,
                status=status,
                check_type=check_type,
                message=message,
                details={"processing_requests": self._processing_requests},
            )

        else:  # LIVENESS, STARTUP, RESOURCE
            status = (
                HealthStatus.HEALTHY
                if self.status.value == "active"
                else HealthStatus.UNHEALTHY
            )
            message = f"Service status: {self.status.value}"

            return HealthCheckResult(
                component_id=self.component_id,
                component_name=self.component_name,
                status=status,
                check_type=check_type,
                message=message,
                details={"service_status": self.status.value},
            )


@pytest.mark.asyncio
class TestHealthAdapterIntegration:
    """Test health monitoring integration with adapters."""

    async def test_healthy_adapter_monitoring(self):
        """Test monitoring a healthy adapter."""
        adapter = HealthAwareAdapter("database", connection_healthy=True)
        await adapter.initialize()

        # Test different check types
        liveness = await adapter.perform_health_check(HealthCheckType.LIVENESS)
        assert liveness.status == HealthStatus.HEALTHY

        readiness = await adapter.perform_health_check(HealthCheckType.READINESS)
        assert readiness.status == HealthStatus.HEALTHY

        dependency = await adapter.perform_health_check(HealthCheckType.DEPENDENCY)
        assert dependency.status == HealthStatus.HEALTHY

    async def test_unhealthy_adapter_monitoring(self):
        """Test monitoring an adapter with connection issues."""
        adapter = HealthAwareAdapter("cache", connection_healthy=False)
        await adapter.initialize()

        # Dependency check should fail
        dependency = await adapter.perform_health_check(HealthCheckType.DEPENDENCY)
        assert dependency.status == HealthStatus.CRITICAL
        assert "unavailable" in dependency.message.lower()

        # But liveness should still pass
        liveness = await adapter.perform_health_check(HealthCheckType.LIVENESS)
        assert liveness.status == HealthStatus.HEALTHY

    async def test_adapter_readiness_without_initialization(self):
        """Test adapter readiness before initialization."""
        adapter = HealthAwareAdapter("storage")

        # Without initialization, readiness should fail
        readiness = await adapter.perform_health_check(HealthCheckType.READINESS)
        assert readiness.status == HealthStatus.UNHEALTHY
        assert "not initialized" in readiness.message.lower()


@pytest.mark.asyncio
class TestHealthServiceIntegration:
    """Test health monitoring integration with services."""

    async def test_service_with_healthy_dependencies(self):
        """Test service health when all dependencies are healthy."""
        # Create service with healthy adapter dependencies
        service = HealthAwareService("integration_service")

        healthy_db = HealthAwareAdapter("database", connection_healthy=True)
        healthy_cache = HealthAwareAdapter("cache", connection_healthy=True)

        service.add_adapter(healthy_db)
        service.add_adapter(healthy_cache)

        await service.initialize()

        # Check different health aspects
        dependency_check = await service.perform_health_check(
            HealthCheckType.DEPENDENCY
        )
        assert dependency_check.status == HealthStatus.HEALTHY
        assert dependency_check.details["healthy_dependencies"] == 2

        readiness_check = await service.perform_health_check(HealthCheckType.READINESS)
        assert readiness_check.status == HealthStatus.HEALTHY

        await service.shutdown()

    async def test_service_with_unhealthy_dependencies(self):
        """Test service health when some dependencies are unhealthy."""
        service = HealthAwareService("failing_service")

        healthy_db = HealthAwareAdapter("database", connection_healthy=True)
        unhealthy_cache = HealthAwareAdapter("cache", connection_healthy=False)

        service.add_adapter(healthy_db)
        service.add_adapter(unhealthy_cache)

        await service.initialize()

        # Dependency check should fail due to unhealthy cache
        dependency_check = await service.perform_health_check(
            HealthCheckType.DEPENDENCY
        )
        assert dependency_check.status == HealthStatus.CRITICAL
        assert dependency_check.details["healthy_dependencies"] == 1
        assert dependency_check.details["dependency_count"] == 2

        await service.shutdown()


@pytest.mark.asyncio
class TestHealthSystemIntegration:
    """Test complete health monitoring system integration."""

    async def test_health_service_with_real_components(self):
        """Test health service monitoring real application components."""
        # Set up a complete system
        health_service = HealthService()
        await health_service.initialize()

        # Create and register components
        db_adapter = HealthAwareAdapter("database", connection_healthy=True)
        cache_adapter = HealthAwareAdapter("cache", connection_healthy=False)
        app_service = HealthAwareService("app_service")

        await db_adapter.initialize()
        await cache_adapter.initialize()

        app_service.add_adapter(db_adapter)
        app_service.add_adapter(cache_adapter)
        await app_service.initialize()

        # Register all components with health service
        health_service.register_component(db_adapter)
        health_service.register_component(cache_adapter)
        health_service.register_component(app_service)

        # Get comprehensive system health
        system_health = await health_service.check_system_health()

        # Verify system recognizes all components
        assert system_health["components"]["total"] == 3

        # Should have issues due to unhealthy cache
        unhealthy_components = (
            system_health["components"]["unhealthy"]
            + system_health["components"]["critical"]
        )
        assert unhealthy_components > 0

        # Verify individual component results
        component_results = system_health["component_results"]
        assert "database_adapter" in component_results
        assert "cache_adapter" in component_results
        assert "app_service" in component_results

        # Database should be healthy
        assert component_results["database_adapter"]["status"] == "healthy"

        # Cache should be unhealthy (connection issues)
        cache_result = component_results["cache_adapter"]
        assert cache_result["status"] in ["critical", "unhealthy"]

        await app_service.shutdown()
        await health_service.shutdown()

    async def test_health_monitoring_with_service_registry(self):
        """Test health monitoring integrated with service registry."""
        # Set up services using the registry
        registry = get_registry()

        # Create health-aware service
        app_service = HealthAwareService("registry_service")
        healthy_adapter = HealthAwareAdapter("storage", connection_healthy=True)
        app_service.add_adapter(healthy_adapter)

        # Register and initialize service
        await registry.register_service(app_service)
        await registry.initialize_all()

        # Create and initialize health service
        health_service = HealthService()
        await health_service.initialize()

        # Register service with health monitoring
        health_service.register_component(app_service)
        health_service.register_component(healthy_adapter)

        # Check system health
        system_health = await health_service.check_system_health()

        assert system_health["components"]["total"] == 2
        assert system_health["components"]["healthy"] == 2

        await health_service.shutdown()
        await registry.shutdown_all()

    async def test_health_monitoring_lifecycle(self):
        """Test complete lifecycle of health monitoring system."""
        # Setup services with health monitoring
        registry = await setup_services(enable_health_monitoring=True)

        # Get the health service
        health_service = registry.get_service("health_service")
        assert health_service is not None

        # Create additional components
        test_adapter = HealthAwareAdapter("test", connection_healthy=True)
        test_service = HealthAwareService("test_service")
        test_service.add_adapter(test_adapter)

        await test_adapter.initialize()
        await registry.register_service(test_service)
        await test_service.initialize()

        # Register with health monitoring
        health_service.register_component(test_adapter)
        health_service.register_component(test_service)

        # System should be healthy
        system_health = await health_service.check_system_health()
        assert system_health["system_healthy"] is True

        # Simulate adapter failure
        test_adapter._connection_healthy = False

        # System should now be unhealthy
        system_health = await health_service.check_system_health()
        assert system_health["system_healthy"] is False

        # Cleanup
        await registry.shutdown_all()

    async def test_health_monitoring_with_alerts(self):
        """Test health monitoring with alerting capabilities."""
        # Disable auto_register_services to avoid picking up components from previous tests
        from acb.services import HealthServiceSettings
        from acb.services._base import ServiceConfig

        config = ServiceConfig(service_id="health_service", name="Health Service")
        settings = HealthServiceSettings(auto_register_services=False)
        health_service = HealthService(service_config=config, settings=settings)
        await health_service.initialize()

        # Create component that will fail
        failing_component = HealthAwareAdapter("failing", connection_healthy=True)
        await failing_component.initialize()
        health_service.register_component(failing_component)

        # Initial check should be healthy
        initial_health = await health_service.check_system_health()
        assert initial_health["system_healthy"] is True

        # Simulate failure
        failing_component._connection_healthy = False

        # Health check should now detect the issue
        failed_health = await health_service.check_system_health()
        assert failed_health["system_healthy"] is False

        # Component history should show the failure
        history = health_service.get_component_history("failing_adapter", limit=2)
        assert len(history) >= 1
        assert not history[-1]["is_healthy"]  # Most recent should be unhealthy

        await health_service.shutdown()


@pytest.mark.asyncio
class TestHealthMonitoringScenarios:
    """Test real-world health monitoring scenarios."""

    async def test_gradual_system_degradation(self):
        """Test system health during gradual degradation."""
        # Disable auto_register_services to avoid picking up components from previous tests
        from acb.services import HealthServiceSettings
        from acb.services._base import ServiceConfig

        config = ServiceConfig(service_id="health_service", name="Health Service")
        settings = HealthServiceSettings(auto_register_services=False)
        health_service = HealthService(service_config=config, settings=settings)
        await health_service.initialize()

        # Set up multiple components
        components = [
            HealthAwareAdapter(f"service_{i}", connection_healthy=True)
            for i in range(5)
        ]

        for component in components:
            await component.initialize()
            health_service.register_component(component)

        # Initially all healthy
        system_health = await health_service.check_system_health()
        assert system_health["system_healthy"] is True
        assert system_health["components"]["healthy"] == 5

        # Gradually fail components
        components[0]._connection_healthy = False
        system_health = await health_service.check_system_health()
        # Should be degraded but still considered healthy
        assert system_health["components"]["healthy"] == 4

        components[1]._connection_healthy = False
        components[2]._connection_healthy = False
        system_health = await health_service.check_system_health()
        # More than half failed - system should be unhealthy
        assert system_health["system_healthy"] is False
        assert system_health["components"]["healthy"] == 2

        await health_service.shutdown()

    async def test_recovery_monitoring(self):
        """Test monitoring system recovery from failures."""
        # Disable auto_register_services to avoid picking up components from previous tests
        from acb.services import HealthServiceSettings
        from acb.services._base import ServiceConfig

        config = ServiceConfig(service_id="health_service", name="Health Service")
        settings = HealthServiceSettings(auto_register_services=False)
        health_service = HealthService(service_config=config, settings=settings)
        await health_service.initialize()

        # Start with failed component
        recovering_component = HealthAwareAdapter(
            "recovering", connection_healthy=False
        )
        await recovering_component.initialize()
        health_service.register_component(recovering_component)

        # Should be unhealthy
        initial_health = await health_service.check_system_health()
        assert initial_health["system_healthy"] is False

        # Simulate recovery
        recovering_component._connection_healthy = True

        # Should recover to healthy
        recovered_health = await health_service.check_system_health()
        assert recovered_health["system_healthy"] is True

        # History should show the recovery
        history = health_service.get_component_history("recovering_adapter", limit=5)
        assert len(history) >= 2

        # Should have at least one unhealthy and one healthy result
        statuses = [result["status"] for result in history]
        assert any(status in ["critical", "unhealthy"] for status in statuses)
        assert any(status == "healthy" for status in statuses)

        await health_service.shutdown()


if __name__ == "__main__":
    pytest.main([__file__])
