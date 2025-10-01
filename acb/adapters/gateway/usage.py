from typing import Any
"""Usage tracking and analytics for API Gateway."""

import time
import typing as t
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel

from ._base import GatewayBase, GatewaySettings


@dataclass
class UsageMetrics:
    """Usage metrics for tracking API consumption."""

    user_id: str
    endpoint: str
    method: str
    timestamp: float
    response_status: int
    response_time_ms: float
    bytes_sent: int = 0
    bytes_received: int = 0
    user_agent: str = ""
    ip_address: str = ""
    metadata: dict[str, t.Any] = field(default_factory=dict)


class QuotaConfig(BaseModel):
    """Configuration for user quotas."""

    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    requests_per_month: int = 100000
    bytes_per_day: int = 10 * 1024 * 1024  # 10MB
    custom_limits: dict[str, int] = field(default_factory=dict)

    class Config:
        extra = "forbid"


@dataclass
class QuotaUsage:
    """Current quota usage for a user."""

    user_id: str
    hourly_requests: int = 0
    daily_requests: int = 0
    monthly_requests: int = 0
    daily_bytes: int = 0
    last_reset_hour: float = 0.0
    last_reset_day: float = 0.0
    last_reset_month: float = 0.0


class UsageTracker(GatewayBase):
    """Track API usage metrics and enforce quotas."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.metrics: list[UsageMetrics] = []
        self.quota_usage: dict[str, QuotaUsage] = {}
        self.default_quota = QuotaConfig()
        self.user_quotas: dict[str, QuotaConfig] = {}

    async def initialize(self) -> None:
        """Initialize usage tracker."""
        await super().initialize()

    def set_user_quota(self, user_id: str, quota: QuotaConfig) -> None:
        """Set custom quota for a user."""
        self.user_quotas[user_id] = quota

    def get_user_quota(self, user_id: str) -> QuotaConfig:
        """Get quota configuration for a user."""
        return self.user_quotas.get(user_id, self.default_quota)

    async def record_request(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        response_status: int,
        response_time_ms: float,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        user_agent: str = "",
        ip_address: str = "",
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Record a request for usage tracking."""
        try:
            metrics = UsageMetrics(
                user_id=user_id,
                endpoint=endpoint,
                method=method,
                timestamp=time.time(),
                response_status=response_status,
                response_time_ms=response_time_ms,
                bytes_sent=bytes_sent,
                bytes_received=bytes_received,
                user_agent=user_agent,
                ip_address=ip_address,
                metadata=metadata or {},
            )

            self.metrics.append(metrics)

            # Update quota usage
            await self._update_quota_usage(user_id, bytes_sent + bytes_received)

            # Keep only recent metrics (last 24 hours by default)
            cutoff_time = time.time() - 24 * 3600
            self.metrics = [m for m in self.metrics if m.timestamp > cutoff_time]

        except Exception as e:
            self.record_error(f"Failed to record request: {e}")

    async def _update_quota_usage(self, user_id: str, bytes_used: int) -> None:
        """Update quota usage for a user."""
        current_time = time.time()

        if user_id not in self.quota_usage:
            self.quota_usage[user_id] = QuotaUsage(user_id=user_id)

        usage = self.quota_usage[user_id]

        # Reset counters if time periods have passed
        current_hour = current_time // 3600
        current_day = current_time // (24 * 3600)
        current_month = datetime.fromtimestamp(current_time).month

        if current_hour > usage.last_reset_hour:
            usage.hourly_requests = 0
            usage.last_reset_hour = current_hour

        if current_day > usage.last_reset_day:
            usage.daily_requests = 0
            usage.daily_bytes = 0
            usage.last_reset_day = current_day

        if current_month != datetime.fromtimestamp(usage.last_reset_month).month:
            usage.monthly_requests = 0
            usage.last_reset_month = current_time

        # Update usage
        usage.hourly_requests += 1
        usage.daily_requests += 1
        usage.monthly_requests += 1
        usage.daily_bytes += bytes_used

    async def check_quota(self, user_id: str) -> tuple[bool, str]:
        """Check if user is within quota limits."""
        try:
            quota = self.get_user_quota(user_id)

            if user_id not in self.quota_usage:
                return True, "OK"

            usage = self.quota_usage[user_id]

            # Check hourly limit
            if usage.hourly_requests >= quota.requests_per_hour:
                return False, "Hourly request limit exceeded"

            # Check daily limits
            if usage.daily_requests >= quota.requests_per_day:
                return False, "Daily request limit exceeded"

            if usage.daily_bytes >= quota.bytes_per_day:
                return False, "Daily data transfer limit exceeded"

            # Check monthly limit
            if usage.monthly_requests >= quota.requests_per_month:
                return False, "Monthly request limit exceeded"

            return True, "OK"

        except Exception as e:
            self.record_error(f"Quota check error: {e}")
            return False, f"Quota check failed: {e}"

    async def get_usage_stats(self, user_id: str) -> dict[str, t.Any]:
        """Get usage statistics for a user."""
        try:
            if user_id not in self.quota_usage:
                return {
                    "user_id": user_id,
                    "hourly_requests": 0,
                    "daily_requests": 0,
                    "monthly_requests": 0,
                    "daily_bytes": 0,
                }

            usage = self.quota_usage[user_id]
            quota = self.get_user_quota(user_id)

            return {
                "user_id": user_id,
                "hourly_requests": usage.hourly_requests,
                "daily_requests": usage.daily_requests,
                "monthly_requests": usage.monthly_requests,
                "daily_bytes": usage.daily_bytes,
                "quota": {
                    "requests_per_hour": quota.requests_per_hour,
                    "requests_per_day": quota.requests_per_day,
                    "requests_per_month": quota.requests_per_month,
                    "bytes_per_day": quota.bytes_per_day,
                },
                "remaining": {
                    "hourly": max(0, quota.requests_per_hour - usage.hourly_requests),
                    "daily": max(0, quota.requests_per_day - usage.daily_requests),
                    "monthly": max(
                        0,
                        quota.requests_per_month - usage.monthly_requests,
                    ),
                    "daily_bytes": max(0, quota.bytes_per_day - usage.daily_bytes),
                },
            }

        except Exception as e:
            self.record_error(f"Failed to get usage stats: {e}")
            return {"error": f"Failed to get usage stats: {e}"}


