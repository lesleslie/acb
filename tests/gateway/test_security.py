"""Tests for Security functionality."""

import re
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.gateway.security import (
    CORSConfig,
    CORSManager,
    CORSMethod,
    SecurityConfig,
    SecurityHeaders,
    SecurityHeadersManager,
    SecurityLevel,
    SecurityManager,
    SecurityValidator,
    SecurityViolation,
)
from acb.gateway._base import GatewayRequest, GatewayResponse, HttpMethod


@pytest.fixture
def security_headers_config():
    """Security headers configuration."""
    return SecurityHeaders(
        enable_hsts=True,
        hsts_max_age=31536000,
        enable_csp=True,
        csp_default_src=["'self'"],
        enable_frame_options=True,
        frame_options="DENY",
    )


@pytest.fixture
def cors_config():
    """CORS configuration."""
    return CORSConfig(
        enabled=True,
        allowed_origins=["https://example.com", "https://api.example.com"],
        allowed_methods=[CORSMethod.GET, CORSMethod.POST],
        allowed_headers=["Content-Type", "Authorization"],
        allow_credentials=True,
    )


@pytest.fixture
def security_config(security_headers_config, cors_config):
    """Security configuration."""
    return SecurityConfig(
        level=SecurityLevel.STANDARD,
        enabled=True,
        headers=security_headers_config,
        cors=cors_config,
        enable_request_validation=True,
        max_request_size=1024 * 1024,  # 1MB
        block_suspicious_user_agents=True,
    )


@pytest.fixture
def mock_request():
    """Mock gateway request."""
    return GatewayRequest(
        method=HttpMethod.GET,
        path="/api/test",
        headers={"User-Agent": "test-agent", "Origin": "https://example.com"},
        body="",
        query_params={},
        tenant_id="test-tenant",
        client_ip="127.0.0.1",
        user_agent="test-agent",
        request_id="test-request",
        content_length=100,
    )


@pytest.fixture
def mock_response():
    """Mock gateway response."""
    return GatewayResponse(
        status_code=200,
        headers={},
        body={"result": "success"},
    )


class TestSecurityHeadersManager:
    """Test cases for SecurityHeadersManager."""

    def test_apply_security_headers(self, security_headers_config, mock_response):
        """Test applying security headers to response."""
        manager = SecurityHeadersManager(security_headers_config)
        manager.apply_security_headers(mock_response)

        headers = mock_response.headers

        # Check HSTS header
        assert "Strict-Transport-Security" in headers
        assert "max-age=31536000" in headers["Strict-Transport-Security"]

        # Check CSP header
        assert "Content-Security-Policy" in headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]

        # Check X-Frame-Options
        assert headers["X-Frame-Options"] == "DENY"

    def test_apply_csp_with_multiple_directives(self, security_headers_config, mock_response):
        """Test CSP with multiple directives."""
        security_headers_config.csp_script_src = ["'self'", "'unsafe-inline'"]
        security_headers_config.csp_style_src = ["'self'", "https://fonts.googleapis.com"]

        manager = SecurityHeadersManager(security_headers_config)
        manager.apply_security_headers(mock_response)

        csp_header = mock_response.headers["Content-Security-Policy"]
        assert "script-src 'self' 'unsafe-inline'" in csp_header
        assert "style-src 'self' https://fonts.googleapis.com" in csp_header

    def test_apply_permissions_policy(self, security_headers_config, mock_response):
        """Test permissions policy header."""
        security_headers_config.enable_permissions_policy = True
        security_headers_config.permissions_policy = {
            "camera": [],
            "microphone": ["'self'"],
            "geolocation": ["'self'", "https://maps.example.com"],
        }

        manager = SecurityHeadersManager(security_headers_config)
        manager.apply_security_headers(mock_response)

        permissions_header = mock_response.headers["Permissions-Policy"]
        assert "camera=()" in permissions_header
        assert "microphone=('self')" in permissions_header
        assert "geolocation=('self' https://maps.example.com)" in permissions_header

    def test_apply_custom_headers(self, security_headers_config, mock_response):
        """Test custom security headers."""
        security_headers_config.custom_headers = {
            "X-Custom-Security": "enabled",
            "X-Rate-Limit": "1000/hour",
        }

        manager = SecurityHeadersManager(security_headers_config)
        manager.apply_security_headers(mock_response)

        assert mock_response.headers["X-Custom-Security"] == "enabled"
        assert mock_response.headers["X-Rate-Limit"] == "1000/hour"

    def test_disabled_headers(self, security_headers_config, mock_response):
        """Test disabled security headers."""
        security_headers_config.enable_hsts = False
        security_headers_config.enable_csp = False

        manager = SecurityHeadersManager(security_headers_config)
        manager.apply_security_headers(mock_response)

        assert "Strict-Transport-Security" not in mock_response.headers
        assert "Content-Security-Policy" not in mock_response.headers


