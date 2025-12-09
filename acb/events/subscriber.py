"""Event Subscriber and Routing System.

Provides subscriber management, event routing, and subscription lifecycle
for the ACB Events System using the unified messaging adapter's pub/sub backend.
Supports both pull and push subscription models with advanced filtering and routing.

Features:
- Pub/sub messaging backend integration
- Event subscription management
- Advanced event filtering and routing
- Pull and push subscription models
- Event buffering and batching
- Subscription health monitoring
"""

from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from enum import Enum
from uuid import UUID

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from acb.services import ServiceBase, ServiceSettings

from ._base import (
    Event,
    EventHandler,
    EventHandlerResult,
    EventSubscription,
)


class SubscriptionMode(Enum):
    """Subscription delivery modes."""

    PUSH = "push"  # Events are pushed to handlers
    PULL = "pull"  # Handlers pull events from queue
    HYBRID = "hybrid"  # Mix of push and pull based on conditions


class SubscriberSettings(ServiceSettings):
    """Settings for event subscriber configuration."""

    # Subscription configuration
    default_mode: SubscriptionMode = Field(default=SubscriptionMode.PUSH)
    max_subscriptions: int = Field(
        default=1000,
        description="Maximum number of subscriptions",
    )
    subscription_timeout: float = Field(
        default=30.0,
        description="Default subscription timeout",
    )

    # Buffer configuration
    enable_buffering: bool = Field(default=True)
    buffer_size: int = Field(
        default=1000,
        description="Maximum events in buffer per subscription",
    )
    buffer_timeout: float = Field(default=5.0, description="Buffer flush timeout")

    # Batch processing
    enable_batching: bool = Field(default=False)
    batch_size: int = Field(default=10, description="Events per batch")
    batch_timeout: float = Field(default=1.0, description="Batch timeout")

    # Performance settings
    max_concurrent_handlers: int = Field(default=100)
    handler_timeout: float = Field(default=30.0)

    # Health monitoring
    health_check_enabled: bool = Field(default=True)

    # Retry configuration
    enable_retries: bool = Field(default=True)
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=1.0)


class EventFilter(BaseModel):
    """Event filtering configuration."""

    # Basic filters
    event_types: list[str] | None = Field(
        default=None,
        description="Allowed event types",
    )
    sources: list[str] | None = Field(default=None, description="Allowed event sources")
    tags: list[str] | None = Field(default=None, description="Required tags")

    # Content filters
    payload_filters: dict[str, t.Any] | None = Field(
        default=None,
        description="Payload field filters",
    )
    header_filters: dict[str, t.Any] | None = Field(
        default=None,
        description="Header field filters",
    )

    # Pattern matching
    event_type_patterns: list[str] | None = Field(
        default=None,
        description="Event type regex patterns",
    )
    source_patterns: list[str] | None = Field(
        default=None,
        description="Source regex patterns",
    )

    # Priority and routing
    min_priority: str | None = Field(default=None, description="Minimum event priority")
    routing_keys: list[str] | None = Field(
        default=None,
        description="Required routing keys",
    )

    def matches(self, event: Event) -> bool:
        """Check if event matches this filter."""
        return (
            self._matches_basic_filters(event)
            and self._matches_content_filters(event)
            and self._matches_pattern_filters(event)
            and self._matches_priority_filter(event)
            and self._matches_routing_keys(event)
        )

    def _matches_basic_filters(self, event: Event) -> bool:
        """Check basic event type, source, and tags filters."""
        # Check event types
        if self.event_types and event.metadata.event_type not in self.event_types:
            return False

        # Check sources
        if self.sources and event.metadata.source not in self.sources:
            return False

        # Check tags
        if self.tags:
            required_tags = set(self.tags)
            if not required_tags.issubset(set(event.metadata.tags)):
                return False

        return True

    def _matches_content_filters(self, event: Event) -> bool:
        """Check payload and header content filters."""
        # Check payload filters
        if self.payload_filters:
            for key, expected_value in self.payload_filters.items():
                if key not in event.payload or event.payload[key] != expected_value:
                    return False

        # Check header filters
        if self.header_filters:
            for key, expected_value in self.header_filters.items():
                if (
                    key not in event.metadata.headers
                    or event.metadata.headers[key] != expected_value
                ):
                    return False

        return True

    def _matches_pattern_filters(self, event: Event) -> bool:
        """Check regex pattern filters for event type and source."""
        import re

        # Check event type patterns
        if self.event_type_patterns and not any(
            re.match(
                pattern,
                event.metadata.event_type,
            )  # REGEX OK: User-provided pattern matching for event filtering
            for pattern in self.event_type_patterns
        ):
            return False

        # Check source patterns
        if self.source_patterns and not any(
            re.match(
                pattern,
                event.metadata.source,
            )  # REGEX OK: User-provided pattern matching for source filtering
            for pattern in self.source_patterns
        ):
            return False

        return True

    def _matches_priority_filter(self, event: Event) -> bool:
        """Check minimum priority filter using match statement."""
        if not self.min_priority:
            return True

        # Use match statement for priority comparison
        match self.min_priority:
            case "low":
                min_level = 0
            case "normal":
                min_level = 1
            case "high":
                min_level = 2
            case "critical":
                min_level = 3
            case _:
                min_level = 0

        match event.metadata.priority.value:
            case "low":
                event_level = 0
            case "normal":
                event_level = 1
            case "high":
                event_level = 2
            case "critical":
                event_level = 3
            case _:
                event_level = 0

        return event_level >= min_level

    def _matches_routing_keys(self, event: Event) -> bool:
        """Check routing key filters."""
        if not self.routing_keys:
            return True

        return (
            event.metadata.routing_key is not None
            and event.metadata.routing_key in self.routing_keys
        )


