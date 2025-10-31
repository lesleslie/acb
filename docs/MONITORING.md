# Monitoring

Adapter‑agnostic monitoring helpers for ACB. For provider integrations (Sentry,
Logfire) see `acb/adapters/monitoring/`.

## Health

Core health primitives live under `acb.monitoring.health`:

- `HealthStatus`: ordered enum (healthy < degraded < unhealthy)
- `ComponentHealth`: component health snapshot
- `HealthCheckResponse`: aggregator (worst status wins)

Example:

```python
from acb.monitoring.health import (
    HealthStatus,
    ComponentHealth,
    HealthCheckResponse,
)
import time

components = [
    ComponentHealth(name="db", status=HealthStatus.HEALTHY),
    ComponentHealth(name="api", status=HealthStatus.DEGRADED, message="High latency"),
]

response = HealthCheckResponse.create(
    components=components,
    version="1.0.0",
    start_time=time.time() - 3600,
)
```

Notes:

- Keep this layer provider‑agnostic.
- Provider adapters (Sentry/Logfire) belong under `acb.adapters.monitoring.*`.

## HTTP

Adapter‑agnostic HTTP connectivity checks built on the ACB Requests adapter
(`acb.adapters.requests`), supporting both HTTPX and Niquests providers.

API:

- `async check_http_client_health(test_url: str | None = None, timeout_ms: float = 5000) -> ComponentHealth`
- `async check_http_connectivity(url: str, expected_status: int = 200, timeout_ms: float = 5000) -> ComponentHealth`

Example:

```python
from acb.monitoring.http import check_http_connectivity, check_http_client_health

# Basic health (initialization only)
result = await check_http_client_health()

# Connectivity test
result = await check_http_connectivity(
    "https://example.com/health", expected_status=200
)
```

Notes:

- Exception handling is adapter‑agnostic via aliasing (httpx, niquests, requests).
- No direct client types are imported; the Requests adapter is resolved via DI.
