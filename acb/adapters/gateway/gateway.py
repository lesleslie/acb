"""Main API Gateway implementation for ACB framework."""

import time
import typing as t
from dataclasses import dataclass, field
from uuid import uuid4

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.config import Config
from acb.depends import depends

from ._base import GatewayBase, GatewaySettings
from .auth import AuthenticationMiddleware, AuthResult
from .middleware import MiddlewareChain
from .rate_limit import RateLimitMiddleware, RateLimitStatus
from .usage import QuotaManager, UsageAnalytics, UsageTracker

try:
    from uuid import uuid7

    def generate_adapter_id() -> str:
        return str(uuid7())

except ImportError:

    def generate_adapter_id() -> str:
        return str(uuid4())


# Module metadata for discovery system
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="API Gateway",
    category="gateway",
    provider="acb",
    version="1.0.0",
    acb_min_version="0.19.1",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.AUTHENTICATION,
        AdapterCapability.RATE_LIMITING,
        AdapterCapability.MONITORING,
        AdapterCapability.VALIDATION,
    ],
    required_packages=["pyjwt>=2.0.0", "pydantic>=2.0.0"],
    description="Comprehensive API Gateway with authentication, rate limiting, and usage tracking",
    config_example={
        "enabled": True,
        "host": "0.0.0.0",
        "port": 8080,
        "cors_enabled": True,
        "rate_limiting_enabled": True,
        "auth_enabled": True,
        "usage_tracking_enabled": True,
    },
)


@dataclass
class GatewayRequest:
    """Represents an incoming gateway request."""

    request_id: str = field(default_factory=lambda: str(uuid4()))
    method: str = ""
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    body: t.Any = None
    ip_address: str = ""
    user_agent: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, t.Any] = field(default_factory=dict)


@dataclass
class GatewayResponse:
    """Represents an outgoing gateway response."""

    request_id: str = ""
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: t.Any = None
    processing_time_ms: float = 0.0
    metadata: dict[str, t.Any] = field(default_factory=dict)


