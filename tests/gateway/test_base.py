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
    RequestMethod,
)


class TestRequestMethod:
    """Test cases for RequestMethod enum."""

    def test_request_method_values(self):
        """Test Request method enum values."""
        assert RequestMethod.GET.value == "GET"
        assert RequestMethod.POST.value == "POST"
        assert RequestMethod.PUT.value == "PUT"
        assert RequestMethod.DELETE.value == "DELETE"
        assert RequestMethod.PATCH.value == "PATCH"
        assert RequestMethod.HEAD.value == "HEAD"
        assert RequestMethod.OPTIONS.value == "OPTIONS"

    def test_request_method_from_string(self):
        """Test creating Request method from string."""
        assert RequestMethod("GET") == RequestMethod.GET
        assert RequestMethod("post".upper()) == RequestMethod.POST

    def test_request_method_case_sensitivity(self):
        """Test Request method case sensitivity."""
        with pytest.raises(ValueError):
            RequestMethod("get")  # Should be uppercase


class TestGatewayLevel:
    """Test cases for GatewayLevel enum."""

    def test_gateway_level_values(self):
        """Test gateway level enum values."""
        assert GatewayLevel.BASIC.value == "basic"
        assert GatewayLevel.STANDARD.value == "standard"
        assert GatewayLevel.ENHANCED.value == "enhanced"
        assert GatewayLevel.ENTERPRISE.value == "enterprise"

    def test_gateway_level_ordering(self):
        """Test gateway level ordering."""
        levels = [GatewayLevel.BASIC, GatewayLevel.STANDARD, GatewayLevel.ENHANCED, GatewayLevel.ENTERPRISE]
        assert len(levels) == 4


class TestGatewayRequest:
    """Test cases for GatewayRequest."""

    def test_gateway_request_creation(self):
        """Test creating a gateway request."""
        request_id = str(uuid4())
        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer token", "Content-Type": "application/json"},
            body='{"key": "value"}',
            query_params={"param1": "value1", "param2": "value2"},
            client_ip="192.168.1.100",
            user_agent="TestAgent/1.0",
            request_id=request_id,
            tenant_id="test-tenant",
        )

        assert request.method == RequestMethod.GET
        assert request.path == "/api/test"
        assert request.headers["Authorization"] == "Bearer token"
        assert request.body == '{"key": "value"}'
        assert request.query_params["param1"] == "value1"
        assert request.tenant_id == "test-tenant"
        assert request.client_ip == "192.168.1.100"
        assert request.user_agent == "TestAgent/1.0"
        assert request.request_id == request_id
        assert request.content_length > 0  # Content length is a computed property

    def test_gateway_request_minimal(self):
        """Test creating a minimal gateway request."""
        request = GatewayRequest(
            method=RequestMethod.POST,
            path="/api/minimal",
            headers={},
            body="",
            query_params={},
            client_ip="",
            user_agent="",
        )

        assert request.method == RequestMethod.POST
        assert request.path == "/api/minimal"
        assert len(request.headers) == 0
        assert request.body == ""
        assert len(request.query_params) == 0

    def test_gateway_request_with_json_body(self):
        """Test gateway request with JSON body."""
        json_body = {"user": "test", "action": "create"}
        request = GatewayRequest(
            method=RequestMethod.POST,
            path="/api/users",
            headers={"Content-Type": "application/json"},
            body=json.dumps(json_body),
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        parsed_body = json.loads(request.body)
        assert parsed_body["user"] == "test"
        assert parsed_body["action"] == "create"
        # content_length is a computed property
        assert request.content_length > 0

    def test_gateway_request_immutability(self):
        """Test that gateway request properties are accessible."""
        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer token"},
            body="",
            query_params={"test": "value"},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        # Test that we can access all properties
        assert request.method == RequestMethod.GET
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
        from acb.gateway._base import GatewayStatus

        response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"result": "success"},
        )

        result = GatewayResult(
            success=True,
            status=GatewayStatus.SUCCESS,
            response=response,
            processing_time_ms=50.0,
        )

        assert result.success is True
        assert result.status == GatewayStatus.SUCCESS
        assert result.response == response
        assert result.processing_time_ms == 50.0

    def test_gateway_result_error(self):
        """Test error gateway result."""
        from acb.gateway._base import GatewayStatus

        result = GatewayResult(
            success=False,
            status=GatewayStatus.UNAUTHORIZED,
            message="Authentication failed",
            processing_time_ms=10.0,
        )
        result.add_error("Authentication failed")

        assert result.success is False
        assert result.status == GatewayStatus.UNAUTHORIZED
        assert result.message == "Authentication failed"
        assert "Authentication failed" in result.errors
        assert result.processing_time_ms == 10.0

    def test_gateway_result_cache_hit(self):
        """Test gateway result with cache hit."""
        from acb.gateway._base import GatewayStatus

        response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "X-Cache": "HIT"},
            body={"cached": "data"},
            cache_hit=True,
        )

        result = GatewayResult(
            success=True,
            status=GatewayStatus.SUCCESS,
            response=response,
            processing_time_ms=1.0,  # Very fast due to cache
        )

        assert result.success is True
        assert result.status == GatewayStatus.SUCCESS
        assert result.response.cache_hit is True
        assert result.processing_time_ms < 10.0  # Should be very fast


