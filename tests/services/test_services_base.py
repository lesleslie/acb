"""Tests for ACB services layer base functionality."""

import pytest

from acb.services._base import (
    ServiceBase,
    ServiceConfig,
    ServiceMetrics,
    ServiceSettings,
    ServiceStatus,
)


class TestServiceBase:
    """Test the ServiceBase class."""

    def test_service_settings_creation(self):
        """Test ServiceSettings creation with defaults."""
        settings = ServiceSettings()
        assert settings.enabled is True
        assert settings.timeout == 30.0
        assert settings.retry_attempts == 3
        assert settings.health_check_enabled is True

    def test_service_config_creation(self):
        """Test ServiceConfig creation."""
        config = ServiceConfig(
            service_id="test_service",
            name="Test Service",
            description="A test service",
            dependencies=["cache", "sql"],
            priority=50,
        )

        assert config.service_id == "test_service"
        assert config.name == "Test Service"
        assert config.description == "A test service"
        assert config.dependencies == ["cache", "sql"]
        assert config.priority == 50

    def test_service_metrics_creation(self):
        """Test ServiceMetrics creation and defaults."""
        metrics = ServiceMetrics()
        assert metrics.initialized_at is None
        assert metrics.requests_handled == 0
        assert metrics.errors_count == 0
        assert metrics.last_error is None
        assert isinstance(metrics.custom_metrics, dict)

    @pytest.mark.asyncio
    async def test_service_base_initialization(self):
        """Test ServiceBase initialization and lifecycle."""

        class TestService(ServiceBase):
            async def _initialize(self):
                self.initialized = True

            async def _shutdown(self):
                self.shutdown_called = True

        service = TestService()
        assert service.status == ServiceStatus.INACTIVE

        # Initialize
        await service.initialize()
        assert service.status == ServiceStatus.ACTIVE
        assert hasattr(service, "initialized")
        assert service.initialized is True

        # Shutdown
        await service.shutdown()
        assert service.status == ServiceStatus.STOPPED
        assert hasattr(service, "shutdown_called")
        assert service.shutdown_called is True

    @pytest.mark.asyncio
    async def test_service_health_check(self):
        """Test service health check functionality."""

        class HealthyService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

            async def _health_check(self):
                return {"custom_status": "all_good"}

        service = HealthyService()
        await service.initialize()

        health = await service.health_check()
        assert health["service_id"] == "healthyservice"
        assert health["healthy"] is True
        assert health["service_specific"]["custom_status"] == "all_good"
        assert "uptime" in health
        assert "metrics" in health

    @pytest.mark.asyncio
    async def test_service_error_handling(self):
        """Test service error handling during initialization."""

        class FailingService(ServiceBase):
            async def _initialize(self):
                raise ValueError("Initialization failed")

            async def _shutdown(self):
                pass

        service = FailingService()

        with pytest.raises(ValueError, match="Initialization failed"):
            await service.initialize()

        assert service.status == ServiceStatus.ERROR
        assert service.metrics.errors_count == 1
        assert "Initialization failed" in service.metrics.last_error

    @pytest.mark.asyncio
    async def test_service_metrics_tracking(self):
        """Test service metrics tracking functionality."""

        class MetricsService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

        service = MetricsService()

        # Test request counting
        service.increment_requests()
        service.increment_requests()
        assert service.metrics.requests_handled == 2

        # Test error recording
        service.record_error("Test error")
        assert service.metrics.errors_count == 1
        assert service.metrics.last_error == "Test error"

        # Test custom metrics
        service.set_custom_metric("custom_key", 42)
        assert service.get_custom_metric("custom_key") == 42
        assert service.get_custom_metric("nonexistent", "default") == "default"

    @pytest.mark.asyncio
    async def test_service_context_manager(self):
        """Test service as async context manager."""

        class ContextService(ServiceBase):
            async def _initialize(self):
                self.init_called = True

            async def _shutdown(self):
                self.shutdown_called = True

        async with ContextService() as service:
            assert service.status == ServiceStatus.ACTIVE
            assert hasattr(service, "init_called")
            assert service.init_called is True

        # After context exit
        assert service.status == ServiceStatus.STOPPED
        assert hasattr(service, "shutdown_called")
        assert service.shutdown_called is True

    @pytest.mark.asyncio
    async def test_service_double_initialization(self):
        """Test that double initialization is handled gracefully."""

        class SimpleService(ServiceBase):
            def __init__(self):
                super().__init__()
                self.init_count = 0

            async def _initialize(self):
                self.init_count += 1

            async def _shutdown(self):
                pass

        service = SimpleService()

        # Initialize twice
        await service.initialize()
        await service.initialize()

        # Should only initialize once
        assert service.init_count == 1
        assert service.status == ServiceStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_service_shutdown_without_init(self):
        """Test shutdown without initialization."""

        class ShutdownService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                self.shutdown_called = True

        service = ShutdownService()

        # Shutdown without init should work
        await service.shutdown()
        assert service.status == ServiceStatus.STOPPED

    @pytest.mark.asyncio
    async def test_service_health_check_failure(self):
        """Test health check when service-specific check fails."""

        class UnhealthyService(ServiceBase):
            async def _initialize(self):
                pass

            async def _shutdown(self):
                pass

            async def _health_check(self):
                raise RuntimeError("Health check failed")

        service = UnhealthyService()
        await service.initialize()

        health = await service.health_check()
        assert health["healthy"] is False
        assert health["status"] == ServiceStatus.ERROR.value
        assert "error" in health
        assert "Health check failed" in health["error"]
