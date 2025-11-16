"""Tests for ACB health check system."""

import asyncio
import pytest

from acb.services._base import ServiceBase, ServiceConfig
from acb.services.health import (
    HealthCheckMixin,
    HealthCheckResult,
    HealthCheckType,
    HealthReporter,
    HealthReporterSettings,
    HealthService,
    HealthServiceSettings,
    HealthStatus,
)


class MockHealthComponent(HealthCheckMixin):
    """Mock component for testing health checks."""

    def __init__(self, component_id: str = "test_component", should_fail: bool = False):
        super().__init__()
        self._component_id = component_id
        self._should_fail = should_fail
        self._check_count = 0

    @property
    def component_id(self) -> str:
        return self._component_id

    @property
    def component_name(self) -> str:
        return f"Test Component {self._component_id}"

    async def _perform_health_check(
        self, check_type: HealthCheckType
    ) -> HealthCheckResult:
        """Mock health check implementation."""
        self._check_count += 1

        if self._should_fail:
            return HealthCheckResult(
                component_id=self.component_id,
                component_name=self.component_name,
                status=HealthStatus.UNHEALTHY,
                check_type=check_type,
                message="Component is unhealthy",
                details={"check_count": self._check_count},
            )

        return HealthCheckResult(
            component_id=self.component_id,
            component_name=self.component_name,
            status=HealthStatus.HEALTHY,
            check_type=check_type,
            message="Component is healthy",
            details={"check_count": self._check_count},
        )


class MockHealthService(ServiceBase, HealthCheckMixin):
    """Mock service for testing service health integration."""

    def __init__(self, service_id: str = "test_service", should_fail: bool = False):
        config = ServiceConfig(service_id=service_id, name=f"Test Service {service_id}")
        super().__init__(config)
        HealthCheckMixin.__init__(self)
        self._should_fail = should_fail

    async def _initialize(self) -> None:
        """Mock initialization."""
        if self._should_fail:
            raise RuntimeError("Service initialization failed")

    async def _shutdown(self) -> None:
        """Mock shutdown."""
        pass

    async def _perform_health_check(
        self, check_type: HealthCheckType
    ) -> HealthCheckResult:
        """Mock health check for service."""
        status = HealthStatus.UNHEALTHY if self._should_fail else HealthStatus.HEALTHY
        message = "Service is unhealthy" if self._should_fail else "Service is healthy"

        return HealthCheckResult(
            component_id=self.component_id,
            component_name=self.component_name,
            status=status,
            check_type=check_type,
            message=message,
            details={"service_status": self.status.value},
        )


@pytest.mark.asyncio
class TestHealthStatus:
    """Test HealthStatus enum functionality."""

    def test_healthy_status_is_truthy(self):
        """Test that healthy and degraded statuses are truthy."""
        assert bool(HealthStatus.HEALTHY) is True
        assert bool(HealthStatus.DEGRADED) is True

    def test_unhealthy_status_is_falsy(self):
        """Test that unhealthy statuses are falsy."""
        assert bool(HealthStatus.UNHEALTHY) is False
        assert bool(HealthStatus.CRITICAL) is False
        assert bool(HealthStatus.UNKNOWN) is False


@pytest.mark.asyncio
class TestHealthCheckResult:
    """Test HealthCheckResult functionality."""

    def test_health_check_result_creation(self):
        """Test creating a health check result."""
        result = HealthCheckResult(
            component_id="test",
            component_name="Test Component",
            status=HealthStatus.HEALTHY,
            check_type=HealthCheckType.LIVENESS,
            message="All good",
        )

        assert result.component_id == "test"
        assert result.component_name == "Test Component"
        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == HealthCheckType.LIVENESS
        assert result.message == "All good"
        assert result.is_healthy is True

    def test_health_check_result_to_dict(self):
        """Test converting result to dictionary."""
        result = HealthCheckResult(
            component_id="test",
            component_name="Test Component",
            status=HealthStatus.DEGRADED,
            check_type=HealthCheckType.READINESS,
            message="Partially healthy",
            details={"cpu_usage": 85.5},
        )

        result_dict = result.to_dict()

        assert result_dict["component_id"] == "test"
        assert result_dict["status"] == "degraded"
        assert result_dict["check_type"] == "readiness"
        assert result_dict["details"]["cpu_usage"] == 85.5
        assert result_dict["is_healthy"] is True  # Degraded is still considered healthy


