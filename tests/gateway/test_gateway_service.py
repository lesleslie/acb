"""Tests for Gateway Service."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from acb.gateway import (
    AnalyticsCollector,
    AuthManager,
    CacheManager,
    GatewayService,
    RateLimiter,
    RoutingEngine,
    SecurityManager,
)
from acb.gateway._base import (
    GatewayConfig,
    GatewayLevel,
    GatewayRequest,
    GatewayResponse,
    RequestMethod,
)
from acb.gateway.validation import RequestResponseValidator


@pytest.fixture
def mock_config():
    """Mock gateway configuration."""
    config = MagicMock(spec=GatewayConfig)
    config.enabled = True
    config.level = GatewayLevel.STANDARD
    config.tenant_isolation = True
    config.performance_mode = False
    return config


@pytest.fixture
def mock_request():
    """Mock gateway request."""
    return GatewayRequest(
        method=RequestMethod.GET,
        path="/api/test",
        headers={"Authorization": "Bearer test-token"},
        body="",
        query_params={"param": "value"},
        client_ip="127.0.0.1",
        user_agent="test-agent",
    )


@pytest.fixture
def mock_components():
    """Mock gateway components."""
    return {
        "rate_limiter": AsyncMock(spec=RateLimiter),
        "auth_manager": AsyncMock(spec=AuthManager),
        "validator": AsyncMock(spec=RequestResponseValidator),
        "routing_engine": AsyncMock(spec=RoutingEngine),
        "analytics": AsyncMock(spec=AnalyticsCollector),
        "cache": AsyncMock(spec=CacheManager),
        "security": AsyncMock(spec=SecurityManager),
    }


@pytest.fixture
def gateway_service(mock_config, mock_components):
    """Gateway service with mocked components."""
    service = GatewayService(config=mock_config)

    # Inject mocked components
    for name, component in mock_components.items():
        setattr(service, f"_{name}", component)

    return service


class TestGatewayService:
    """Test cases for GatewayService."""

    @pytest.mark.asyncio
    async def test_process_request_success(self, gateway_service, mock_request, mock_components):
        """Test successful request processing."""
        # Setup mocks
        mock_components["auth_manager"].authenticate.return_value = AsyncMock(
            authenticated=True, user_id="test-user"
        )
        mock_components["rate_limiter"].check_rate_limit.return_value = AsyncMock(
            allowed=True, remaining=10
        )
        mock_components["validator"].validate_request.return_value = AsyncMock(
            valid=True, errors=[]
        )
        mock_components["security"].validate_request_security.return_value = []
        mock_components["security"].handle_preflight_request.return_value = None
        mock_components["routing_engine"].route_request.return_value = AsyncMock(
            target_url="http://backend:8080/api/test"
        )
        mock_components["cache"].get.return_value = None

        # Mock upstream response
        upstream_response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"result": "success"},
        )

        # Mock the upstream call
        gateway_service._call_upstream = AsyncMock(return_value=upstream_response)

        # Process request
        response = await gateway_service.process_request(mock_request)

        # Assertions
        assert response.status_code == 200
        assert response.body == {"result": "success"}

        # Verify component calls
        mock_components["auth_manager"].authenticate.assert_called_once_with(mock_request)
        mock_components["rate_limiter"].check_rate_limit.assert_called_once_with(
            mock_request.client_ip, mock_request.tenant_id
        )
        mock_components["validator"].validate_request.assert_called_once_with(mock_request)
        mock_components["analytics"].track_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_request_auth_failure(self, gateway_service, mock_request, mock_components):
        """Test request processing with authentication failure."""
        # Setup auth failure
        mock_components["auth_manager"].authenticate.return_value = AsyncMock(
            authenticated=False, error="Invalid token"
        )

        # Process request
        response = await gateway_service.process_request(mock_request)

        # Assertions
        assert response.status_code == 401
        assert "authentication failed" in response.body.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_process_request_rate_limit_exceeded(self, gateway_service, mock_request, mock_components):
        """Test request processing with rate limit exceeded."""
        # Setup rate limit exceeded
        mock_components["auth_manager"].authenticate.return_value = AsyncMock(
            authenticated=True, user_id="test-user"
        )
        mock_components["rate_limiter"].check_rate_limit.return_value = AsyncMock(
            allowed=False, remaining=0, retry_after=60
        )

        # Process request
        response = await gateway_service.process_request(mock_request)

        # Assertions
        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "60"

    @pytest.mark.asyncio
    async def test_process_request_validation_failure(self, gateway_service, mock_request, mock_components):
        """Test request processing with validation failure."""
        # Setup validation failure
        mock_components["auth_manager"].authenticate.return_value = AsyncMock(
            authenticated=True, user_id="test-user"
        )
        mock_components["rate_limiter"].check_rate_limit.return_value = AsyncMock(
            allowed=True, remaining=10
        )
        mock_components["validator"].validate_request.return_value = AsyncMock(
            valid=False, errors=["Invalid parameter format"]
        )

        # Process request
        response = await gateway_service.process_request(mock_request)

        # Assertions
        assert response.status_code == 400
        assert "validation failed" in response.body.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_process_request_security_violation(self, gateway_service, mock_request, mock_components):
        """Test request processing with security violation."""
        from acb.gateway.security import SecurityViolation

        # Setup security violation
        mock_components["auth_manager"].authenticate.return_value = AsyncMock(
            authenticated=True, user_id="test-user"
        )
        mock_components["rate_limiter"].check_rate_limit.return_value = AsyncMock(
            allowed=True, remaining=10
        )
        mock_components["validator"].validate_request.return_value = AsyncMock(
            valid=True, errors=[]
        )
        mock_components["security"].validate_request_security.return_value = [
            SecurityViolation(
                violation_type="suspicious_user_agent",
                severity="critical",
                description="Malicious user agent detected",
            )
        ]
        mock_components["security"].is_request_blocked.return_value = True

        # Process request
        response = await gateway_service.process_request(mock_request)

        # Assertions
        assert response.status_code == 403
        assert "security violation" in response.body.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_process_request_cache_hit(self, gateway_service, mock_request, mock_components):
        """Test request processing with cache hit."""
        # Setup cache hit
        mock_components["auth_manager"].authenticate.return_value = AsyncMock(
            authenticated=True, user_id="test-user"
        )
        mock_components["rate_limiter"].check_rate_limit.return_value = AsyncMock(
            allowed=True, remaining=10
        )
        mock_components["validator"].validate_request.return_value = AsyncMock(
            valid=True, errors=[]
        )
        mock_components["security"].validate_request_security.return_value = []
        mock_components["security"].handle_preflight_request.return_value = None

        # Mock cache hit
        cached_response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "X-Cache": "HIT"},
            body={"cached": "result"},
        )
        mock_components["cache"].get.return_value = cached_response

        # Process request
        response = await gateway_service.process_request(mock_request)

        # Assertions
        assert response.status_code == 200
        assert response.body == {"cached": "result"}
        assert response.headers.get("X-Cache") == "HIT"

    @pytest.mark.asyncio
    async def test_process_request_cors_preflight(self, gateway_service, mock_request, mock_components):
        """Test CORS preflight request handling."""
        # Setup CORS preflight
        mock_request.method = RequestMethod.OPTIONS

        preflight_response = GatewayResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE",
            },
            body="",
        )
        mock_components["security"].handle_preflight_request.return_value = preflight_response

        # Process request
        response = await gateway_service.process_request(mock_request)

        # Assertions
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers

    @pytest.mark.asyncio
    async def test_call_upstream_success(self, gateway_service):
        """Test successful upstream call."""
        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text.return_value = '{"result": "success"}'
        mock_client.request.return_value.__aenter__.return_value = mock_response

        gateway_service._http_client = mock_client

        # Create request
        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer token"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        # Call upstream
        response = await gateway_service._call_upstream(request, "http://backend:8080/api/test")

        # Assertions
        assert response.status_code == 200
        assert response.body == {"result": "success"}

    @pytest.mark.asyncio
    async def test_call_upstream_timeout(self, gateway_service):
        """Test upstream call timeout."""
        # Mock HTTP client with timeout
        mock_client = AsyncMock()
        mock_client.request.side_effect = asyncio.TimeoutError()

        gateway_service._http_client = mock_client

        # Create request
        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        # Call upstream
        response = await gateway_service._call_upstream(request, "http://backend:8080/api/test")

        # Assertions
        assert response.status_code == 504
        assert "timeout" in response.body.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_get_health_status(self, gateway_service, mock_components):
        """Test health status retrieval."""
        # Setup component health
        mock_components["rate_limiter"].get_health.return_value = {"status": "healthy"}
        mock_components["auth_manager"].get_health.return_value = {"status": "healthy"}
        mock_components["cache"].get_health.return_value = {"status": "healthy"}

        # Get health status
        health = await gateway_service.get_health()

        # Assertions
        assert health["status"] == "healthy"
        assert "components" in health
        assert "uptime" in health
        assert "version" in health

    @pytest.mark.asyncio
    async def test_get_metrics(self, gateway_service, mock_components):
        """Test metrics retrieval."""
        # Setup component metrics
        mock_components["analytics"].get_metrics.return_value = {
            "requests_total": 1000,
            "errors_total": 10,
        }
        mock_components["rate_limiter"].get_metrics.return_value = {
            "rate_limit_hits": 5,
        }

        # Get metrics
        metrics = await gateway_service.get_metrics()

        # Assertions
        assert "requests_total" in metrics
        assert "errors_total" in metrics
        assert "rate_limit_hits" in metrics
        assert "uptime" in metrics

    def test_service_initialization(self, mock_config):
        """Test service initialization."""
        service = GatewayService(config=mock_config)

        # Assertions
        assert service._config == mock_config
        assert service._start_time <= time.time()
        assert hasattr(service, '_rate_limiter')
        assert hasattr(service, '_auth_manager')
        assert hasattr(service, '_validator')
        assert hasattr(service, '_routing_engine')
        assert hasattr(service, '_analytics')
        assert hasattr(service, '_cache')
        assert hasattr(service, '_security')

    @pytest.mark.asyncio
    async def test_cleanup(self, gateway_service, mock_components):
        """Test service cleanup."""
        # Add cleanup methods to mocks
        for component in mock_components.values():
            component.cleanup = AsyncMock()

        # Cleanup
        await gateway_service.cleanup()

        # Verify cleanup was called on all components
        for component in mock_components.values():
            component.cleanup.assert_called_once()
