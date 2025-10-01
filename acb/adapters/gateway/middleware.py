"""Middleware components for API Gateway."""

import json
import typing as t
from abc import ABC, abstractmethod

from pydantic import BaseModel, ValidationError

from ._base import GatewayBase, GatewaySettings


class MiddlewareBase(ABC):
    """Abstract base class for gateway middleware."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        self.settings = settings or GatewaySettings()

    @abstractmethod
    async def process_request(self, request: dict[str, t.Any]) -> dict[str, t.Any]:
        """Process incoming request."""

    @abstractmethod
    async def process_response(self, response: dict[str, t.Any]) -> dict[str, t.Any]:
        """Process outgoing response."""


class CORSMiddleware(MiddlewareBase):
    """CORS (Cross-Origin Resource Sharing) middleware."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.config = settings.gateway_config if settings else None

    async def process_request(self, request: dict[str, t.Any]) -> dict[str, t.Any]:
        """Process CORS preflight requests."""
        if not self.config or not self.config.cors_enabled:
            return request

        method = request.get("method", "").upper()
        headers = request.get("headers", {})

        # Handle preflight OPTIONS requests
        if method == "OPTIONS":
            request["cors_preflight"] = True
            request["cors_origin"] = headers.get("Origin", "")
            request["cors_method"] = headers.get("Access-Control-Request-Method", "")
            request["cors_headers"] = headers.get("Access-Control-Request-Headers", "")

        return request

    async def process_response(self, response: dict[str, t.Any]) -> dict[str, t.Any]:
        """Add CORS headers to response."""
        if not self.config or not self.config.cors_enabled:
            return response

        headers = response.setdefault("headers", {})

        # Add CORS headers
        if "*" in self.config.cors_origins:
            headers["Access-Control-Allow-Origin"] = "*"
        else:
            origin = response.get("request_origin", "")
            if origin in self.config.cors_origins:
                headers["Access-Control-Allow-Origin"] = origin

        headers["Access-Control-Allow-Methods"] = ", ".join(self.config.cors_methods)
        headers["Access-Control-Allow-Headers"] = ", ".join(self.config.cors_headers)
        headers["Access-Control-Max-Age"] = "86400"  # 24 hours

        # Handle preflight response
        if response.get("cors_preflight"):
            response["status"] = 200
            response["body"] = ""

        return response


class SecurityHeadersMiddleware(MiddlewareBase):
    """Security headers middleware."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)

    async def process_request(self, request: dict[str, t.Any]) -> dict[str, t.Any]:
        """Process request for security validation."""
        # Could add request security checks here
        return request

    async def process_response(self, response: dict[str, t.Any]) -> dict[str, t.Any]:
        """Add security headers to response."""
        headers = response.setdefault("headers", {})

        # Add common security headers
        headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Content-Security-Policy": "default-src 'self'",
            },
        )

        return response


class ValidationMiddleware(MiddlewareBase):
    """Request/response validation middleware."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.schemas: dict[str, type[BaseModel]] = {}

    def register_schema(
        self, endpoint: str, method: str, schema: type[BaseModel]
    ) -> None:
        """Register validation schema for an endpoint."""
        key = f"{method.upper()}:{endpoint}"
        self.schemas[key] = schema

    async def process_request(self, request: dict[str, t.Any]) -> dict[str, t.Any]:
        """Validate incoming request."""
        if not self.settings or not self.settings.gateway_config.validation_enabled:
            return request

        try:
            method = request.get("method", "").upper()
            path = request.get("path", "")
            key = f"{method}:{path}"

            if key in self.schemas:
                schema = self.schemas[key]
                body = request.get("body", {})

                # Parse JSON body if it's a string
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError as e:
                        request["validation_error"] = f"Invalid JSON: {e}"
                        return request

                # Validate against schema
                try:
                    validated_data = schema(**body)
                    request["validated_body"] = validated_data.model_dump()
                except ValidationError as e:
                    if self.settings.gateway_config.strict_validation:
                        request["validation_error"] = f"Validation failed: {e}"
                    else:
                        request["validation_warnings"] = str(e)

        except Exception as e:
            request["validation_error"] = f"Validation middleware error: {e}"

        return request

    async def process_response(self, response: dict[str, t.Any]) -> dict[str, t.Any]:
        """Validate outgoing response."""
        # Could add response validation here if needed
        return response


class LoggingMiddleware(MiddlewareBase):
    """Request/response logging middleware."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.request_logs: list[dict[str, t.Any]] = []

    async def process_request(self, request: dict[str, t.Any]) -> dict[str, t.Any]:
        """Log incoming request."""
        import time

        request["start_time"] = time.time()

        log_entry = {
            "timestamp": request["start_time"],
            "method": request.get("method", ""),
            "path": request.get("path", ""),
            "headers": request.get("headers", {}),
            "ip_address": request.get("ip_address", ""),
            "user_agent": request.get("headers", {}).get("User-Agent", ""),
        }

        self.request_logs.append(log_entry)

        # Keep only recent logs (last 1000)
        if len(self.request_logs) > 1000:
            self.request_logs = self.request_logs[-1000:]

        return request

    async def process_response(self, response: dict[str, t.Any]) -> dict[str, t.Any]:
        """Log outgoing response."""
        import time

        if "start_time" in response:
            response_time = (time.time() - response["start_time"]) * 1000
            response["response_time_ms"] = response_time

        return response

    def get_recent_logs(self, limit: int = 100) -> list[dict[str, t.Any]]:
        """Get recent request logs."""
        return self.request_logs[-limit:]


class MiddlewareChain(GatewayBase):
    """Chain of middleware for request/response processing."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.middleware: list[MiddlewareBase] = []

    async def initialize(self) -> None:
        """Initialize middleware chain."""
        await super().initialize()

        # Add default middleware
        if self.settings and self.settings.gateway_config.middleware_enabled:
            self.add_middleware(LoggingMiddleware(self.settings))
            self.add_middleware(CORSMiddleware(self.settings))
            self.add_middleware(SecurityHeadersMiddleware(self.settings))
            self.add_middleware(ValidationMiddleware(self.settings))

    def add_middleware(self, middleware: MiddlewareBase) -> None:
        """Add middleware to the chain."""
        self.middleware.append(middleware)

    def remove_middleware(self, middleware_type: type[MiddlewareBase]) -> bool:
        """Remove middleware from the chain."""
        for i, middleware in enumerate(self.middleware):
            if isinstance(middleware, middleware_type):
                del self.middleware[i]
                return True
        return False

    async def process_request(self, request: dict[str, t.Any]) -> dict[str, t.Any]:
        """Process request through middleware chain."""
        try:
            for middleware in self.middleware:
                request = await middleware.process_request(request)

                # Stop processing if validation error occurred
                if "validation_error" in request:
                    break

            self.record_request(success="validation_error" not in request)
            return request

        except Exception as e:
            self.record_error(f"Middleware request processing error: {e}")
            request["middleware_error"] = str(e)
            return request

    async def process_response(self, response: dict[str, t.Any]) -> dict[str, t.Any]:
        """Process response through middleware chain (in reverse order)."""
        try:
            # Process in reverse order for response
            for middleware in reversed(self.middleware):
                response = await middleware.process_response(response)

            return response

        except Exception as e:
            self.record_error(f"Middleware response processing error: {e}")
            response["middleware_error"] = str(e)
            return response

    def get_middleware_by_type(
        self, middleware_type: type[MiddlewareBase]
    ) -> MiddlewareBase | None:
        """Get middleware instance by type."""
        for middleware in self.middleware:
            if isinstance(middleware, middleware_type):
                return middleware
        return None
