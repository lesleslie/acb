"""Tests for Gateway Base functionality."""

import json
from uuid import uuid4

import pytest

from acb.gateway._base import (
    GatewayConfig,
    GatewayLevel,
    GatewayRequest,
    GatewayResponse,
    GatewayResult,
    GatewaySettings,
    HttpMethod,
)


class TestHttpMethod:
    """Test cases for HttpMethod enum."""

    def test_http_method_values(self):
        """Test HTTP method enum values."""
        assert HttpMethod.GET.value == "GET"
        assert HttpMethod.POST.value == "POST"
        assert HttpMethod.PUT.value == "PUT"
        assert HttpMethod.DELETE.value == "DELETE"
        assert HttpMethod.PATCH.value == "PATCH"
        assert HttpMethod.HEAD.value == "HEAD"
        assert HttpMethod.OPTIONS.value == "OPTIONS"

    def test_http_method_from_string(self):
        """Test creating HTTP method from string."""
        assert HttpMethod("GET") == HttpMethod.GET
        assert HttpMethod("post".upper()) == HttpMethod.POST

    def test_http_method_case_sensitivity(self):
        """Test HTTP method case sensitivity."""
        with pytest.raises(ValueError):
            HttpMethod("get")  # Should be uppercase


class TestGatewayLevel:
    """Test cases for GatewayLevel enum."""

    def test_gateway_level_values(self):
        """Test gateway level enum values."""
        assert GatewayLevel.BASIC.value == "basic"
        assert GatewayLevel.STANDARD.value == "standard"
        assert GatewayLevel.ADVANCED.value == "advanced"
        assert GatewayLevel.ENTERPRISE.value == "enterprise"

    def test_gateway_level_ordering(self):
        """Test gateway level ordering."""
        levels = [GatewayLevel.BASIC, GatewayLevel.STANDARD, GatewayLevel.ADVANCED, GatewayLevel.ENTERPRISE]
        assert len(levels) == 4


class TestGatewayRequest:
    """Test cases for GatewayRequest."""

    def test_gateway_request_creation(self):
        """Test creating a gateway request."""
        request_id = str(uuid4())
        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer token", "Content-Type": "application/json"},
            body='{"key": "value"}',
            query_params={"param1": "value1", "param2": "value2"},
            tenant_id="test-tenant",
            client_ip="192.168.1.100",
            user_agent="TestAgent/1.0",
            request_id=request_id,
            content_length=100,
        )

        assert request.method == HttpMethod.GET
        assert request.path == "/api/test"
        assert request.headers["Authorization"] == "Bearer token"
        assert request.body == '{"key": "value"}'
        assert request.query_params["param1"] == "value1"
        assert request.tenant_id == "test-tenant"
        assert request.client_ip == "192.168.1.100"
        assert request.user_agent == "TestAgent/1.0"
        assert request.request_id == request_id
        assert request.content_length == 100

    def test_gateway_request_minimal(self):
        """Test creating a minimal gateway request."""
        request = GatewayRequest(
            method=HttpMethod.POST,
            path="/api/minimal",
            headers={},
            body="",
            query_params={},
            tenant_id="",
            client_ip="",
            user_agent="",
            request_id="",
            content_length=0,
        )

        assert request.method == HttpMethod.POST
        assert request.path == "/api/minimal"
        assert len(request.headers) == 0
        assert request.body == ""
        assert len(request.query_params) == 0

    def test_gateway_request_with_json_body(self):
        """Test gateway request with JSON body."""
        json_body = {"user": "test", "action": "create"}
        request = GatewayRequest(
            method=HttpMethod.POST,
            path="/api/users",
            headers={"Content-Type": "application/json"},
            body=json.dumps(json_body),
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id=str(uuid4()),
            content_length=len(json.dumps(json_body)),
        )

        parsed_body = json.loads(request.body)
        assert parsed_body["user"] == "test"
        assert parsed_body["action"] == "create"

    def test_gateway_request_immutability(self):
        """Test that gateway request properties are accessible."""
        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer token"},
            body="",
            query_params={"test": "value"},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id=str(uuid4()),
            content_length=0,
        )

        # Test that we can access all properties
        assert request.method == HttpMethod.GET
        assert request.path == "/api/test"
        assert request.headers["Authorization"] == "Bearer token"
        assert request.query_params["test"] == "value"


class TestGatewayResponse:
    """Test cases for GatewayResponse."""

    def test_gateway_response_creation(self):
        """Test creating a gateway response."""
        response_body = {"result": "success", "data": {"id": 123}}
        response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "X-Custom": "value"},
            body=response_body,
        )

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/json"
        assert response.headers["X-Custom"] == "value"
        assert response.body == response_body

    def test_gateway_response_error(self):
        """Test creating an error gateway response."""
        error_body = {"error": "Not Found", "code": 404}
        response = GatewayResponse(
            status_code=404,
            headers={"Content-Type": "application/json"},
            body=error_body,
        )

        assert response.status_code == 404
        assert response.body["error"] == "Not Found"
        assert response.body["code"] == 404

    def test_gateway_response_text_body(self):
        """Test gateway response with text body."""
        response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "text/plain"},
            body="Hello, World!",
        )

        assert response.status_code == 200
        assert response.body == "Hello, World!"
        assert response.headers["Content-Type"] == "text/plain"

    def test_gateway_response_empty_body(self):
        """Test gateway response with empty body."""
        response = GatewayResponse(
            status_code=204,
            headers={},
            body="",
        )

        assert response.status_code == 204
        assert response.body == ""
        assert len(response.headers) == 0