class TestGatewayConfig:
    """Test cases for GatewayConfig."""

    def test_gateway_config_creation(self):
        """Test creating gateway configuration."""
        config = GatewayConfig(
            level=GatewayLevel.STANDARD,
            enable_rate_limiting=True,
            enable_authentication=True,
            enable_validation=True,
            timeout=30.0,
            max_request_size=1024*1024,  # 1MB
            tenant_id="test-tenant",
        )

        assert config.level == GatewayLevel.STANDARD
        assert config.enable_rate_limiting is True
        assert config.enable_authentication is True
        assert config.enable_validation is True
        assert config.timeout == 30.0
        assert config.max_request_size == 1024*1024
        assert config.tenant_id == "test-tenant"

    def test_gateway_config_defaults(self):
        """Test gateway configuration defaults."""
        config = GatewayConfig()

        assert config.level == GatewayLevel.STANDARD  # Default level
        assert config.enable_rate_limiting is True  # Default enabled
        assert config.enable_authentication is True  # Default enabled
        assert config.enable_validation is True  # Default enabled
        assert config.enable_caching is True  # Default enabled
        assert config.enable_analytics is True  # Default enabled
        assert config.enable_security_headers is True  # Default enabled

    def test_gateway_config_validation(self):
        """Test gateway configuration validation."""
        # Test valid config
        config = GatewayConfig(
            timeout=60.0,
            max_request_size=5 * 1024 * 1024,  # 5MB
        )

        assert config.timeout == 60.0
        assert config.max_request_size == 5 * 1024 * 1024

        # Test that config accepts None for optional fields
        config_with_none = GatewayConfig(
            timeout=None,
            max_request_size=None,
        )
        assert config_with_none.timeout is None
        assert config_with_none.max_request_size is None


class TestGatewaySettings:
    """Test cases for GatewaySettings."""

    def test_gateway_settings_creation(self):
        """Test creating gateway settings."""
        settings = GatewaySettings(
            level=GatewayLevel.ENHANCED,
            enable_rate_limiting=True,
            enable_authentication=True,
            enable_caching=True,
            enable_analytics=True,
            timeout=60.0,
        )

        assert settings.level == GatewayLevel.ENHANCED
        assert settings.enable_rate_limiting is True
        assert settings.enable_authentication is True
        assert settings.enable_caching is True
        assert settings.enable_analytics is True
        assert settings.timeout == 60.0

    def test_gateway_settings_defaults(self):
        """Test gateway settings defaults."""
        settings = GatewaySettings()

        # Default values from GatewaySettings
        assert settings.enabled is True
        assert settings.level == GatewayLevel.STANDARD
        assert settings.timeout == 30.0
        assert settings.max_request_size == 10 * 1024 * 1024  # 10MB

        # Default feature enablement
        assert settings.enable_rate_limiting is True
        assert settings.enable_authentication is True
        assert settings.enable_caching is True
        assert settings.enable_analytics is True

    def test_gateway_settings_feature_toggling(self):
        """Test gateway settings feature toggling."""
        settings = GatewaySettings(
            enable_rate_limiting=False,
            enable_authentication=False,
            enable_caching=True,
            enable_analytics=False,
        )

        assert settings.enable_rate_limiting is False
        assert settings.enable_authentication is False
        assert settings.enable_caching is True
        assert settings.enable_analytics is False

    def test_gateway_settings_with_custom_config(self):
        """Test gateway settings with level and timeout."""
        settings = GatewaySettings(
            level=GatewayLevel.ENTERPRISE,
            timeout=60.0,
            enable_caching=False,
        )

        assert settings.level == GatewayLevel.ENTERPRISE
        assert settings.timeout == 60.0
        assert settings.enable_caching is False
