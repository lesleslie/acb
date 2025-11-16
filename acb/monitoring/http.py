from __future__ import annotations

import time

import typing as t
from contextlib import suppress

from acb.adapters import import_adapter
from acb.depends import depends

from .health import ComponentHealth, HealthStatus


def _resolve_http_exceptions() -> tuple[type[Exception], type[Exception]]:
    """Resolve adapter-agnostic HTTP exception types.

    Tries, in order: httpx, niquests, requests; otherwise returns local fallbacks.
    Returns a tuple of (HTTPRequestError, HTTPTimeoutError).
    """
    with suppress(Exception):  # httpx
        from httpx import HTTPError, TimeoutException  # type: ignore

        return HTTPError, TimeoutException

    with suppress(Exception):  # niquests
        from niquests.exceptions import RequestException, Timeout  # type: ignore

        return RequestException, Timeout

    with suppress(Exception):  # requests
        from requests.exceptions import RequestException, Timeout  # type: ignore

        return RequestException, Timeout

    class _HTTPRequestError(Exception):
        pass

    class _HTTPTimeoutError(Exception):
        pass

    return _HTTPRequestError, _HTTPTimeoutError


# Adapter-agnostic HTTP exceptions (single assignment for type-checkers)
HTTPRequestError, HTTPTimeoutError = _resolve_http_exceptions()


async def check_http_client_health(
    test_url: str | None = None,
    timeout_ms: float = 5000,
) -> ComponentHealth:
    start = time.perf_counter()

    try:
        requests_adapter = import_adapter("requests")
        requests = depends.get_sync(requests_adapter)
    except Exception as e:
        return ComponentHealth(
            name="http_client",
            status=HealthStatus.UNHEALTHY,
            message=f"Failed to initialize Requests adapter: {e}",
            metadata={"error": str(e), "error_type": type(e).__name__},
        )

    try:
        metadata: dict[str, t.Any] = {}
        if test_url:
            timeout_sec = max(1, int(timeout_ms / 1000))
            resp = await requests.get(test_url, timeout=timeout_sec)
            latency_ms = (time.perf_counter() - start) * 1000
            if resp.status_code >= 400:
                return ComponentHealth(
                    name="http_client",
                    status=HealthStatus.DEGRADED,
                    message=f"Connectivity test failed: HTTP {resp.status_code}",
                    latency_ms=latency_ms,
                    metadata={"test_url": test_url, "status_code": resp.status_code},
                )
            if latency_ms > timeout_ms:
                return ComponentHealth(
                    name="http_client",
                    status=HealthStatus.DEGRADED,
                    message=(
                        f"High latency detected: {latency_ms:.2f}ms (threshold: {timeout_ms}ms)"
                    ),
                    latency_ms=latency_ms,
                    metadata={
                        "test_url": test_url,
                        "status_code": resp.status_code,
                        "threshold_ms": timeout_ms,
                    },
                )
            return ComponentHealth(
                name="http_client",
                status=HealthStatus.HEALTHY,
                message="HTTP client operational with successful connectivity test",
                latency_ms=latency_ms,
                metadata={"test_url": test_url, "status_code": resp.status_code},
            )

        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="http_client",
            status=HealthStatus.HEALTHY,
            message="Requests adapter initialized and ready",
            latency_ms=latency_ms,
            metadata=metadata,
        )
    except HTTPTimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="http_client",
            status=HealthStatus.DEGRADED,
            message=f"Connectivity test timeout after {latency_ms:.2f}ms",
            latency_ms=latency_ms,
            metadata={"test_url": test_url, "error": "timeout"} if test_url else {},
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="http_client",
            status=HealthStatus.DEGRADED,
            message=f"Connectivity test error: {e}",
            latency_ms=latency_ms,
            metadata={
                "test_url": test_url,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            if test_url
            else {"error": str(e), "error_type": type(e).__name__},
        )


async def check_http_connectivity(
    url: str,
    expected_status: int = 200,
    timeout_ms: float = 5000,
) -> ComponentHealth:
    start = time.perf_counter()

    try:
        requests_adapter = import_adapter("requests")
        requests = depends.get_sync(requests_adapter)
    except Exception as e:
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"Failed to initialize Requests adapter: {e}",
            metadata={"url": url, "error": str(e), "error_type": type(e).__name__},
        )

    try:
        timeout_sec = max(1, int(timeout_ms / 1000))
        resp = await requests.get(url, timeout=timeout_sec)
        latency_ms = (time.perf_counter() - start) * 1000
        if resp.status_code != expected_status:
            return ComponentHealth(
                name="http_connectivity",
                status=HealthStatus.DEGRADED,
                message=f"Unexpected status code: {resp.status_code} (expected: {expected_status})",
                latency_ms=latency_ms,
                metadata={
                    "url": url,
                    "status_code": resp.status_code,
                    "expected_status": expected_status,
                },
            )
        if latency_ms > timeout_ms:
            return ComponentHealth(
                name="http_connectivity",
                status=HealthStatus.DEGRADED,
                message=f"High latency: {latency_ms:.2f}ms (threshold: {timeout_ms}ms)",
                latency_ms=latency_ms,
                metadata={
                    "url": url,
                    "status_code": resp.status_code,
                    "threshold_ms": timeout_ms,
                },
            )
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.HEALTHY,
            message=f"Connectivity test successful: {url}",
            latency_ms=latency_ms,
            metadata={"url": url, "status_code": resp.status_code},
        )
    except HTTPTimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"Request timeout after {latency_ms:.2f}ms",
            latency_ms=latency_ms,
            metadata={"url": url, "error": "timeout"},
        )
    except HTTPRequestError as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"HTTP error: {e}",
            latency_ms=latency_ms,
            metadata={"url": url, "error": str(e), "error_type": type(e).__name__},
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="http_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"Connectivity check failed: {e}",
            latency_ms=latency_ms,
            metadata={"url": url, "error": str(e), "error_type": type(e).__name__},
        )


__all__ = [
    "check_http_client_health",
    "check_http_connectivity",
]
