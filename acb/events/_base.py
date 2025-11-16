"""Base classes for ACB Events System.

Provides the foundation for event-driven architecture with support for
both synchronous and asynchronous event handling. Follows ACB's adapter
pattern with discovery metadata and service integration.

Features:
- Base Event and EventHandler classes
- Event metadata and routing information
- Support for sync/async handlers
- Automatic error handling and retries
- Integration with ACB's dependency injection
"""

from abc import ABC, abstractmethod
from enum import Enum
from uuid import UUID

import asyncio
import typing as t
from contextlib import suppress
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from acb.services import ServiceBase, ServiceCapability, ServiceMetadata
from acb.services.discovery import ServiceStatus

# Event handling imports
uuid_lib: t.Any
try:
    import uuid_utils

    _uuid7_available = True
    uuid_lib = uuid_utils
except ImportError:
    import uuid

    _uuid7_available = False
    uuid_lib = uuid


class EventPriority(Enum):
    """Event priority levels for processing order."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(Enum):
    """Event processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class EventDeliveryMode(Enum):
    """Event delivery modes."""

    FIRE_AND_FORGET = "fire_and_forget"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"
    BROADCAST = "broadcast"


def generate_event_id() -> UUID:
    """Generate a UUID for event identification."""
    if _uuid7_available:
        uuid_obj = uuid_lib.uuid7()
        return UUID(str(uuid_obj))
    uuid_obj = uuid_lib.uuid4()
    return UUID(str(uuid_obj))


class EventMetadata(BaseModel):
    """Event metadata for routing and processing."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    event_id: UUID = Field(default_factory=generate_event_id)
    event_type: str = Field(description="Type identifier for this event")
    source: str = Field(description="Source component that generated the event")
    timestamp: datetime = Field(default_factory=datetime.now)

    priority: EventPriority = Field(default=EventPriority.NORMAL)
    delivery_mode: EventDeliveryMode = Field(default=EventDeliveryMode.FIRE_AND_FORGET)

    # Routing information
    routing_key: str | None = Field(
        default=None,
        description="Routing key for targeted delivery",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for request tracking",
    )
    reply_to: str | None = Field(default=None, description="Response destination")

    # Processing control
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(
        default=1.0,
        description="Initial retry delay in seconds",
    )
    timeout: float | None = Field(
        default=None,
        description="Processing timeout in seconds",
    )

    # Custom metadata
    headers: dict[str, t.Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class Event(BaseModel):
    """Base event class for all events in the system."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    metadata: EventMetadata
    payload: dict[str, t.Any] = Field(default_factory=dict)

    # Processing state
    status: EventStatus = Field(default=EventStatus.PENDING)
    retry_count: int = Field(default=0)
    error_message: str | None = Field(default=None)

    def __str__(self) -> str:
        return f"Event({self.metadata.event_type}, {self.metadata.event_id})"

    def __repr__(self) -> str:
        return (
            f"Event(event_type={self.metadata.event_type!r}, "
            f"event_id={self.metadata.event_id}, "
            f"status={self.status.value})"
        )

    def is_expired(self) -> bool:
        """Check if the event has expired based on timeout."""
        if not self.metadata.timeout:
            return False

        elapsed = (datetime.now() - self.metadata.timestamp).total_seconds()
        return elapsed > self.metadata.timeout

    def can_retry(self) -> bool:
        """Check if the event can be retried."""
        return (
            self.status == EventStatus.FAILED
            and self.retry_count < self.metadata.max_retries
        )

    def mark_processing(self) -> None:
        """Mark event as being processed."""
        self.status = EventStatus.PROCESSING

    def mark_completed(self) -> None:
        """Mark event as successfully completed."""
        self.status = EventStatus.COMPLETED

    def mark_failed(self, error: str) -> None:
        """Mark event as failed with error message."""
        self.status = EventStatus.FAILED
        self.error_message = error

    def mark_retrying(self) -> None:
        """Mark event for retry."""
        self.status = EventStatus.RETRYING
        self.retry_count += 1


