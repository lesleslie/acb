from __future__ import annotations

import time
from enum import Enum

import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HealthStatus):
            return NotImplemented
        order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
            HealthStatus.CRITICAL: 3,
            HealthStatus.UNKNOWN: 4,
        }
        return order[self] < order[other]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, HealthStatus):
            return NotImplemented
        order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
            HealthStatus.CRITICAL: 3,
            HealthStatus.UNKNOWN: 4,
        }
        return order[self] > order[other]


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = None
    metadata: dict[str, t.Any] = field(default_factory=dict)
    check_type: str | None = None
    component_id: str | None = None
    component_name: str | None = None
    details: dict[str, t.Any] = field(default_factory=dict)
    timestamp: float | None = None
    duration_ms: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        result: dict[str, t.Any] = {"name": self.name, "status": self.status.value}
        if self.message is not None:
            result["message"] = self.message
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        if self.metadata:
            result["metadata"] = self.metadata
        if self.check_type is not None:
            result["check_type"] = self.check_type
        if self.component_id is not None:
            result["component_id"] = self.component_id
        if self.component_name is not None:
            result["component_name"] = self.component_name
        if self.details:
            result["details"] = self.details
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp
        if self.duration_ms is not None:
            result["duration_ms"] = round(self.duration_ms, 2)
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass
class HealthCheckResponse:
    status: HealthStatus
    timestamp: str
    version: str
    components: list[ComponentHealth]
    uptime_seconds: float
    metadata: dict[str, t.Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        components: list[ComponentHealth],
        *,
        version: str,
        start_time: float,
        metadata: dict[str, t.Any] | None = None,
    ) -> HealthCheckResponse:
        overall = (
            HealthStatus.HEALTHY
            if not components
            else max(c.status for c in components)
        )
        return cls(
            status=overall,
            timestamp=datetime.now(UTC).isoformat(),
            version=version,
            components=components,
            uptime_seconds=time.time() - start_time,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, t.Any]:
        result: dict[str, t.Any] = {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "components": [c.to_dict() for c in self.components],
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def is_healthy(self) -> bool:  # pragma: no cover - trivial
        return self.status == HealthStatus.HEALTHY

    def is_ready(self) -> bool:  # pragma: no cover - trivial
        return self.status != HealthStatus.UNHEALTHY


__all__ = [
    "ComponentHealth",
    "HealthCheckResponse",
    "HealthStatus",
]