class EventBuffer:
    """Event buffer for subscription event queuing."""

    def __init__(self, max_size: int = 1000, timeout: float = 5.0) -> None:
        self._buffer: deque[Event] = deque(maxlen=max_size)
        self._max_size = max_size
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)

    async def put(self, event: Event) -> None:
        """Add event to buffer."""
        async with self._lock:
            self._buffer.append(event)
            self._not_empty.notify()

    async def get(self, timeout: float | None = None) -> Event | None:
        """Get next event from buffer."""
        async with self._not_empty:
            while not self._buffer:
                try:
                    await asyncio.wait_for(
                        self._not_empty.wait(),
                        timeout=timeout or self._timeout,
                    )
                except TimeoutError:
                    return None

            return self._buffer.popleft()

    async def get_batch(
        self,
        batch_size: int,
        timeout: float | None = None,
    ) -> list[Event]:
        """Get a batch of events from buffer."""
        events = []
        batch_timeout = timeout or self._timeout

        # Get first event (wait if necessary)
        first_event = await self.get(batch_timeout)
        if first_event:
            events.append(first_event)

        # Get remaining events (non-blocking)
        for _ in range(batch_size - 1):
            try:
                event = await asyncio.wait_for(self.get(0.01), timeout=0.01)
                if event:
                    events.append(event)
                else:
                    break
            except TimeoutError:
                break

        return events

    def size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)

    def is_full(self) -> bool:
        """Check if buffer is full."""
        return len(self._buffer) >= self._max_size

    async def clear(self) -> list[Event]:
        """Clear buffer and return all events."""
        async with self._lock:
            events = list(self._buffer)
            self._buffer.clear()
            return events