class UsageAnalytics(GatewayBase):
    """Advanced analytics for API usage patterns."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.tracker: UsageTracker | None = None

    async def initialize(self) -> None:
        """Initialize analytics engine."""
        await super().initialize()

    def set_tracker(self, tracker: UsageTracker) -> None:
        """Set the usage tracker for analytics."""
        self.tracker = tracker

    async def get_endpoint_analytics(
        self,
        time_range_hours: int = 24,
    ) -> dict[str, t.Any]:
        """Get analytics for endpoints."""
        if not self.tracker:
            return {"error": "No usage tracker configured"}

        try:
            cutoff_time = time.time() - time_range_hours * 3600
            recent_metrics = [
                m for m in self.tracker.metrics if m.timestamp > cutoff_time
            ]

            endpoint_stats: Any = defaultdict(
                lambda: {
                    "requests": 0,
                    "avg_response_time": 0.0,
                    "success_rate": 0.0,
                    "error_count": 0,
                    "total_bytes": 0,
                },
            )

            for metric in recent_metrics:
                key = f"{metric.method} {metric.endpoint}"
                stats = endpoint_stats[key]
                stats["requests"] += 1
                stats["total_bytes"] += metric.bytes_sent + metric.bytes_received

                # Update average response time
                current_avg = stats["avg_response_time"]
                request_count = stats["requests"]
                stats["avg_response_time"] = (
                    current_avg * (request_count - 1) + metric.response_time_ms
                ) / request_count

                # Track errors
                if metric.response_status >= 400:
                    stats["error_count"] += 1

            # Calculate success rates
            for stats in endpoint_stats.values():
                if stats["requests"] > 0:
                    stats["success_rate"] = (
                        (stats["requests"] - stats["error_count"]) / stats["requests"]
                    ) * 100

            return {
                "time_range_hours": time_range_hours,
                "endpoints": dict(endpoint_stats),
                "total_requests": len(recent_metrics),
            }

        except Exception as e:
            self.record_error(f"Analytics error: {e}")
            return {"error": f"Analytics failed: {e}"}

    async def get_user_analytics(self, time_range_hours: int = 24) -> dict[str, t.Any]:
        """Get analytics for users."""
        if not self.tracker:
            return {"error": "No usage tracker configured"}

        try:
            cutoff_time = time.time() - time_range_hours * 3600
            recent_metrics = [
                m for m in self.tracker.metrics if m.timestamp > cutoff_time
            ]

            user_stats = defaultdict(
                lambda: {
                    "requests": 0,
                    "avg_response_time": 0.0,
                    "total_bytes": 0,
                    "unique_endpoints": set(),
                    "error_count": 0,
                },
            )

            for metric in recent_metrics:
                stats = user_stats[metric.user_id]
                stats["requests"] += 1
                stats["total_bytes"] += metric.bytes_sent + metric.bytes_received
                stats["unique_endpoints"].add(f"{metric.method} {metric.endpoint}")

                # Update average response time
                current_avg = stats["avg_response_time"]
                request_count = stats["requests"]
                stats["avg_response_time"] = (
                    current_avg * (request_count - 1) + metric.response_time_ms
                ) / request_count

                if metric.response_status >= 400:
                    stats["error_count"] += 1

            # Convert sets to counts and format results
            formatted_stats = {}
            for user_id, stats in user_stats.items():
                formatted_stats[user_id] = {
                    "requests": stats["requests"],
                    "avg_response_time": stats["avg_response_time"],
                    "total_bytes": stats["total_bytes"],
                    "unique_endpoints": len(stats["unique_endpoints"]),
                    "error_count": stats["error_count"],
                    "success_rate": (
                        (stats["requests"] - stats["error_count"]) / stats["requests"]
                    )
                    * 100
                    if stats["requests"] > 0
                    else 0,
                }

            return {
                "time_range_hours": time_range_hours,
                "users": formatted_stats,
                "total_users": len(formatted_stats),
            }

        except Exception as e:
            self.record_error(f"User analytics error: {e}")
            return {"error": f"User analytics failed: {e}"}


class QuotaManager(GatewayBase):
    """Manage user quotas and enforcement."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.tracker: UsageTracker | None = None

    async def initialize(self) -> None:
        """Initialize quota manager."""
        await super().initialize()

    def set_tracker(self, tracker: UsageTracker) -> None:
        """Set the usage tracker for quota management."""
        self.tracker = tracker

    async def create_quota(
        self,
        user_id: str,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        requests_per_month: int = 100000,
        bytes_per_day: int = 10 * 1024 * 1024,
    ) -> bool:
        """Create a quota for a user."""
        if not self.tracker:
            return False

        try:
            quota = QuotaConfig(
                requests_per_hour=requests_per_hour,
                requests_per_day=requests_per_day,
                requests_per_month=requests_per_month,
                bytes_per_day=bytes_per_day,
            )

            self.tracker.set_user_quota(user_id, quota)
            return True

        except Exception as e:
            self.record_error(f"Failed to create quota: {e}")
            return False

    async def update_quota(self, user_id: str, updates: dict[str, int]) -> bool:
        """Update quota limits for a user."""
        if not self.tracker:
            return False

        try:
            current_quota = self.tracker.get_user_quota(user_id)
            updated_quota = QuotaConfig(
                requests_per_hour=updates.get(
                    "requests_per_hour",
                    current_quota.requests_per_hour,
                ),
                requests_per_day=updates.get(
                    "requests_per_day",
                    current_quota.requests_per_day,
                ),
                requests_per_month=updates.get(
                    "requests_per_month",
                    current_quota.requests_per_month,
                ),
                bytes_per_day=updates.get("bytes_per_day", current_quota.bytes_per_day),
            )

            self.tracker.set_user_quota(user_id, updated_quota)
            return True

        except Exception as e:
            self.record_error(f"Failed to update quota: {e}")
            return False

    async def reset_quota(self, user_id: str) -> bool:
        """Reset quota usage for a user."""
        if not self.tracker or user_id not in self.tracker.quota_usage:
            return False

        try:
            current_time = time.time()
            self.tracker.quota_usage[user_id] = QuotaUsage(
                user_id=user_id,
                last_reset_hour=current_time // 3600,
                last_reset_day=current_time // (24 * 3600),
                last_reset_month=current_time,
            )
            return True

        except Exception as e:
            self.record_error(f"Failed to reset quota: {e}")
            return False