class EventHandlerResult(BaseModel):
    """Result of event handler execution."""

    success: bool
    error_message: str | None = None
    retry_after: float | None = None
    metadata: dict[str, t.Any] = Field(default_factory=dict)


class EventHandler(ABC):
    """Abstract base class for event handlers."""

    def __init__(self) -> None:
        self._handler_id = str(generate_event_id())
        self._handler_name = self.__class__.__name__

    @property
    def handler_id(self) -> str:
        """Get unique handler identifier."""
        return self._handler_id

    @property
    def handler_name(self) -> str:
        """Get handler name."""
        return self._handler_name

    @abstractmethod
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can process the given event.

        Args:
            event: Event to check

        Returns:
            True if this handler can process the event
        """

    @abstractmethod
    async def handle(self, event: Event) -> EventHandlerResult:
        """Handle an event asynchronously.

        Args:
            event: Event to process

        Returns:
            Result of event processing
        """

    async def handle_error(self, event: Event, error: Exception) -> EventHandlerResult:
        """Handle errors during event processing.

        Args:
            event: Event that caused the error
            error: Exception that occurred

        Returns:
            Result indicating error handling outcome
        """
        return EventHandlerResult(
            success=False,
            error_message=str(error),
            retry_after=event.metadata.retry_delay if event.can_retry() else None,
        )

    def __str__(self) -> str:
        return f"{self.handler_name}({self.handler_id})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(handler_id={self.handler_id!r})"


class TypedEventHandler[EventType: Event](EventHandler):
    """Typed event handler for specific event types."""

    def __init__(self, event_type: str) -> None:
        super().__init__()
        self._event_type = event_type

    @property
    def event_type(self) -> str:
        """Get the event type this handler processes."""
        return self._event_type

    def can_handle(self, event: Event) -> bool:
        """Check if this handler can process the given event type."""
        return event.metadata.event_type == self._event_type

    async def handle(self, event: Event) -> EventHandlerResult:
        """Handle the event. Subclasses should override this method."""
        return EventHandlerResult(success=True)


class FunctionalEventHandler(EventHandler):
    """Event handler that wraps a function."""

    def __init__(
        self,
        handler_func: t.Callable[
            [Event],
            EventHandlerResult | t.Awaitable[EventHandlerResult],
        ],
        event_type: str | None = None,
        predicate: t.Callable[[Event], bool] | None = None,
    ) -> None:
        super().__init__()
        self._handler_func = handler_func
        self._event_type = event_type
        self._predicate = predicate
        self._is_async = asyncio.iscoroutinefunction(handler_func)

    def can_handle(self, event: Event) -> bool:
        """Check if this handler can process the given event."""
        if self._event_type and event.metadata.event_type != self._event_type:
            return False

        if self._predicate:
            return self._predicate(event)

        return True

    async def handle(self, event: Event) -> EventHandlerResult:
        """Handle event using the wrapped function."""
        try:
            if self._is_async:
                result: EventHandlerResult | t.Awaitable[EventHandlerResult] = (
                    self._handler_func(event)
                )
                # Type narrowing: result is an awaitable in this branch
                if isinstance(result, EventHandlerResult):
                    # Already a result, return it
                    return result
                # Must be awaitable, await it
                result = await result
            else:
                result = self._handler_func(event)

            if isinstance(result, EventHandlerResult):
                return result

            # Convert other return types to EventHandlerResult
            return EventHandlerResult(success=bool(result))

        except Exception as e:
            return await self.handle_error(event, e)


class EventSubscription(BaseModel):
    """Event subscription configuration."""

    subscription_id: UUID = Field(default_factory=generate_event_id)
    handler: EventHandler = Field(description="Event handler instance")
    event_type: str | None = Field(
        default=None,
        description="Specific event type to subscribe to",
    )
    predicate: t.Callable[[Event], bool] | None = Field(
        default=None,
        description="Custom event filter",
    )

    # Subscription options
    active: bool = Field(default=True)
    max_concurrent: int = Field(
        default=1,
        description="Maximum concurrent event processing",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def matches(self, event: Event) -> bool:
        """Check if this subscription matches the given event."""
        if not self.active:
            return False

        if self.event_type and event.metadata.event_type != self.event_type:
            return False

        if self.predicate and not self.predicate(event):
            return False

        return self.handler.can_handle(event)


class EventPublisherBase(ServiceBase):
    """Base class for event publishers with service integration."""

    SERVICE_METADATA = ServiceMetadata(
        service_id=generate_event_id(),
        name="Event Publisher",
        category="events",
        service_type="publisher",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework",
        created_date=datetime.now().isoformat(),
        last_modified=datetime.now().isoformat(),
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.ERROR_HANDLING,
            ServiceCapability.METRICS_COLLECTION,
        ],
        description="Event publisher for pub-sub messaging with ACB integration",
        settings_class="EventPublisherSettings",
    )

    def __init__(self) -> None:
        super().__init__()
        self._subscriptions: list[EventSubscription] = []
        self._active_tasks: dict[UUID, asyncio.Task[None]] = {}

    @abstractmethod
    async def publish(self, event: Event) -> None:
        """Publish an event to subscribers.

        Args:
            event: Event to publish
        """

    @abstractmethod
    async def subscribe(self, subscription: EventSubscription) -> None:
        """Add an event subscription.

        Args:
            subscription: Subscription configuration
        """

    @abstractmethod
    async def unsubscribe(self, subscription_id: UUID) -> bool:
        """Remove an event subscription.

        Args:
            subscription_id: ID of subscription to remove

        Returns:
            True if subscription was found and removed
        """

    async def get_subscriptions(self) -> list[EventSubscription]:
        """Get all active subscriptions."""
        return [sub for sub in self._subscriptions if sub.active]

    async def get_subscription_count(self) -> int:
        """Get count of active subscriptions."""
        return len([sub for sub in self._subscriptions if sub.active])

    async def clear_subscriptions(self) -> None:
        """Clear all subscriptions."""
        # Cancel any active tasks
        for task in self._active_tasks.values():
            if not task.done():
                task.cancel()

        with suppress(Exception):
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
        # Ignore cancellation exceptions

        self._active_tasks.clear()
        self._subscriptions.clear()


# Event creation helpers
def create_event(
    event_type: str,
    source: str,
    payload: dict[str, t.Any] | None = None,
    **metadata_kwargs: t.Any,
) -> Event:
    """Create a new event with metadata.

    Args:
        event_type: Type identifier for the event
        source: Source component generating the event
        payload: Event payload data
        **metadata_kwargs: Additional metadata fields

    Returns:
        New Event instance
    """
    metadata = EventMetadata(
        event_type=event_type,
        source=source,
        **metadata_kwargs,
    )

    return Event(
        metadata=metadata,
        payload=payload or {},
    )


def create_subscription(
    handler: EventHandler,
    event_type: str | None = None,
    predicate: t.Callable[[Event], bool] | None = None,
    **subscription_kwargs: t.Any,
) -> EventSubscription:
    """Create a new event subscription.

    Args:
        handler: Event handler instance
        event_type: Specific event type to subscribe to
        predicate: Custom event filter function
        **subscription_kwargs: Additional subscription options

    Returns:
        New EventSubscription instance
    """
    return EventSubscription(
        handler=handler,
        event_type=event_type,
        predicate=predicate,
        **subscription_kwargs,
    )


# Decorator for creating functional event handlers
def event_handler(
    event_type: str | None = None,
    predicate: t.Callable[[Event], bool] | None = None,
) -> t.Callable[
    [
        t.Callable[
            [Event],
            EventHandlerResult | t.Awaitable[EventHandlerResult],
        ]
    ],
    FunctionalEventHandler,
]:
    """Decorator to create an event handler from a function.

    Args:
        event_type: Specific event type to handle
        predicate: Custom event filter function

    Returns:
        Decorator function
    """

    def decorator(
        func: t.Callable[
            [Event],
            EventHandlerResult | t.Awaitable[EventHandlerResult],
        ],
    ) -> FunctionalEventHandler:
        return FunctionalEventHandler(
            handler_func=func,
            event_type=event_type,
            predicate=predicate,
        )

    return decorator