class ManagedSubscription(BaseModel):
    """Managed subscription with routing and health tracking."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subscription: EventSubscription
    filter: EventFilter | None = None
    mode: SubscriptionMode = SubscriptionMode.PUSH
    buffer: EventBuffer | None = None

    # Health tracking
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    events_processed: int = 0
    events_failed: int = 0
    avg_processing_time: float = 0.0

    # State management
    active: bool = True
    paused: bool = False
    error_count: int = 0
    last_error: str | None = None

    def record_success(self, processing_time: float) -> None:
        """Record successful event processing."""
        self.last_activity = datetime.now()
        self.events_processed += 1
        # Update running average
        if self.events_processed == 1:
            self.avg_processing_time = processing_time
        else:
            self.avg_processing_time = (
                self.avg_processing_time * (self.events_processed - 1) + processing_time
            ) / self.events_processed

    def record_failure(self, error: str) -> None:
        """Record failed event processing."""
        self.last_activity = datetime.now()
        self.events_failed += 1
        self.error_count += 1
        self.last_error = error

    def get_health_score(self) -> float:
        """Calculate health score (0.0 to 1.0)."""
        if self.events_processed + self.events_failed == 0:
            return 1.0

        success_rate = self.events_processed / (
            self.events_processed + self.events_failed
        )
        error_penalty = min(self.error_count * 0.1, 0.5)  # Max 50% penalty
        return max(0.0, success_rate - error_penalty)

    def is_healthy(self, min_score: float = 0.7) -> bool:
        """Check if subscription is healthy."""
        return self.active and not self.paused and self.get_health_score() >= min_score


class EventRouter:
    """Event routing engine for subscriptions."""

    def __init__(self) -> None:
        self._type_routes: dict[str, list[ManagedSubscription]] = defaultdict(list)
        self._wildcard_routes: list[ManagedSubscription] = []
        self._filtered_routes: list[ManagedSubscription] = []

    def add_subscription(self, managed_sub: ManagedSubscription) -> None:
        """Add subscription to routing tables."""
        if managed_sub.subscription.event_type:
            self._type_routes[managed_sub.subscription.event_type].append(managed_sub)
        elif managed_sub.filter:
            self._filtered_routes.append(managed_sub)
        else:
            self._wildcard_routes.append(managed_sub)

    def remove_subscription(self, subscription_id: UUID) -> bool:
        """Remove subscription from routing tables."""
        # Check type routes
        for subs in self._type_routes.values():
            for i, managed_sub in enumerate(subs):
                if managed_sub.subscription.subscription_id == subscription_id:
                    subs.pop(i)
                    return True

        # Check wildcard routes
        for i, managed_sub in enumerate(self._wildcard_routes):
            if managed_sub.subscription.subscription_id == subscription_id:
                self._wildcard_routes.pop(i)
                return True

        # Check filtered routes
        for i, managed_sub in enumerate(self._filtered_routes):
            if managed_sub.subscription.subscription_id == subscription_id:
                self._filtered_routes.pop(i)
                return True

        return False

    def find_matching_subscriptions(self, event: Event) -> list[ManagedSubscription]:
        """Find all subscriptions that should receive this event."""
        matching = []

        # Check type-specific routes
        type_subs = self._type_routes.get(event.metadata.event_type, [])
        for managed_sub in type_subs:
            if self._subscription_matches(managed_sub, event):
                matching.append(managed_sub)

        # Check filtered routes
        for managed_sub in self._filtered_routes:
            if self._subscription_matches(managed_sub, event):
                matching.append(managed_sub)

        # Check wildcard routes
        for managed_sub in self._wildcard_routes:
            if self._subscription_matches(managed_sub, event):
                matching.append(managed_sub)

        return matching

    def _subscription_matches(
        self,
        managed_sub: ManagedSubscription,
        event: Event,
    ) -> bool:
        """Check if a managed subscription matches an event."""
        if not managed_sub.active or managed_sub.paused:
            return False

        # Check subscription-level matching
        if not managed_sub.subscription.matches(event):
            return False

        # Check filter-level matching
        return not (managed_sub.filter and not managed_sub.filter.matches(event))


class EventSubscriber(ServiceBase):
    """Event subscriber with routing and subscription management using queue adapter."""

    def __init__(self, settings: SubscriberSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or SubscriberSettings()
        self._router = EventRouter()
        self._subscriptions: dict[UUID, ManagedSubscription] = {}

        # PubSub adapter integration (lazy initialization)
        self._pubsub: t.Any = None
        self._pubsub_class: t.Any = None

        # Processing control
        self._processing_semaphore = asyncio.Semaphore(
            self._settings.max_concurrent_handlers,
        )
        self._shutdown_event = asyncio.Event()

        # Health monitoring
        self._health_check_task: asyncio.Task[None] | None = None

    async def _initialize(self) -> None:
        """Initialize the event subscriber (ServiceBase requirement)."""
        # Start health monitoring if enabled
        if self._settings.health_check_enabled:
            self._health_check_task = asyncio.create_task(self._health_check_worker())

        self.logger.info("Event subscriber started")

    async def _shutdown(self) -> None:
        """Shutdown the event subscriber (ServiceBase requirement)."""
        self._shutdown_event.set()

        # Stop health monitoring
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._health_check_task

        self.logger.info("Event subscriber stopped")

    async def start(self) -> None:
        """Start the event subscriber (public API)."""
        await self.initialize()

    async def stop(self) -> None:
        """Stop the event subscriber (public API)."""
        await self.shutdown()

    async def subscribe(
        self,
        handler: EventHandler,
        event_type: str | None = None,
        event_filter: EventFilter | None = None,
        mode: SubscriptionMode | None = None,
        **subscription_kwargs: t.Any,
    ) -> UUID:
        """Create a new event subscription.

        Args:
            handler: Event handler instance
            event_type: Specific event type to subscribe to
            event_filter: Advanced event filtering
            mode: Subscription mode (push/pull/hybrid)
            **subscription_kwargs: Additional subscription options

        Returns:
            Subscription ID
        """
        if len(self._subscriptions) >= self._settings.max_subscriptions:
            msg = "Maximum number of subscriptions reached"
            raise ValueError(msg)

        # Create subscription
        subscription = EventSubscription(
            handler=handler,
            event_type=event_type,
            **subscription_kwargs,
        )

        # Create buffer if needed
        buffer = None
        sub_mode = mode or self._settings.default_mode
        if self._settings.enable_buffering and sub_mode in (
            SubscriptionMode.PULL,
            SubscriptionMode.HYBRID,
        ):
            buffer = EventBuffer(
                max_size=self._settings.buffer_size,
                timeout=self._settings.buffer_timeout,
            )

        # Create managed subscription
        managed_sub = ManagedSubscription(
            subscription=subscription,
            filter=event_filter,
            mode=sub_mode,
            buffer=buffer,
        )

        # Register subscription
        self._subscriptions[subscription.subscription_id] = managed_sub
        self._router.add_subscription(managed_sub)

        self.logger.debug(
            "Added subscription: %s (handler=%s, event_type=%s)",
            subscription.subscription_id,
            handler.handler_name,
            event_type,
        )

        return subscription.subscription_id

    async def unsubscribe(self, subscription_id: UUID) -> bool:
        """Remove an event subscription.

        Args:
            subscription_id: ID of subscription to remove

        Returns:
            True if subscription was found and removed
        """
        if subscription_id not in self._subscriptions:
            return False

        # Remove from router
        self._router.remove_subscription(subscription_id)

        # Remove from subscriptions
        managed_sub = self._subscriptions.pop(subscription_id)

        # Clear buffer if exists
        if managed_sub.buffer:
            await managed_sub.buffer.clear()

        self.logger.debug("Removed subscription: %s", subscription_id)
        return True

    async def deliver_event(self, event: Event) -> dict[UUID, EventHandlerResult]:
        """Deliver event to matching subscriptions.

        Args:
            event: Event to deliver

        Returns:
            Dict mapping subscription IDs to handler results
        """
        # Find matching subscriptions
        matching_subs = self._router.find_matching_subscriptions(event)

        if not matching_subs:
            return {}

        # Process subscriptions based on mode
        results: dict[UUID, EventHandlerResult] = {}
        tasks: list[tuple[UUID, asyncio.Task[t.Any]]] = []

        for managed_sub in matching_subs:
            await self._process_subscription_by_mode(managed_sub, event, results, tasks)

        # Wait for push deliveries
        if tasks:
            await self._handle_completed_push_deliveries(tasks, results)

        return results

    async def _process_subscription_by_mode(
        self,
        managed_sub: ManagedSubscription,
        event: Event,
        results: dict[UUID, EventHandlerResult],
        tasks: list[tuple[UUID, asyncio.Task[t.Any]]],
    ) -> None:
        """Process a subscription based on its mode (PUSH, PULL, or HYBRID)."""
        if managed_sub.mode == SubscriptionMode.PUSH:
            task = asyncio.create_task(self._deliver_push(event, managed_sub))
            tasks.append((managed_sub.subscription.subscription_id, task))
        elif managed_sub.mode in (SubscriptionMode.PULL, SubscriptionMode.HYBRID):
            # Add to buffer for pull-based consumption
            if managed_sub.buffer:
                await managed_sub.buffer.put(event)
                results[managed_sub.subscription.subscription_id] = EventHandlerResult(
                    success=True
                )

    async def _handle_completed_push_deliveries(
        self,
        tasks: list[tuple[UUID, asyncio.Task[t.Any]]],
        results: dict[UUID, EventHandlerResult],
    ) -> None:
        """Handle completed push delivery tasks and update results."""
        completed_tasks = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True,
        )

        for (sub_id, _), result in zip(tasks, completed_tasks, strict=False):
            if isinstance(result, Exception):
                results[sub_id] = EventHandlerResult(
                    success=False,
                    error_message=str(result),
                )
            elif isinstance(result, EventHandlerResult):
                results[sub_id] = result
            else:
                # Handle unexpected result type
                results[sub_id] = EventHandlerResult(
                    success=False,
                    error_message="Unexpected result type",
                )

    async def pull_events(
        self,
        subscription_id: UUID,
        batch_size: int = 1,
        timeout: float | None = None,
    ) -> list[Event]:
        """Pull events for a subscription (pull mode).

        Args:
            subscription_id: Subscription ID
            batch_size: Maximum number of events to return
            timeout: Pull timeout

        Returns:
            List of events
        """
        managed_sub = self._subscriptions.get(subscription_id)
        if not managed_sub or not managed_sub.buffer:
            return []

        if batch_size == 1:
            event = await managed_sub.buffer.get(timeout)
            return [event] if event else []
        return await managed_sub.buffer.get_batch(batch_size, timeout)

    async def _deliver_push(
        self,
        event: Event,
        managed_sub: ManagedSubscription,
    ) -> EventHandlerResult:
        """Deliver event using push mode."""
        async with self._processing_semaphore:
            start_time = asyncio.get_event_loop().time()

            try:
                # Apply timeout
                result = await asyncio.wait_for(
                    managed_sub.subscription.handler.handle(event),
                    timeout=self._settings.handler_timeout,
                )

                # Record success
                processing_time = asyncio.get_event_loop().time() - start_time
                managed_sub.record_success(processing_time)

                return result

            except TimeoutError:
                error_msg = f"Handler timeout after {self._settings.handler_timeout}s"
                managed_sub.record_failure(error_msg)
                return EventHandlerResult(success=False, error_message=error_msg)

            except Exception as e:
                error_msg = str(e)
                managed_sub.record_failure(error_msg)
                return await managed_sub.subscription.handler.handle_error(event, e)

    async def _health_check_worker(self) -> None:
        """Background worker for subscription health monitoring."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.health_check_interval)

                unhealthy_subs = [
                    sub_id
                    for sub_id, managed_sub in self._subscriptions.items()
                    if not managed_sub.is_healthy()
                ]

                if unhealthy_subs:
                    self.logger.warning(
                        "Found %d unhealthy subscriptions: %s",
                        len(unhealthy_subs),
                        unhealthy_subs,
                    )

            except Exception as e:
                self.logger.exception("Health check error: %s", e)

    # Subscription management methods
    async def pause_subscription(self, subscription_id: UUID) -> bool:
        """Pause a subscription."""
        managed_sub = self._subscriptions.get(subscription_id)
        if managed_sub:
            managed_sub.paused = True
            return True
        return False

    async def resume_subscription(self, subscription_id: UUID) -> bool:
        """Resume a paused subscription."""
        managed_sub = self._subscriptions.get(subscription_id)
        if managed_sub:
            managed_sub.paused = False
            return True
        return False

    async def get_subscription_stats(
        self,
        subscription_id: UUID,
    ) -> dict[str, t.Any] | None:
        """Get statistics for a subscription."""
        managed_sub = self._subscriptions.get(subscription_id)
        if not managed_sub:
            return None

        return {
            "subscription_id": str(subscription_id),
            "handler_name": managed_sub.subscription.handler.handler_name,
            "event_type": managed_sub.subscription.event_type,
            "mode": managed_sub.mode.value,
            "active": managed_sub.active,
            "paused": managed_sub.paused,
            "events_processed": managed_sub.events_processed,
            "events_failed": managed_sub.events_failed,
            "avg_processing_time": managed_sub.avg_processing_time,
            "health_score": managed_sub.get_health_score(),
            "buffer_size": managed_sub.buffer.size() if managed_sub.buffer else 0,
        }

    async def get_all_subscription_stats(self) -> list[dict[str, t.Any]]:
        """Get statistics for all subscriptions."""
        return [
            sub_stats
            for sub_id in self._subscriptions
            if (sub_stats := await self.get_subscription_stats(sub_id)) is not None
        ]

    @property
    def is_running(self) -> bool:
        """Check if the subscriber is currently running."""
        from acb.services import ServiceStatus

        return self.status == ServiceStatus.ACTIVE

    # Context manager support (delegating to ServiceBase)
    async def __aenter__(self) -> "EventSubscriber":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        await self.shutdown()


# Factory function
def create_event_subscriber(**settings_kwargs: t.Any) -> EventSubscriber:
    """Create an event subscriber with specified settings.

    Args:
        **settings_kwargs: Settings overrides

    Returns:
        Configured EventSubscriber instance
    """
    settings = SubscriberSettings(**settings_kwargs)
    return EventSubscriber(settings)


# Convenience context manager
@asynccontextmanager
async def event_subscriber_context(
    settings: SubscriberSettings | None = None,
) -> AsyncGenerator[EventSubscriber]:
    """Context manager for event subscriber lifecycle.

    Args:
        settings: Subscriber settings

    Yields:
        Started EventSubscriber instance
    """
    subscriber = EventSubscriber(settings)
    try:
        await subscriber.initialize()
        yield subscriber
    finally:
        await subscriber.shutdown()
