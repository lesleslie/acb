"""Security headers and CORS management for ACB Gateway.

This module provides comprehensive security management including:
- Security headers enforcement (HSTS, CSP, X-Frame-Options, etc.)
- CORS policy management and enforcement
- Content security policy management
- Security headers validation
- Request security scanning
- Response security enforcement

Features:
- Comprehensive security headers
- Flexible CORS configuration
- Content Security Policy management
- Security policy validation
- Multi-tenant security isolation
- Security audit logging
"""

from __future__ import annotations

import re
import typing as t
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field
from acb.gateway._base import GatewayRequest, GatewayResponse


class SecurityLevel(Enum):
    """Security enforcement levels."""

    BASIC = "basic"        # Basic security headers
    STANDARD = "standard"  # Standard security headers + CORS
    STRICT = "strict"      # Strict security headers + CSP
    PARANOID = "paranoid"  # Maximum security enforcement


class CORSMethod(Enum):
    """CORS allowed methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class SecurityViolation:
    """Security violation record."""

    violation_type: str
    severity: str  # low, medium, high, critical
    description: str
    source_ip: str | None = None
    user_agent: str | None = None
    request_path: str | None = None
    timestamp: float = field(default_factory=lambda: __import__('time').time())

    # Additional context
    headers: dict[str, str] = field(default_factory=dict)
    payload_sample: str | None = None
    mitigation_applied: str | None = None


class SecurityHeaders(BaseModel):
    """Security headers configuration."""

    # HSTS (HTTP Strict Transport Security)
    enable_hsts: bool = True
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    # Content Security Policy
    enable_csp: bool = True
    csp_default_src: list[str] = Field(default_factory=lambda: ["'self'"])
    csp_script_src: list[str] = Field(default_factory=lambda: ["'self'"])
    csp_style_src: list[str] = Field(default_factory=lambda: ["'self'", "'unsafe-inline'"])
    csp_img_src: list[str] = Field(default_factory=lambda: ["'self'", "data:", "https:"])
    csp_font_src: list[str] = Field(default_factory=lambda: ["'self'"])
    csp_connect_src: list[str] = Field(default_factory=lambda: ["'self'"])
    csp_media_src: list[str] = Field(default_factory=lambda: ["'self'"])
    csp_object_src: list[str] = Field(default_factory=lambda: ["'none'"])
    csp_frame_src: list[str] = Field(default_factory=lambda: ["'none'"])
    csp_report_uri: str | None = None

    # Frame options
    enable_frame_options: bool = True
    frame_options: str = "DENY"  # DENY, SAMEORIGIN, ALLOW-FROM

    # Content type options
    enable_content_type_options: bool = True
    content_type_options: str = "nosniff"

    # XSS Protection
    enable_xss_protection: bool = True
    xss_protection: str = "1; mode=block"

    # Referrer Policy
    enable_referrer_policy: bool = True
    referrer_policy: str = "strict-origin-when-cross-origin"

    # Permissions Policy
    enable_permissions_policy: bool = True
    permissions_policy: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "camera": [],
            "microphone": [],
            "geolocation": [],
            "payment": [],
        }
    )

    # Additional security headers
    custom_headers: dict[str, str] = Field(default_factory=dict)

    class Config:
        extra = "forbid"


class CORSConfig(BaseModel):
    """CORS configuration."""

    # Basic CORS settings
    enabled: bool = True
    allow_credentials: bool = False

    # Allowed origins
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])
    allowed_origin_patterns: list[str] = Field(default_factory=list)

    # Allowed methods
    allowed_methods: list[CORSMethod] = Field(
        default_factory=lambda: [
            CORSMethod.GET,
            CORSMethod.POST,
            CORSMethod.PUT,
            CORSMethod.DELETE,
            CORSMethod.PATCH,
            CORSMethod.HEAD,
            CORSMethod.OPTIONS,
        ]
    )

    # Allowed headers
    allowed_headers: list[str] = Field(
        default_factory=lambda: [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
        ]
    )

    # Exposed headers
    exposed_headers: list[str] = Field(default_factory=list)

    # Preflight settings
    max_age: int = 86400  # 24 hours
    preflight_continue: bool = False

    # Per-tenant CORS
    tenant_specific_cors: dict[str, dict[str, t.Any]] = Field(default_factory=dict)

    class Config:
        extra = "forbid"


class SecurityConfig(BaseModel):
    """Security configuration."""

    # Security level
    level: SecurityLevel = SecurityLevel.STANDARD
    enabled: bool = True

    # Security headers
    headers: SecurityHeaders = Field(default_factory=SecurityHeaders)

    # CORS configuration
    cors: CORSConfig = Field(default_factory=CORSConfig)

    # Request validation
    enable_request_validation: bool = True
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    block_suspicious_user_agents: bool = True
    suspicious_user_agents: list[str] = Field(
        default_factory=lambda: [
            r".*bot.*",
            r".*crawler.*",
            r".*scanner.*",
            r".*nikto.*",
            r".*sqlmap.*",
        ]
    )

    # IP filtering
    enable_ip_filtering: bool = False
    allowed_ips: list[str] = Field(default_factory=list)
    blocked_ips: list[str] = Field(default_factory=list)
    trusted_proxies: list[str] = Field(default_factory=list)

    # Rate limiting integration
    security_rate_limiting: bool = True
    violation_rate_limit: int = 10  # violations per hour

    # Audit logging
    enable_audit_logging: bool = True
    log_all_requests: bool = False
    log_security_events: bool = True

    class Config:
        extra = "forbid"


class SecurityHeadersManager:
    """Security headers management."""

    def __init__(self, config: SecurityHeaders) -> None:
        self._config = config

    def apply_security_headers(self, response: GatewayResponse) -> None:
        """Apply security headers to response."""
        headers = response.headers

        self._apply_hsts_header(headers)
        self._apply_csp_header(headers)
        self._apply_standard_security_headers(headers)
        self._apply_permissions_policy(headers)
        self._apply_custom_headers(headers)

    def _apply_hsts_header(self, headers: dict[str, str]) -> None:
        """Apply HSTS header."""
        if not self._config.enable_hsts:
            return

        hsts_value = f"max-age={self._config.hsts_max_age}"
        if self._config.hsts_include_subdomains:
            hsts_value += "; includeSubDomains"
        if self._config.hsts_preload:
            hsts_value += "; preload"
        headers["Strict-Transport-Security"] = hsts_value

    def _apply_csp_header(self, headers: dict[str, str]) -> None:
        """Apply Content Security Policy header."""
        if not self._config.enable_csp:
            return

        csp_directives = []

        csp_mappings = [
            ("default-src", self._config.csp_default_src),
            ("script-src", self._config.csp_script_src),
            ("style-src", self._config.csp_style_src),
            ("img-src", self._config.csp_img_src),
            ("font-src", self._config.csp_font_src),
            ("connect-src", self._config.csp_connect_src),
            ("media-src", self._config.csp_media_src),
            ("object-src", self._config.csp_object_src),
            ("frame-src", self._config.csp_frame_src),
        ]

        for directive, sources in csp_mappings:
            if sources:
                csp_directives.append(f"{directive} {' '.join(sources)}")

        if self._config.csp_report_uri:
            csp_directives.append(f"report-uri {self._config.csp_report_uri}")

        if csp_directives:
            headers["Content-Security-Policy"] = "; ".join(csp_directives)

    def _apply_standard_security_headers(self, headers: dict[str, str]) -> None:
        """Apply standard security headers."""
        if self._config.enable_frame_options:
            headers["X-Frame-Options"] = self._config.frame_options

        if self._config.enable_content_type_options:
            headers["X-Content-Type-Options"] = self._config.content_type_options

        if self._config.enable_xss_protection:
            headers["X-XSS-Protection"] = self._config.xss_protection

        if self._config.enable_referrer_policy:
            headers["Referrer-Policy"] = self._config.referrer_policy

    def _apply_permissions_policy(self, headers: dict[str, str]) -> None:
        """Apply Permissions Policy header."""
        if not self._config.enable_permissions_policy:
            return

        permissions_directives = []
        for feature, allowed_origins in self._config.permissions_policy.items():
            if allowed_origins:
                permissions_directives.append(f"{feature}=({' '.join(allowed_origins)})")
            else:
                permissions_directives.append(f"{feature}=()")

        if permissions_directives:
            headers["Permissions-Policy"] = ", ".join(permissions_directives)

    def _apply_custom_headers(self, headers: dict[str, str]) -> None:
        """Apply custom security headers."""
        for header_name, header_value in self._config.custom_headers.items():
            headers[header_name] = header_value


class CORSManager:
    """CORS policy management."""

    def __init__(self, config: CORSConfig) -> None:
        self._config = config

    def handle_preflight_request(
        self,
        request: GatewayRequest,
        tenant_id: str | None = None,
    ) -> GatewayResponse | None:
        """Handle CORS preflight request."""
        if not self._config.enabled:
            return None

        if request.method.value != "OPTIONS":
            return None

        # Get tenant-specific CORS config if available
        cors_config = self._get_tenant_cors_config(tenant_id)

        # Check origin
        origin = request.headers.get("origin")
        if not self._is_origin_allowed(origin, cors_config):
            return self._create_cors_error_response("Origin not allowed")

        # Check requested method
        requested_method = request.headers.get("access-control-request-method")
        if requested_method and not self._is_method_allowed(requested_method, cors_config):
            return self._create_cors_error_response("Method not allowed")

        # Check requested headers
        requested_headers = request.headers.get("access-control-request-headers")
        if requested_headers and not self._are_headers_allowed(requested_headers, cors_config):
            return self._create_cors_error_response("Headers not allowed")

        # Create preflight response
        response = GatewayResponse(
            status_code=200,
            headers={},
            body="",
        )

        self._apply_cors_headers(response, request, cors_config)
        return response

    def apply_cors_headers(
        self,
        response: GatewayResponse,
        request: GatewayRequest,
        tenant_id: str | None = None,
    ) -> None:
        """Apply CORS headers to response."""
        if not self._config.enabled:
            return

        cors_config = self._get_tenant_cors_config(tenant_id)
        self._apply_cors_headers(response, request, cors_config)

    def _apply_cors_headers(
        self,
        response: GatewayResponse,
        request: GatewayRequest,
        cors_config: CORSConfig,
    ) -> None:
        """Apply CORS headers to response."""
        origin = request.headers.get("origin")

        # Access-Control-Allow-Origin
        if self._is_origin_allowed(origin, cors_config):
            if "*" in cors_config.allowed_origins and not cors_config.allow_credentials:
                response.headers["Access-Control-Allow-Origin"] = "*"
            elif origin:
                response.headers["Access-Control-Allow-Origin"] = origin

        # Access-Control-Allow-Credentials
        if cors_config.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        # Access-Control-Allow-Methods
        if cors_config.allowed_methods:
            methods = [method.value for method in cors_config.allowed_methods]
            response.headers["Access-Control-Allow-Methods"] = ", ".join(methods)

        # Access-Control-Allow-Headers
        if cors_config.allowed_headers:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(cors_config.allowed_headers)

        # Access-Control-Expose-Headers
        if cors_config.exposed_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(cors_config.exposed_headers)

        # Access-Control-Max-Age
        if request.method.value == "OPTIONS":
            response.headers["Access-Control-Max-Age"] = str(cors_config.max_age)

    def _is_origin_allowed(self, origin: str | None, cors_config: CORSConfig) -> bool:
        """Check if origin is allowed."""
        if not origin:
            return True  # Same-origin requests

        # Check exact matches
        if "*" in cors_config.allowed_origins:
            return True

        if origin in cors_config.allowed_origins:
            return True

        # Check pattern matches
        for pattern in cors_config.allowed_origin_patterns:
            try:
                if re.match(pattern, origin):
                    return True
            except re.error:
                continue

        return False

    def _is_method_allowed(self, method: str, cors_config: CORSConfig) -> bool:
        """Check if method is allowed."""
        method_enum = CORSMethod(method.upper())
        return method_enum in cors_config.allowed_methods

    def _are_headers_allowed(self, headers: str, cors_config: CORSConfig) -> bool:
        """Check if headers are allowed."""
        requested_headers = [h.strip().lower() for h in headers.split(",")]
        allowed_headers = [h.lower() for h in cors_config.allowed_headers]

        return all(header in allowed_headers for header in requested_headers)

    def _get_tenant_cors_config(self, tenant_id: str | None) -> CORSConfig:
        """Get CORS config for tenant."""
        if tenant_id and tenant_id in self._config.tenant_specific_cors:
            tenant_cors = self._config.tenant_specific_cors[tenant_id]
            # Merge with base config
            config_dict = self._config.model_dump()
            config_dict.update(tenant_cors)
            return CORSConfig(**config_dict)

        return self._config

    def _create_cors_error_response(self, message: str) -> GatewayResponse:
        """Create CORS error response."""
        return GatewayResponse(
            status_code=403,
            headers={"Content-Type": "application/json"},
            body={"error": "CORS policy violation", "message": message},
        )


class SecurityValidator:
    """Security validation and scanning."""

    def __init__(self, config: SecurityConfig) -> None:
        self._config = config
        self._violations: list[SecurityViolation] = []

    async def validate_request(self, request: GatewayRequest) -> list[SecurityViolation]:
        """Validate request for security issues."""
        violations = []

        if not self._config.enable_request_validation:
            return violations

        # Check request size
        if request.content_length > self._config.max_request_size:
            violations.append(SecurityViolation(
                violation_type="request_size",
                severity="medium",
                description=f"Request size {request.content_length} exceeds limit {self._config.max_request_size}",
                source_ip=request.client_ip,
                user_agent=request.user_agent,
                request_path=request.path,
            ))

        # Check user agent
        if self._config.block_suspicious_user_agents and request.user_agent:
            for pattern in self._config.suspicious_user_agents:
                try:
                    if re.search(pattern, request.user_agent, re.IGNORECASE):
                        violations.append(SecurityViolation(
                            violation_type="suspicious_user_agent",
                            severity="high",
                            description=f"Suspicious user agent detected: {request.user_agent}",
                            source_ip=request.client_ip,
                            user_agent=request.user_agent,
                            request_path=request.path,
                        ))
                        break
                except re.error:
                    continue

        # Check IP filtering
        if self._config.enable_ip_filtering:
            if request.client_ip:
                if request.client_ip in self._config.blocked_ips:
                    violations.append(SecurityViolation(
                        violation_type="blocked_ip",
                        severity="high",
                        description=f"Request from blocked IP: {request.client_ip}",
                        source_ip=request.client_ip,
                        user_agent=request.user_agent,
                        request_path=request.path,
                    ))

                if (self._config.allowed_ips and
                    request.client_ip not in self._config.allowed_ips and
                    request.client_ip not in self._config.trusted_proxies):
                    violations.append(SecurityViolation(
                        violation_type="ip_not_allowed",
                        severity="medium",
                        description=f"Request from non-allowed IP: {request.client_ip}",
                        source_ip=request.client_ip,
                        user_agent=request.user_agent,
                        request_path=request.path,
                    ))

        # Check for common attack patterns in URL
        attack_patterns = [
            (r"\.\.\/", "path_traversal", "medium"),
            (r"<script", "xss_attempt", "high"),
            (r"javascript:", "javascript_injection", "high"),
            (r"union.*select", "sql_injection", "critical"),
            (r"drop.*table", "sql_injection", "critical"),
            (r"exec\(", "command_injection", "critical"),
        ]

        for pattern, violation_type, severity in attack_patterns:
            try:
                if re.search(pattern, request.path, re.IGNORECASE):
                    violations.append(SecurityViolation(
                        violation_type=violation_type,
                        severity=severity,
                        description=f"Potential {violation_type} detected in path",
                        source_ip=request.client_ip,
                        user_agent=request.user_agent,
                        request_path=request.path,
                    ))
            except re.error:
                continue

        # Store violations for audit
        self._violations.extend(violations)

        return violations

    def get_violations(
        self,
        since: float | None = None,
        severity: str | None = None,
    ) -> list[SecurityViolation]:
        """Get security violations."""
        violations = self._violations

        if since:
            violations = [v for v in violations if v.timestamp >= since]

        if severity:
            violations = [v for v in violations if v.severity == severity]

        return violations

    def clear_violations(self) -> None:
        """Clear violation history."""
        self._violations.clear()


class SecurityManager:
    """Main security manager for gateway security."""

    def __init__(self, config: SecurityConfig | None = None) -> None:
        self._config = config or SecurityConfig()
        self._headers_manager = SecurityHeadersManager(self._config.headers)
        self._cors_manager = CORSManager(self._config.cors)
        self._validator = SecurityValidator(self._config)

    async def handle_preflight_request(
        self,
        request: GatewayRequest,
        tenant_id: str | None = None,
    ) -> GatewayResponse | None:
        """Handle CORS preflight request."""
        return self._cors_manager.handle_preflight_request(request, tenant_id)

    async def validate_request_security(
        self,
        request: GatewayRequest,
    ) -> list[SecurityViolation]:
        """Validate request for security issues."""
        return await self._validator.validate_request(request)

    def apply_security_headers(
        self,
        response: GatewayResponse,
        request: GatewayRequest,
        tenant_id: str | None = None,
    ) -> None:
        """Apply security headers to response."""
        # Apply security headers
        self._headers_manager.apply_security_headers(response)

        # Apply CORS headers
        self._cors_manager.apply_cors_headers(response, request, tenant_id)

    def get_security_violations(
        self,
        since: float | None = None,
        severity: str | None = None,
    ) -> list[SecurityViolation]:
        """Get security violations."""
        return self._validator.get_violations(since, severity)

    def clear_security_violations(self) -> None:
        """Clear security violation history."""
        self._validator.clear_violations()

    def is_request_blocked(self, violations: list[SecurityViolation]) -> bool:
        """Check if request should be blocked based on violations."""
        if not violations:
            return False

        # Block on critical violations
        critical_violations = [v for v in violations if v.severity == "critical"]
        if critical_violations:
            return True

        # Block on high severity violations (configurable)
        high_violations = [v for v in violations if v.severity == "high"]
        if len(high_violations) >= 2:  # Multiple high severity violations
            return True

        return False