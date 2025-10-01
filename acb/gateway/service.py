"""Main Gateway Service implementation for ACB Gateway system.

This module provides the main gateway service that orchestrates all gateway
components including rate limiting, authentication, routing, caching, security,
analytics, and validation.
"""

from __future__ import annotations

import time
import typing as t

from acb.config import Config
from acb.depends import depends
from acb.gateway._base import (
    GatewayConfig,
    GatewayMetrics,
    GatewayProtocol,
    GatewayRequest,
    GatewayResponse,
    GatewayResult,
    GatewaySettings,
    GatewayStatus,
)
from acb.gateway.analytics import AnalyticsCollector
from acb.gateway.auth import AuthConfig, AuthManager
from acb.gateway.cache import CacheManager
from acb.gateway.rate_limiting import RateLimitConfig, RateLimiter
from acb.gateway.routing import Route, RoutingEngine
from acb.gateway.security import SecurityManager
from acb.gateway.validation import RequestResponseValidator, ValidationRule
from acb.logger import Logger
from acb.services._base import ServiceBase, ServiceConfig

# Service metadata for discovery system
try:
    from acb.services.discovery import (
        ServiceCapability,
        ServiceMetadata,
        ServiceStatus,
        generate_service_id,
    )

    SERVICE_METADATA = ServiceMetadata(
        service_id=generate_service_id(),
        name="Gateway Service",
        category="gateway",
        service_type="api_gateway",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.LIFECYCLE_MANAGEMENT,
            ServiceCapability.HEALTH_MONITORING,
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.CACHING,
            ServiceCapability.MONITORING,
            ServiceCapability.ERROR_HANDLING,
        ],
        description="Comprehensive API gateway service with rate limiting, authentication, routing, caching, and security",
        settings_class="GatewaySettings",
        config_example={
            "enabled": True,
            "level": "standard",
            "enable_rate_limiting": True,
            "enable_authentication": True,
            "enable_caching": True,
            "enable_analytics": True,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None


class GatewayService(ServiceBase, GatewayProtocol):
    """Main API Gateway service for ACB applications.

    This service provides comprehensive API gateway functionality including:
    - Rate limiting and throttling
    - Authentication and authorization
    - Request/response validation
    - Multi-tenant routing
    - Response caching
    - Security headers and CORS
    - Analytics and monitoring

    Performance targets:
    - <1ms overhead for simple requests
    - <5ms for authenticated requests with validation
    - <10ms for complex routing with analytics
    """

    config: Config = depends()
    logger: Logger = depends()

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        gateway_settings: GatewaySettings | None = None,
    ) -> None:
        # Initialize ServiceBase
        service_config = service_config or ServiceConfig(
            service_id="gateway",
            name="GatewayService",
            description="Comprehensive API gateway service",
        )
        super().__init__(service_config=service_config)

        # Initialize gateway-specific components
        self._gateway_settings = gateway_settings or GatewaySettings()
        self._gateway_metrics = GatewayMetrics()

        # Initialize gateway components
        self._rate_limiter = RateLimiter()
        self._auth_manager = AuthManager()
        self._routing_engine = RoutingEngine()
        self._cache_manager = CacheManager()
        self._security_manager = SecurityManager()
        self._analytics_collector = AnalyticsCollector()
        self._validator = RequestResponseValidator()

    async def _initialize(self) -> None:
        """Initialize the GatewayService."""
        self.logger.info("Initializing GatewayService")

        # Initialize validation service if enabled
        if self._validation_enabled:
            await self._initialize_validation_service()

        # Set up default routes if none configured
        await self._setup_default_routes()

        # Set up performance monitoring
        self.set_custom_metric("gateway_enabled", True)
        self.set_custom_metric("level", self._gateway_settings.level.value)

        self.logger.info("GatewayService initialized successfully")

    async def _shutdown(self) -> None:
        """Shutdown the GatewayService."""
        self.logger.info("Shutting down GatewayService")

        # Clear route configuration
        self._routing_engine = RoutingEngine()

        # Clean up validation service
        self._validation_service = None

        self.logger.info("GatewayService shut down successfully")

    async def _health_check(self) -> dict[str, t.Any]:
        """Perform GatewayService health check."""
        try:
            # Test basic gateway functionality
            test_request = GatewayRequest(
                method="GET",
                path="/health",
                client_ip="127.0.0.1",
            )

            start_time = time.perf_counter()
            result = await self.validate_request(test_request)
            processing_time = (time.perf_counter() - start_time) * 1000

            # Check component health
            cache_stats = await self._cache_manager.get_cache_stats()
            route_count = len(self._routing_engine.list_routes())

            return {
                "gateway_functional": result is not None,
                "processing_time_ms": processing_time,
                "cache_healthy": cache_stats.total_requests >= 0,
                "routes_configured": route_count,
                "validation_enabled": self._validation_enabled,
                "validation_available": self._validation_service is not None,
                "metrics": self._gateway_metrics.to_dict(),
                "components": {
                    "rate_limiter": "available",
                    "auth_manager": "available",
                    "routing_engine": "available",
                    "cache_manager": "available",
                    "security_manager": "available",
                    "analytics_collector": "available",
                },
            }

        except Exception as e:
            return {
                "gateway_functional": False,
                "error": str(e),
                "components_loaded": {
                    "rate_limiter": self._rate_limiter is not None,
                    "auth_manager": self._auth_manager is not None,
                    "routing_engine": self._routing_engine is not None,
                    "cache_manager": self._cache_manager is not None,
                    "security_manager": self._security_manager is not None,
                    "analytics_collector": self._analytics_collector is not None,
                },
            }

    async def _initialize_validation_service(self) -> None:
        """Initialize validation service integration."""
        try:
            from acb.services.discovery import import_service

            ValidationService = import_service("validation")
            self._validation_service = depends.get(ValidationService)
            self.logger.info("Validation service integration enabled")
        except Exception as e:
            self.logger.warning(f"Failed to initialize validation service: {e}")
            self._validation_enabled = False

    async def _setup_default_routes(self) -> None:
        """Set up default routes if none configured."""
        routes = self._routing_engine.list_routes()
        if not routes:
            self.logger.info("No routes configured, gateway will handle all requests")

    async def process_request(
        self,
        request: GatewayRequest,
        config: GatewayConfig | None = None,
    ) -> GatewayResult:
        """Process a gateway request through the complete pipeline."""
        start_time = time.perf_counter()
        gateway_config = config or GatewayConfig()
        result = GatewayResult(
            success=False,
            status=GatewayStatus.GATEWAY_ERROR,
            request=request,
        )

        try:
            # Pre-processing pipeline
            cache_hit = await self._run_preprocessing_pipeline(request, result, gateway_config)
            if cache_hit or not result.success:
                return result

            # Main processing
            await self._run_main_processing(request, result, gateway_config)

            # Post-processing pipeline
            await self._run_postprocessing_pipeline(request, result, gateway_config)

        except Exception as e:
            self.logger.error(f"Gateway processing error: {e}")
            result.add_error(f"Gateway processing failed: {e}")
            result.status = GatewayStatus.GATEWAY_ERROR

        finally:
            result.processing_time_ms = (time.perf_counter() - start_time) * 1000
            self._gateway_metrics.record_request(
                success=result.success,
                response_time_ms=result.processing_time_ms,
                status=result.status,
            )

            # Record analytics
            if result.response:
                await self._analytics_collector.collect_request_end(
                    request, result.response, processing_time_ms
                )

            # Update service metrics
            self.increment_requests()
            if not result.success:
                self.record_error(f"Gateway failed: {'; '.join(result.errors)}")

        return result

    async def _run_preprocessing_pipeline(
        self,
        request: GatewayRequest,
        result: GatewayResult,
        config: GatewayConfig,
    ) -> bool:
        """Run pre-processing pipeline. Returns True if cache hit."""
        # 1. Security validation
        if config.enable_security_headers:
            await self._process_security(request, result)
            if not result.success:
                return False

        # 2. Rate limiting
        if config.enable_rate_limiting and not request.skip_rate_limiting:
            await self._process_rate_limiting(request, result)
            if not result.success:
                return False

        # 3. Authentication
        if config.enable_authentication and not request.skip_authentication:
            await self._process_authentication(request, result)
            if not result.success:
                return False

        # 4. Request validation
        if config.enable_validation and not request.skip_validation:
            await self._process_validation(request, result)
            if not result.success:
                return False

        # 5. Check cache
        if config.enable_caching and not request.skip_caching:
            cached_response = await self._check_cache(request, result)
            if cached_response:
                result.response = cached_response
                result.success = True
                result.status = GatewayStatus.SUCCESS
                await self._analytics_collector.collect_cache_event(request, True)
                return True

        return False

    async def _run_main_processing(
        self,
        request: GatewayRequest,
        result: GatewayResult,
        config: GatewayConfig,
    ) -> None:
        """Run main processing (routing)."""
        await self._process_routing(request, result, config)

    async def _run_postprocessing_pipeline(
        self,
        request: GatewayRequest,
        result: GatewayResult,
        config: GatewayConfig,
    ) -> None:
        """Run post-processing pipeline."""
        # 1. Response validation
        if result.response and config.enable_validation:
            await self._process_response_validation(request, result)
            if not result.success:
                return

        # 2. Cache response
        if result.response and config.enable_caching:
            await self._cache_response(request, result.response)

        # 3. Apply security headers
        if result.response and config.enable_security_headers:
            await self._apply_security_headers(request, result.response)

        # Mark as successful if we got here
        if result.response:
            result.success = True
            result.status = GatewayStatus.SUCCESS

    async def validate_request(
        self,
        request: GatewayRequest,
        config: GatewayConfig | None = None,
    ) -> GatewayResult:
        """Validate a request without full processing."""
        start_time = time.perf_counter()
        gateway_config = config or GatewayConfig()
        result = GatewayResult(
            success=True,
            status=GatewayStatus.SUCCESS,
            request=request,
        )

        try:
            # Security validation
            if gateway_config.enable_security_headers:
                violations = await self._security_manager.validate_request_security(request)
                if self._security_manager.is_request_blocked(violations):
                    result.add_error("Request blocked by security policy")
                    result.status = GatewayStatus.FORBIDDEN
                    return result

            # Rate limiting check
            if gateway_config.enable_rate_limiting:
                rate_limit_config = RateLimitConfig()
                rate_limit_result = await self._rate_limiter.check_rate_limit(
                    request, rate_limit_config
                )
                if not rate_limit_result.allowed:
                    result.add_error("Rate limit exceeded")
                    result.status = GatewayStatus.RATE_LIMITED
                    return result

            # Authentication check
            if gateway_config.enable_authentication:
                auth_config = AuthConfig()
                auth_result = await self._auth_manager.authenticate(request, auth_config)
                if not auth_result.authenticated:
                    result.add_error("Authentication failed")
                    result.status = GatewayStatus.UNAUTHORIZED
                    return result

            # Request validation
            if gateway_config.enable_validation and self._validation_service:
                try:
                    validation_result = await self._validation_service.validate(request.body)
                    if not validation_result.is_valid:
                        result.add_error("Request validation failed")
                        result.status = GatewayStatus.VALIDATION_FAILED
                        return result
                except Exception as e:
                    self.logger.warning(f"Validation service error: {e}")

        except Exception as e:
            self.logger.error(f"Request validation error: {e}")
            result.add_error(f"Validation failed: {e}")
            result.status = GatewayStatus.GATEWAY_ERROR

        finally:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            result.processing_time_ms = processing_time_ms

        return result

    async def get_metrics(self) -> GatewayMetrics:
        """Get current gateway metrics."""
        return self._gateway_metrics

    async def reset_metrics(self) -> None:
        """Reset gateway metrics."""
        self._gateway_metrics = GatewayMetrics()
        await self._analytics_collector.reset_metrics()
        self.logger.info("Gateway metrics reset")

    # Helper methods for request processing pipeline

    async def _process_security(self, request: GatewayRequest, result: GatewayResult) -> None:
        """Process security validation."""
        result.add_component_used("security")

        # Handle CORS preflight
        preflight_response = await self._security_manager.handle_preflight_request(
            request, request.tenant_id
        )
        if preflight_response:
            result.response = preflight_response
            result.success = True
            result.status = GatewayStatus.SUCCESS
            return

        # Validate request security
        violations = await self._security_manager.validate_request_security(request)
        if self._security_manager.is_request_blocked(violations):
            result.add_error("Request blocked by security policy")
            result.status = GatewayStatus.FORBIDDEN

    async def _process_rate_limiting(self, request: GatewayRequest, result: GatewayResult) -> None:
        """Process rate limiting."""
        result.add_component_used("rate_limiter")

        rate_limit_config = RateLimitConfig()
        rate_limit_result = await self._rate_limiter.check_rate_limit(request, rate_limit_config)

        await self._analytics_collector.collect_rate_limit_event(
            request, not rate_limit_result.allowed
        )

        if not rate_limit_result.allowed:
            result.add_error("Rate limit exceeded")
            result.status = GatewayStatus.RATE_LIMITED
            # Create rate limit response
            result.response = GatewayResponse(
                status_code=429,
                headers={"Retry-After": str(rate_limit_result.info.retry_after or 60)},
                body={"error": "Rate limit exceeded", "retry_after": rate_limit_result.info.retry_after},
            )

    async def _process_authentication(self, request: GatewayRequest, result: GatewayResult) -> None:
        """Process authentication."""
        result.add_component_used("auth")

        auth_config = AuthConfig()
        auth_result = await self._auth_manager.authenticate(request, auth_config)

        await self._analytics_collector.collect_authentication_event(
            request,
            auth_result.authenticated,
            auth_config.method.value,
            auth_result.error_message,
        )

        if not auth_result.authenticated:
            result.add_error("Authentication failed")
            result.status = GatewayStatus.UNAUTHORIZED
            # Create auth failure response
            result.response = GatewayResponse(
                status_code=401,
                headers=auth_result.response_headers,
                body={"error": "Authentication required", "message": auth_result.error_message},
            )
        else:
            # Add user context to request
            if auth_result.user:
                request.auth_user = {
                    "user_id": auth_result.user.user_id,
                    "username": auth_result.user.username,
                    "roles": auth_result.user.roles,
                    "scopes": auth_result.user.scopes,
                    "tenant_id": auth_result.user.tenant_id,
                }

    async def _process_validation(self, request: GatewayRequest, result: GatewayResult) -> None:
        """Process request validation using RequestResponseValidator."""
        result.add_component_used("validation")

        try:
            # Validate request body
            if request.body is not None:
                body_validation = await self._validator.validate_request_body(
                    request.body,
                    request.headers.get("content-type", "application/json")
                )
                if not body_validation.valid:
                    result.add_error("Request body validation failed")
                    result.status = GatewayStatus.VALIDATION_FAILED
                    result.response = GatewayResponse(
                        status_code=400,
                        headers={"Content-Type": "application/json"},
                        body={
                            "error": "Request body validation failed",
                            "validation_id": body_validation.validation_id,
                            "errors": body_validation.errors,
                            "warnings": body_validation.warnings,
                        },
                    )
                    return

            # Validate request headers
            header_validation = await self._validator.validate_request_headers(request.headers)
            if not header_validation.valid:
                result.add_error("Request header validation failed")
                result.status = GatewayStatus.VALIDATION_FAILED
                result.response = GatewayResponse(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    body={
                        "error": "Request header validation failed",
                        "validation_id": header_validation.validation_id,
                        "errors": header_validation.errors,
                        "warnings": header_validation.warnings,
                    },
                )
                return

            # Validate query parameters
            if request.query_params:
                query_validation = await self._validator.validate_request_query(request.query_params)
                if not query_validation.valid:
                    result.add_error("Query parameter validation failed")
                    result.status = GatewayStatus.VALIDATION_FAILED
                    result.response = GatewayResponse(
                        status_code=400,
                        headers={"Content-Type": "application/json"},
                        body={
                            "error": "Query parameter validation failed",
                            "validation_id": query_validation.validation_id,
                            "errors": query_validation.errors,
                            "warnings": query_validation.warnings,
                        },
                    )
                    return

            # Validate path parameters
            if request.path_params:
                path_validation = await self._validator.validate_request_path(request.path_params)
                if not path_validation.valid:
                    result.add_error("Path parameter validation failed")
                    result.status = GatewayStatus.VALIDATION_FAILED
                    result.response = GatewayResponse(
                        status_code=400,
                        headers={"Content-Type": "application/json"},
                        body={
                            "error": "Path parameter validation failed",
                            "validation_id": path_validation.validation_id,
                            "errors": path_validation.errors,
                            "warnings": path_validation.warnings,
                        },
                    )
                    return

        except Exception as e:
            self.logger.warning(f"Validation processing error: {e}")
            result.add_error(f"Validation processing error: {str(e)}")
            result.status = GatewayStatus.VALIDATION_FAILED

    async def _process_response_validation(self, request: GatewayRequest, result: GatewayResult) -> None:
        """Process response validation using RequestResponseValidator."""
        if not result.response:
            return

        result.add_component_used("response_validation")

        try:
            # Validate response body
            if result.response.body is not None:
                content_type = result.response.headers.get("content-type", "application/json")
                body_validation = await self._validator.validate_response_body(
                    result.response.body,
                    content_type
                )
                if not body_validation.valid:
                    self.logger.warning(
                        f"Response body validation failed for request {request.request_id}: "
                        f"{body_validation.errors}"
                    )
                    # Log validation warnings but don't block response for warnings
                    result.add_error("Response body validation failed")
                    # Don't block the response, just log the issue
                    # In production, you might want to handle this differently

            # Validate response headers
            header_validation = await self._validator.validate_response_headers(result.response.headers)
            if not header_validation.valid:
                self.logger.warning(
                    f"Response header validation failed for request {request.request_id}: "
                    f"{header_validation.errors}"
                )
                result.add_error("Response header validation failed")

        except Exception as e:
            self.logger.warning(f"Response validation processing error: {e}")
            result.add_error(f"Response validation processing error: {str(e)}")

    async def _check_cache(self, request: GatewayRequest, result: GatewayResult) -> GatewayResponse | None:
        """Check for cached response."""
        result.add_component_used("cache")

        cached_response = await self._cache_manager.get_cached_response(
            request, request.tenant_id
        )

        if cached_response:
            await self._analytics_collector.collect_cache_event(request, True)
            return cached_response.to_gateway_response()
        else:
            await self._analytics_collector.collect_cache_event(request, False)
            return None

    async def _cache_response(self, request: GatewayRequest, response: GatewayResponse) -> None:
        """Cache the response."""
        await self._cache_manager.cache_response(
            request, response, tenant_id=request.tenant_id
        )

    async def _apply_security_headers(self, request: GatewayRequest, response: GatewayResponse) -> None:
        """Apply security headers to response."""
        self._security_manager.apply_security_headers(response, request, request.tenant_id)

    async def _process_routing(
        self,
        request: GatewayRequest,
        result: GatewayResult,
        config: GatewayConfig,
    ) -> None:
        """Process request routing."""
        result.add_component_used("routing")

        # Find matching route
        route = await self._routing_engine.find_route(request, request.tenant_id)
        if not route:
            result.add_error("No matching route found")
            result.status = GatewayStatus.ROUTING_FAILED
            result.response = GatewayResponse(
                status_code=404,
                headers={"Content-Type": "application/json"},
                body={"error": "Not found", "message": "No matching route"},
            )
            return

        # Select upstream
        upstream = await self._routing_engine.select_upstream(route, request)
        if not upstream:
            result.add_error("No healthy upstream available")
            result.status = GatewayStatus.UPSTREAM_ERROR
            result.response = GatewayResponse(
                status_code=503,
                headers={"Content-Type": "application/json"},
                body={"error": "Service unavailable", "message": "No healthy upstream"},
            )
            return

        # For this implementation, we'll create a mock response
        # In a real implementation, this would make an HTTP request to the upstream
        result.response = GatewayResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"message": "Success", "upstream": upstream.id, "route": route.id},
            upstream_url=upstream.url,
        )

    # Route management methods

    def add_route(self, route: Route) -> None:
        """Add a route to the gateway."""
        self._routing_engine.add_route(route)
        self.logger.info(f"Added route: {route.id}")

    def remove_route(self, route_id: str) -> bool:
        """Remove a route from the gateway."""
        removed = self._routing_engine.remove_route(route_id)
        if removed:
            self.logger.info(f"Removed route: {route_id}")
        return removed

    def list_routes(self, tenant_id: str | None = None) -> list[Route]:
        """List all routes."""
        return self._routing_engine.list_routes(tenant_id)

    # Analytics methods

    async def get_analytics_metrics(self, tenant_id: str | None = None) -> dict[str, t.Any]:
        """Get analytics metrics."""
        metrics = await self._analytics_collector.get_metrics(tenant_id)
        return metrics.to_dict()

    async def get_recent_events(self, limit: int = 100, tenant_id: str | None = None) -> list[dict[str, t.Any]]:
        """Get recent analytics events."""
        events = await self._analytics_collector.get_recent_events(limit, tenant_id=tenant_id)
        return [event.to_dict() for event in events]

    # Validation management methods

    def add_validation_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule to the gateway."""
        self._validator.add_rule(rule)
        self.logger.info(f"Added validation rule: {rule.name}")

    def remove_validation_rule(self, rule_name: str) -> None:
        """Remove a validation rule from the gateway."""
        self._validator.remove_rule(rule_name)
        self.logger.info(f"Removed validation rule: {rule_name}")

    def get_validation_rule(self, rule_name: str) -> ValidationRule | None:
        """Get a validation rule by name."""
        return self._validator.get_rule(rule_name)

    def list_validation_rules(self, validation_type: t.Any = None) -> list[ValidationRule]:
        """List all validation rules."""
        return self._validator.list_rules(validation_type)

    def get_validation_stats(self) -> dict[str, t.Any]:
        """Get validation statistics."""
        return self._validator.get_validation_stats()