class TestCORSManager:
    """Test cases for CORSManager."""

    def test_handle_preflight_request_success(self, cors_config, mock_request):
        """Test successful CORS preflight handling."""
        mock_request.method = HttpMethod.OPTIONS
        mock_request.headers["access-control-request-method"] = "POST"
        mock_request.headers["access-control-request-headers"] = "Content-Type,Authorization"

        manager = CORSManager(cors_config)
        response = manager.handle_preflight_request(mock_request)

        assert response is not None
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers

    def test_handle_preflight_request_invalid_origin(self, cors_config, mock_request):
        """Test CORS preflight with invalid origin."""
        mock_request.method = HttpMethod.OPTIONS
        mock_request.headers["origin"] = "https://evil.com"

        manager = CORSManager(cors_config)
        response = manager.handle_preflight_request(mock_request)

        assert response is not None
        assert response.status_code == 403

    def test_handle_preflight_request_invalid_method(self, cors_config, mock_request):
        """Test CORS preflight with invalid method."""
        mock_request.method = HttpMethod.OPTIONS
        mock_request.headers["access-control-request-method"] = "DELETE"

        manager = CORSManager(cors_config)
        response = manager.handle_preflight_request(mock_request)

        assert response is not None
        assert response.status_code == 403

    def test_apply_cors_headers(self, cors_config, mock_request, mock_response):
        """Test applying CORS headers to response."""
        manager = CORSManager(cors_config)
        manager.apply_cors_headers(mock_response, mock_request)

        assert mock_response.headers["Access-Control-Allow-Origin"] == "https://example.com"
        assert "GET, POST" in mock_response.headers["Access-Control-Allow-Methods"]
        assert mock_response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_apply_cors_headers_wildcard_origin(self, cors_config, mock_request, mock_response):
        """Test CORS headers with wildcard origin."""
        cors_config.allowed_origins = ["*"]
        cors_config.allow_credentials = False

        manager = CORSManager(cors_config)
        manager.apply_cors_headers(mock_response, mock_request)

        assert mock_response.headers["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Credentials" not in mock_response.headers

    def test_origin_pattern_matching(self, cors_config, mock_request):
        """Test origin pattern matching."""
        cors_config.allowed_origins = []
        cors_config.allowed_origin_patterns = [r"https://.*\.example\.com"]

        mock_request.headers["origin"] = "https://api.example.com"

        manager = CORSManager(cors_config)
        allowed = manager._is_origin_allowed("https://api.example.com", cors_config)

        assert allowed is True

        # Test non-matching pattern
        allowed = manager._is_origin_allowed("https://evil.com", cors_config)
        assert allowed is False

    def test_tenant_specific_cors(self, cors_config, mock_request, mock_response):
        """Test tenant-specific CORS configuration."""
        cors_config.tenant_specific_cors = {
            "tenant1": {
                "allowed_origins": ["https://tenant1.com"],
                "allow_credentials": False,
            }
        }

        manager = CORSManager(cors_config)
        tenant_config = manager._get_tenant_cors_config("tenant1")

        assert "https://tenant1.com" in tenant_config.allowed_origins
        assert tenant_config.allow_credentials is False

    def test_cors_disabled(self, cors_config, mock_request):
        """Test CORS when disabled."""
        cors_config.enabled = False

        manager = CORSManager(cors_config)
        response = manager.handle_preflight_request(mock_request)

        assert response is None


class TestSecurityValidator:
    """Test cases for SecurityValidator."""

    @pytest.mark.asyncio
    async def test_validate_request_success(self, security_config, mock_request):
        """Test successful request validation."""
        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_validate_request_size_violation(self, security_config, mock_request):
        """Test request size violation."""
        mock_request.content_length = 2 * 1024 * 1024  # 2MB, exceeds 1MB limit

        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 1
        assert violations[0].violation_type == "request_size"
        assert violations[0].severity == "medium"

    @pytest.mark.asyncio
    async def test_validate_suspicious_user_agent(self, security_config, mock_request):
        """Test suspicious user agent detection."""
        mock_request.user_agent = "sqlmap/1.0"

        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 1
        assert violations[0].violation_type == "suspicious_user_agent"
        assert violations[0].severity == "high"

    @pytest.mark.asyncio
    async def test_validate_blocked_ip(self, security_config, mock_request):
        """Test blocked IP detection."""
        security_config.enable_ip_filtering = True
        security_config.blocked_ips = ["127.0.0.1"]

        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 1
        assert violations[0].violation_type == "blocked_ip"
        assert violations[0].severity == "high"

    @pytest.mark.asyncio
    async def test_validate_ip_not_allowed(self, security_config, mock_request):
        """Test IP not in allow list."""
        security_config.enable_ip_filtering = True
        security_config.allowed_ips = ["192.168.1.1"]

        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 1
        assert violations[0].violation_type == "ip_not_allowed"
        assert violations[0].severity == "medium"

    @pytest.mark.asyncio
    async def test_validate_path_traversal_attack(self, security_config, mock_request):
        """Test path traversal attack detection."""
        mock_request.path = "/api/../../../etc/passwd"

        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 1
        assert violations[0].violation_type == "path_traversal"
        assert violations[0].severity == "medium"

    @pytest.mark.asyncio
    async def test_validate_xss_attempt(self, security_config, mock_request):
        """Test XSS attempt detection."""
        mock_request.path = "/api/search?q=<script>alert('xss')</script>"

        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 1
        assert violations[0].violation_type == "xss_attempt"
        assert violations[0].severity == "high"

    @pytest.mark.asyncio
    async def test_validate_sql_injection_attempt(self, security_config, mock_request):
        """Test SQL injection attempt detection."""
        mock_request.path = "/api/users?id=1 UNION SELECT * FROM passwords"

        validator = SecurityValidator(security_config)
        violations = await validator.validate_request(mock_request)

        assert len(violations) == 1
        assert violations[0].violation_type == "sql_injection"
        assert violations[0].severity == "critical"

    def test_get_violations_filter_by_time(self, security_config):
        """Test getting violations filtered by time."""
        validator = SecurityValidator(security_config)

        # Add some violations
        violation1 = SecurityViolation(
            violation_type="test",
            severity="low",
            description="Test violation 1",
            timestamp=time.time() - 3600,  # 1 hour ago
        )
        violation2 = SecurityViolation(
            violation_type="test",
            severity="high",
            description="Test violation 2",
            timestamp=time.time() - 1800,  # 30 minutes ago
        )

        validator._violations = [violation1, violation2]

        # Get violations since 45 minutes ago
        since = time.time() - 2700
        recent_violations = validator.get_violations(since=since)

        assert len(recent_violations) == 1
        assert recent_violations[0].description == "Test violation 2"

    def test_get_violations_filter_by_severity(self, security_config):
        """Test getting violations filtered by severity."""
        validator = SecurityValidator(security_config)

        violation1 = SecurityViolation(
            violation_type="test",
            severity="low",
            description="Low severity violation",
        )
        violation2 = SecurityViolation(
            violation_type="test",
            severity="high",
            description="High severity violation",
        )

        validator._violations = [violation1, violation2]

        high_violations = validator.get_violations(severity="high")

        assert len(high_violations) == 1
        assert high_violations[0].description == "High severity violation"


class TestSecurityManager:
    """Test cases for SecurityManager."""

    @pytest.mark.asyncio
    async def test_handle_preflight_request(self, security_config, mock_request):
        """Test CORS preflight request handling."""
        mock_request.method = HttpMethod.OPTIONS

        manager = SecurityManager(security_config)
        response = await manager.handle_preflight_request(mock_request)

        assert response is not None
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_request_security(self, security_config, mock_request):
        """Test request security validation."""
        manager = SecurityManager(security_config)
        violations = await manager.validate_request_security(mock_request)

        # Should be no violations for normal request
        assert len(violations) == 0

    def test_apply_security_headers(self, security_config, mock_request, mock_response):
        """Test applying security headers."""
        manager = SecurityManager(security_config)
        manager.apply_security_headers(mock_response, mock_request)

        # Check that security headers are applied
        assert "Strict-Transport-Security" in mock_response.headers
        assert "Content-Security-Policy" in mock_response.headers
        assert "X-Frame-Options" in mock_response.headers

        # Check that CORS headers are applied
        assert "Access-Control-Allow-Origin" in mock_response.headers

    def test_is_request_blocked_critical_violation(self, security_config):
        """Test request blocking on critical violation."""
        manager = SecurityManager(security_config)

        violations = [
            SecurityViolation(
                violation_type="sql_injection",
                severity="critical",
                description="Critical SQL injection attempt",
            )
        ]

        assert manager.is_request_blocked(violations) is True

    def test_is_request_blocked_multiple_high_violations(self, security_config):
        """Test request blocking on multiple high severity violations."""
        manager = SecurityManager(security_config)

        violations = [
            SecurityViolation(
                violation_type="xss_attempt",
                severity="high",
                description="XSS attempt",
            ),
            SecurityViolation(
                violation_type="suspicious_user_agent",
                severity="high",
                description="Suspicious user agent",
            ),
        ]

        assert manager.is_request_blocked(violations) is True

    def test_is_request_blocked_single_high_violation(self, security_config):
        """Test request not blocked on single high severity violation."""
        manager = SecurityManager(security_config)

        violations = [
            SecurityViolation(
                violation_type="suspicious_user_agent",
                severity="high",
                description="Suspicious user agent",
            )
        ]

        assert manager.is_request_blocked(violations) is False

    def test_is_request_blocked_no_violations(self, security_config):
        """Test request not blocked when no violations."""
        manager = SecurityManager(security_config)

        assert manager.is_request_blocked([]) is False

    def test_get_security_violations(self, security_config):
        """Test getting security violations."""
        manager = SecurityManager(security_config)

        # Add some violations directly to validator
        violation = SecurityViolation(
            violation_type="test",
            severity="medium",
            description="Test violation",
        )
        manager._validator._violations = [violation]

        violations = manager.get_security_violations()

        assert len(violations) == 1
        assert violations[0].description == "Test violation"

    def test_clear_security_violations(self, security_config):
        """Test clearing security violations."""
        manager = SecurityManager(security_config)

        # Add violation
        violation = SecurityViolation(
            violation_type="test",
            severity="medium",
            description="Test violation",
        )
        manager._validator._violations = [violation]

        # Clear violations
        manager.clear_security_violations()

        violations = manager.get_security_violations()
        assert len(violations) == 0