class TestGatewayResult:
    """Test cases for GatewayResult."""

    def test_gateway_result_success(self):
        """Test successful gateway result."""
        response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"result": "success"},
        )

        result = GatewayResult(
            success=True,
            response=response,
            error=None,
            processing_time=0.05,
            cache_hit=False,
        )

        assert result.success is True
        assert result.response == response
        assert result.error is None
        assert result.processing_time == 0.05
        assert result.cache_hit is False

    def test_gateway_result_error(self):
        """Test error gateway result."""
        result = GatewayResult(
            success=False,
            response=None,
            error="Authentication failed",
            processing_time=0.01,
            cache_hit=False,
        )

        assert result.success is False
        assert result.response is None
        assert result.error == "Authentication failed"
        assert result.processing_time == 0.01

    def test_gateway_result_cache_hit(self):
        """Test gateway result with cache hit."""
        response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "X-Cache": "HIT"},
            body={"cached": "data"},
        )

        result = GatewayResult(
            success=True,
            response=response,
            error=None,
            processing_time=0.001,  # Very fast due to cache
            cache_hit=True,
        )

        assert result.success is True
        assert result.cache_hit is True
        assert result.processing_time < 0.01  # Should be very fast


class TestGatewayConfig:
    """Test cases for GatewayConfig."""

    def test_gateway_config_creation(self):
        """Test creating gateway configuration."""
        config = GatewayConfig(
            enabled=True,
            level=GatewayLevel.STANDARD,
            tenant_isolation=True,
            performance_mode=False,
            timeout_seconds=30.0,
            max_request_size=1024*1024,  # 1MB
            debug=True,
        )

        assert config.enabled is True
        assert config.level == GatewayLevel.STANDARD
        assert config.tenant_isolation is True
        assert config.performance_mode is False
        assert config.timeout_seconds == 30.0
        assert config.max_request_size == 1024*1024
        assert config.debug is True

    def test_gateway_config_defaults(self):
        """Test gateway configuration defaults."""
        config = GatewayConfig()

        assert config.enabled is True  # Default should be enabled
        assert config.level == GatewayLevel.STANDARD  # Default level
        assert config.tenant_isolation is True  # Default tenant isolation
        assert config.performance_mode is False  # Default performance mode
        assert config.timeout_seconds == 30.0  # Default timeout
        assert config.debug is False  # Default debug off

    def test_gateway_config_validation(self):
        """Test gateway configuration validation."""
        # Test valid config
        config = GatewayConfig(
            timeout_seconds=60.0,
            max_request_size=5 * 1024 * 1024,  # 5MB
        )

        assert config.timeout_seconds == 60.0
        assert config.max_request_size == 5 * 1024 * 1024

        # Test negative timeout should be handled by validation
        with pytest.raises(ValueError):
            GatewayConfig(timeout_seconds=-1.0)

        # Test zero max request size should be handled by validation
        with pytest.raises(ValueError):
            GatewayConfig(max_request_size=0)


class TestGatewaySettings:
    """Test cases for GatewaySettings."""

    def test_gateway_settings_creation(self):
        """Test creating gateway settings."""
        config = GatewayConfig(level=GatewayLevel.ADVANCED)

        settings = GatewaySettings(
            config=config,
            rate_limit_enabled=True,
            auth_enabled=True,
            cache_enabled=True,
            analytics_enabled=True,
            security_enabled=True,
        )

        assert settings.config == config
        assert settings.rate_limit_enabled is True
        assert settings.auth_enabled is True
        assert settings.cache_enabled is True
        assert settings.analytics_enabled is True
        assert settings.security_enabled is True

    def test_gateway_settings_defaults(self):
        """Test gateway settings defaults."""
        settings = GatewaySettings()

        # Should have default config
        assert settings.config is not None
        assert isinstance(settings.config, GatewayConfig)

        # Default feature enablement
        assert settings.rate_limit_enabled is True
        assert settings.auth_enabled is True
        assert settings.cache_enabled is True
        assert settings.analytics_enabled is True
        assert settings.security_enabled is True

    def test_gateway_settings_feature_toggling(self):
        """Test gateway settings feature toggling."""
        settings = GatewaySettings(
            rate_limit_enabled=False,
            auth_enabled=False,
            cache_enabled=True,
            analytics_enabled=False,
            security_enabled=True,
        )

        assert settings.rate_limit_enabled is False
        assert settings.auth_enabled is False
        assert settings.cache_enabled is True
        assert settings.analytics_enabled is False
        assert settings.security_enabled is True

    def test_gateway_settings_with_custom_config(self):
        """Test gateway settings with custom config."""
        custom_config = GatewayConfig(
            level=GatewayLevel.ENTERPRISE,
            performance_mode=True,
            timeout_seconds=60.0,
        )

        settings = GatewaySettings(
            config=custom_config,
            cache_enabled=False,
        )

        assert settings.config.level == GatewayLevel.ENTERPRISE
        assert settings.config.performance_mode is True
        assert settings.config.timeout_seconds == 60.0
        assert settings.cache_enabled is False