@pytest.mark.asyncio
class TestHealthCheckMixin:
    """Test HealthCheckMixin functionality."""

    async def test_health_check_mixin_basic_usage(self):
        """Test basic health check functionality."""
        component = MockHealthComponent("test_basic")

        result = await component.perform_health_check()

        assert result.component_id == "test_basic"
        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == HealthCheckType.LIVENESS
        assert result.duration_ms is not None
        assert result.duration_ms > 0

    async def test_health_check_with_failure(self):
        """Test health check when component fails."""
        component = MockHealthComponent("test_fail", should_fail=True)

        result = await component.perform_health_check()

        assert result.component_id == "test_fail"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.is_healthy is False

    async def test_health_check_timeout(self):
        """Test health check timeout handling."""

        class SlowComponent(MockHealthComponent):
            async def _perform_health_check(
                self, check_type: HealthCheckType
            ) -> HealthCheckResult:
                await asyncio.sleep(2.0)  # Longer than timeout
                return await super()._perform_health_check(check_type)

        component = SlowComponent("slow")
        result = await component.perform_health_check(timeout=0.1)

        assert result.status == HealthStatus.CRITICAL
        assert "timed out" in result.message.lower()
        assert result.error == "Timeout"

    async def test_health_check_exception_handling(self):
        """Test health check exception handling."""

        class BrokenComponent(MockHealthComponent):
            async def _perform_health_check(
                self, check_type: HealthCheckType
            ) -> HealthCheckResult:
                raise ValueError("Something broke")

        component = BrokenComponent("broken")
        result = await component.perform_health_check()

        assert result.status == HealthStatus.CRITICAL
        assert "Something broke" in result.error
        assert result.is_healthy is False

    async def test_different_check_types(self):
        """Test different health check types."""
        component = MockHealthComponent("multi_type")

        for check_type in HealthCheckType:
            result = await component.perform_health_check(check_type)
            assert result.check_type == check_type