class RequestProcessor(GatewayBase):
    """Process requests through the gateway pipeline."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.auth_middleware: AuthenticationMiddleware | None = None
        self.rate_limit_middleware: RateLimitMiddleware | None = None
        self.middleware_chain: MiddlewareChain | None = None
        self.usage_tracker: UsageTracker | None = None

    async def initialize(self) -> None:
        """Initialize request processor."""
        await super().initialize()

        # Initialize middleware components
        self.auth_middleware = AuthenticationMiddleware(self.settings)
        await self.auth_middleware.initialize()

        self.rate_limit_middleware = RateLimitMiddleware(self.settings)
        await self.rate_limit_middleware.initialize()

        self.middleware_chain = MiddlewareChain(self.settings)
        await self.middleware_chain.initialize()

        self.usage_tracker = UsageTracker(self.settings)
        await self.usage_tracker.initialize()

    async def process_request(
        self,
        request: GatewayRequest,
        required_scopes: list[str] | None = None,
    ) -> GatewayResponse:
        """Process a complete request through the gateway pipeline."""
        start_time = time.time()
        response = GatewayResponse(request_id=request.request_id)

        try:
            # Convert request to dict for middleware processing
            request_dict = {
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "headers": request.headers,
                "query_params": request.query_params,
                "body": request.body,
                "ip_address": request.ip_address,
                "user_agent": request.user_agent,
                "timestamp": request.timestamp,
                "metadata": request.metadata,
            }

            # 1. Process through middleware chain
            request_dict = await self.middleware_chain.process_request(request_dict)

            # Check for validation errors
            if "validation_error" in request_dict:
                response.status = 400
                response.body = {"error": request_dict["validation_error"]}
                return await self._finalize_response(request, response, start_time)

            # 2. Authentication (if enabled)
            auth_result: AuthResult | None = None
            if self.settings.gateway_config.auth_enabled:
                auth_result = await self.auth_middleware.authenticate_request(
                    request.headers,
                    required_scopes,
                )

                if not auth_result.success:
                    response.status = 401
                    response.body = {"error": auth_result.error}
                    return await self._finalize_response(request, response, start_time)

            # 3. Rate limiting (if enabled)
            if self.settings.gateway_config.rate_limiting_enabled:
                user_id = auth_result.user_id if auth_result else None
                rate_limit_key = self.rate_limit_middleware.get_rate_limit_key(
                    user_id,
                    request.ip_address,
                )

                rate_limit_result = await self.rate_limit_middleware.check_rate_limit(
                    rate_limit_key,
                )

                if rate_limit_result.status == RateLimitStatus.RATE_LIMITED:
                    response.status = 429
                    response.headers["Retry-After"] = str(rate_limit_result.retry_after)
                    response.body = {
                        "error": "Rate limit exceeded",
                        "retry_after": rate_limit_result.retry_after,
                    }
                    return await self._finalize_response(request, response, start_time)

                # Add rate limit headers
                response.headers.update(
                    {
                        "X-RateLimit-Remaining": str(rate_limit_result.remaining),
                        "X-RateLimit-Reset": str(int(rate_limit_result.reset_time)),
                    },
                )

            # 4. Quota checking (if usage tracking enabled)
            if self.settings.gateway_config.usage_tracking_enabled and auth_result:
                quota_ok, quota_error = await self.usage_tracker.check_quota(
                    auth_result.user_id,
                )

                if not quota_ok:
                    response.status = 402  # Payment Required
                    response.body = {"error": quota_error}
                    return await self._finalize_response(request, response, start_time)

            # 5. Process successful request
            response.status = 200
            response.body = {
                "message": "Request processed successfully",
                "request_id": request.request_id,
                "user_id": auth_result.user_id if auth_result else None,
            }

            # Record successful usage
            if self.settings.gateway_config.usage_tracking_enabled and auth_result:
                await self.usage_tracker.record_request(
                    user_id=auth_result.user_id,
                    endpoint=request.path,
                    method=request.method,
                    response_status=response.status,
                    response_time_ms=(time.time() - start_time) * 1000,
                    user_agent=request.user_agent,
                    ip_address=request.ip_address,
                )

            return await self._finalize_response(request, response, start_time)

        except Exception as e:
            self.record_error(f"Request processing error: {e}")
            response.status = 500
            response.body = {"error": "Internal server error"}
            return await self._finalize_response(request, response, start_time)

    async def _finalize_response(
        self,
        request: GatewayRequest,
        response: GatewayResponse,
        start_time: float,
    ) -> GatewayResponse:
        """Finalize response processing."""
        try:
            # Calculate processing time
            response.processing_time_ms = (time.time() - start_time) * 1000

            # Convert response to dict for middleware processing
            response_dict = {
                "request_id": response.request_id,
                "status": response.status,
                "headers": response.headers,
                "body": response.body,
                "processing_time_ms": response.processing_time_ms,
                "metadata": response.metadata,
                "start_time": start_time,
            }

            # Process through middleware chain
            response_dict = await self.middleware_chain.process_response(response_dict)

            # Update response from processed dict
            response.headers = response_dict.get("headers", response.headers)
            response.metadata = response_dict.get("metadata", response.metadata)

            # Record metrics
            self.record_request(
                success=response.status < 400,
                response_time=response.processing_time_ms,
            )

            return response

        except Exception as e:
            self.record_error(f"Response finalization error: {e}")
            return response


class APIGateway(GatewayBase):
    """Main API Gateway class coordinating all components."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.processor: RequestProcessor | None = None
        self.usage_tracker: UsageTracker | None = None
        self.usage_analytics: UsageAnalytics | None = None
        self.quota_manager: QuotaManager | None = None
        self._running = False

    @depends.inject
    async def initialize(self, config: Config = depends()) -> None:
        """Initialize the API Gateway."""
        await super().initialize()

        # Initialize core processor
        self.processor = RequestProcessor(self.settings)
        await self.processor.initialize()

        # Initialize usage tracking components
        self.usage_tracker = UsageTracker(self.settings)
        await self.usage_tracker.initialize()

        self.usage_analytics = UsageAnalytics(self.settings)
        await self.usage_analytics.initialize()
        self.usage_analytics.set_tracker(self.usage_tracker)

        self.quota_manager = QuotaManager(self.settings)
        await self.quota_manager.initialize()
        self.quota_manager.set_tracker(self.usage_tracker)

        # Connect components
        if self.processor:
            self.processor.usage_tracker = self.usage_tracker

        self._running = True

    async def shutdown(self) -> None:
        """Shutdown the API Gateway."""
        self._running = False

        if self.processor:
            await self.processor.shutdown()

        if self.usage_tracker:
            await self.usage_tracker.shutdown()

        if self.usage_analytics:
            await self.usage_analytics.shutdown()

        if self.quota_manager:
            await self.quota_manager.shutdown()

        await super().shutdown()

    async def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
        body: t.Any = None,
        ip_address: str = "",
        required_scopes: list[str] | None = None,
    ) -> GatewayResponse:
        """Handle an incoming request."""
        if not self._running or not self.processor:
            return GatewayResponse(
                status=503,
                body={"error": "Gateway not available"},
            )

        request = GatewayRequest(
            method=method.upper(),
            path=path,
            headers=headers or {},
            query_params=query_params or {},
            body=body,
            ip_address=ip_address,
            user_agent=headers.get("User-Agent", "") if headers else "",
        )

        return await self.processor.process_request(request, required_scopes)

    async def add_api_key(
        self,
        api_key: str,
        user_id: str,
        scopes: list[str] | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> bool:
        """Add an API key for authentication."""
        if not self.processor or not self.processor.auth_middleware:
            return False

        try:
            self.processor.auth_middleware.add_api_key(
                api_key,
                user_id,
                scopes,
                metadata,
            )
            return True
        except Exception as e:
            self.record_error(f"Failed to add API key: {e}")
            return False

    async def create_user_quota(
        self,
        user_id: str,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        requests_per_month: int = 100000,
        bytes_per_day: int = 10 * 1024 * 1024,
    ) -> bool:
        """Create quota for a user."""
        if not self.quota_manager:
            return False

        return await self.quota_manager.create_quota(
            user_id,
            requests_per_hour,
            requests_per_day,
            requests_per_month,
            bytes_per_day,
        )

    async def get_usage_analytics(self, time_range_hours: int = 24) -> dict[str, t.Any]:
        """Get usage analytics."""
        if not self.usage_analytics:
            return {"error": "Analytics not available"}

        endpoint_analytics = await self.usage_analytics.get_endpoint_analytics(
            time_range_hours,
        )
        user_analytics = await self.usage_analytics.get_user_analytics(time_range_hours)

        return {
            "endpoints": endpoint_analytics,
            "users": user_analytics,
        }

    async def get_user_usage_stats(self, user_id: str) -> dict[str, t.Any]:
        """Get usage statistics for a specific user."""
        if not self.usage_tracker:
            return {"error": "Usage tracking not available"}

        return await self.usage_tracker.get_usage_stats(user_id)

    async def health_check(self) -> dict[str, t.Any]:
        """Comprehensive health check."""
        base_health = await super().health_check()

        return base_health | {
            "components": {
                "processor": self.processor.status.value
                if self.processor
                else "inactive",
                "usage_tracker": (
                    self.usage_tracker.status.value
                    if self.usage_tracker
                    else "inactive"
                ),
                "usage_analytics": (
                    self.usage_analytics.status.value
                    if self.usage_analytics
                    else "inactive"
                ),
                "quota_manager": (
                    self.quota_manager.status.value
                    if self.quota_manager
                    else "inactive"
                ),
            },
            "running": self._running,
        }


# Convenience function for ACB integration
async def create_api_gateway(settings: GatewaySettings | None = None) -> APIGateway:
    """Create and initialize an API Gateway instance."""
    gateway = APIGateway(settings)
    await gateway.initialize()
    return gateway