@pytest.mark.asyncio
class TestHealthReporter:
    """Test HealthReporter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.settings = HealthReporterSettings(
            check_interval=0.1,  # Fast for testing
            critical_threshold=2,
            degraded_threshold=1,
        )

    async def test_health_reporter_component_registration(self):
        """Test registering components with health reporter."""
        reporter = HealthReporter(self.settings)
        component = MockHealthComponent("test_reg")

        reporter.register_component(component)

        assert "test_reg" in reporter._components
        assert reporter._components["test_reg"] == component

    async def test_health_reporter_component_unregistration(self):
        """Test unregistering components."""
        reporter = HealthReporter(self.settings)
        component = MockHealthComponent("test_unreg")

        reporter.register_component(component)
        reporter.unregister_component(component)

        assert "test_unreg" not in reporter._components

    async def test_health_reporter_check_all_components(self):
        """Test checking health of all components."""
        reporter = HealthReporter(self.settings)

        # Register multiple components
        healthy_component = MockHealthComponent("healthy")
        unhealthy_component = MockHealthComponent("unhealthy", should_fail=True)

        reporter.register_component(healthy_component)
        reporter.register_component(unhealthy_component)

        # Check all components
        results = await reporter.check_all_components()

        assert len(results) == 2
        assert results["healthy"].status == HealthStatus.HEALTHY
        assert results["unhealthy"].status == HealthStatus.UNHEALTHY

    async def test_health_reporter_system_health(self):
        """Test system health aggregation."""
        reporter = HealthReporter(self.settings)

        # Add components with different health states
        reporter.register_component(MockHealthComponent("healthy1"))
        reporter.register_component(MockHealthComponent("healthy2"))
        reporter.register_component(MockHealthComponent("unhealthy", should_fail=True))

        # Perform health checks to populate history
        await reporter.check_all_components()

        system_health = reporter.get_system_health()

        assert system_health["components"]["total"] == 3
        assert system_health["components"]["healthy"] == 2
        assert system_health["components"]["unhealthy"] == 1
        assert system_health["system_status"] in ["degraded", "unhealthy"]

    async def test_health_reporter_monitoring_lifecycle(self):
        """Test starting and stopping health monitoring."""
        reporter = HealthReporter(self.settings)
        component = MockHealthComponent("monitor_test")
        reporter.register_component(component)

        # Start monitoring
        await reporter.start_monitoring()
        assert reporter._check_task is not None

        # Let it run briefly
        await asyncio.sleep(0.2)

        # Stop monitoring
        await reporter.stop_monitoring()
        assert reporter._check_task is None

    async def test_health_reporter_history_tracking(self):
        """Test health check history tracking."""
        reporter = HealthReporter(self.settings)
        component = MockHealthComponent("history_test")
        reporter.register_component(component)

        # Perform multiple health checks
        for _ in range(3):
            await reporter.check_all_components()
            await asyncio.sleep(0.01)  # Small delay

        history = reporter.get_component_history("history_test", limit=5)
        assert len(history) == 3
        assert all(result.component_id == "history_test" for result in history)

    async def test_health_reporter_cleanup(self):
        """Test health reporter cleanup."""
        reporter = HealthReporter(self.settings)
        await reporter.start_monitoring()

        # Cleanup should stop monitoring
        await reporter.cleanup()
        assert reporter._check_task is None


@pytest.mark.asyncio
class TestHealthService:
    """Test HealthService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.settings = HealthServiceSettings(
            auto_register_services=False,  # Disable for testing
            health_check_enabled=False,  # Prevent recursion in tests
        )

    async def test_health_service_initialization(self):
        """Test health service initialization."""
        service = HealthService(settings=self.settings)

        await service.initialize()

        assert service.status.value == "active"
        assert service._reporter is not None

    async def test_health_service_component_registration(self):
        """Test registering components with health service."""
        service = HealthService(settings=self.settings)
        component = MockHealthComponent("service_test")

        await service.initialize()
        service.register_component(component)

        # Component should be registered with the reporter
        assert "service_test" in service._reporter._components

    async def test_health_service_system_health_check(self):
        """Test comprehensive system health check."""
        service = HealthService(settings=self.settings)
        component = MockHealthComponent("system_test")

        await service.initialize()
        service.register_component(component)

        health_status = await service.check_system_health()

        assert "system_status" in health_status
        assert "component_results" in health_status
        assert "system_test" in health_status["component_results"]

    async def test_health_service_component_health_check(self):
        """Test checking individual component health."""
        service = HealthService(settings=self.settings)
        component = MockHealthComponent("individual_test")

        await service.initialize()
        service.register_component(component)

        result = await service.check_component_health("individual_test")

        assert result is not None
        assert result.component_id == "individual_test"
        assert result.status == HealthStatus.HEALTHY

    async def test_health_service_component_history(self):
        """Test getting component health history."""
        service = HealthService(settings=self.settings)
        component = MockHealthComponent("history_service_test")

        await service.initialize()
        service.register_component(component)

        # Perform some health checks
        await service.check_component_health("history_service_test")
        await service.check_component_health("history_service_test")

        history = service.get_component_history("history_service_test", limit=5)

        assert len(history) >= 1
        assert all("component_id" in result for result in history)

    async def test_health_service_own_health_check(self):
        """Test health service checking its own health."""
        service = HealthService(settings=self.settings)

        await service.initialize()

        # Health service should be able to check its own health
        result = await service.perform_health_check(HealthCheckType.LIVENESS)

        assert result.component_id == "health_service"
        assert result.status == HealthStatus.HEALTHY
        assert "monitoring_active" in result.details

    async def test_health_service_shutdown(self):
        """Test health service shutdown."""
        service = HealthService(settings=self.settings)

        await service.initialize()
        await service.shutdown()

        assert service.status.value == "stopped"


@pytest.mark.asyncio
class TestServiceHealthIntegration:
    """Test integration between health system and services."""

    async def test_service_with_health_mixin(self):
        """Test service that implements health checking."""
        service = MockHealthService("integration_test")

        await service.initialize()

        # Service should support health checks
        result = await service.perform_health_check()

        assert result.component_id == "integration_test"
        assert result.status == HealthStatus.HEALTHY

        await service.shutdown()

    async def test_service_health_with_reporter(self):
        """Test service health monitoring with reporter."""
        service = MockHealthService("reporter_integration")
        reporter = HealthReporter(HealthReporterSettings(check_interval=0.1))

        await service.initialize()

        # Register service with reporter
        reporter.register_component(service)

        # Check all components should include the service
        results = await reporter.check_all_components()

        assert "reporter_integration" in results
        assert results["reporter_integration"].status == HealthStatus.HEALTHY

        await reporter.cleanup()
        await service.shutdown()

    async def test_failing_service_health(self):
        """Test health monitoring of a failing service."""
        service = MockHealthService("failing_service", should_fail=True)
        reporter = HealthReporter(HealthReporterSettings())

        # Service initialization should fail
        with pytest.raises(RuntimeError):
            await service.initialize()

        # Service should still be monitorable
        reporter.register_component(service)
        results = await reporter.check_all_components()

        assert results["failing_service"].status == HealthStatus.UNHEALTHY

        await reporter.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])
