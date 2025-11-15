"""ACB Events System - Event-driven architecture for ACB framework.

Provides a comprehensive event-driven architecture with pub-sub messaging,
event handlers, and integration with message queues and streaming platforms.
Follows ACB's service patterns with discovery, dependency injection, and
health monitoring.

Features:
- Event-driven pub-sub messaging
- Synchronous and asynchronous event handling
- Event filtering and routing
- Message queue integration (Redis, RabbitMQ, Kafka)
- Service discovery and registration
- Health monitoring and metrics
- Integration with ACB Services Layer

Usage:
    # Basic event handling
    from acb.events import create_event, EventPublisher, EventHandler

    # Create and publish events
    event = create_event("user.created", "user_service", {"user_id": 123})

    async with EventPublisher() as publisher:
        await publisher.publish(event)

    # Create event handlers
    @event_handler("user.created")
    async def handle_user_created(event):
        print(f"User created: {event.payload['user_id']}")
        return EventHandlerResult(success=True)

    # Service discovery
    EventPublisher = import_event_handler("publisher")
    EventSubscriber = import_event_handler("subscriber")
"""

from contextlib import suppress

# Core event classes
from ._base import (
    Event,
    EventDeliveryMode,
    EventHandler,
    EventHandlerResult,
    EventMetadata,
    EventPriority,
    EventPublisherBase,
    EventStatus,
    EventSubscription,
    FunctionalEventHandler,
    TypedEventHandler,
    create_event,
    create_subscription,
    event_handler,
    generate_event_id,
)

# Event discovery system
from .discovery import (
    EventCapability,
    EventHandlerDescriptor,
    EventHandlerNotFound,
    EventHandlerNotInstalled,
    EventHandlerStatus,
    apply_event_handler_overrides,
    create_event_metadata_template,
    disable_event_handler,
    enable_event_handler,
    generate_event_handler_id,
    get_event_handler_class,
    get_event_handler_descriptor,
    get_event_handler_info,
    get_event_handler_override,
    import_event_handler,
    list_available_event_handlers,
    list_enabled_event_handlers,
    list_event_handlers,
    list_event_handlers_by_capability,
    register_event_handlers,
    try_import_event_handler,
)
from .discovery import (
    EventMetadata as EventHandlerMetadata,
)

# Publisher implementation
from .publisher import (
    EventPublisher,
    EventPublisherSettings,
    PublisherMetrics,
    create_event_publisher,
    event_publisher_context,
)

# Subscriber implementation
from .subscriber import (
    EventBuffer,
    EventFilter,
    EventRouter,
    EventSubscriber,
    ManagedSubscription,
    SubscriberSettings,
    SubscriptionMode,
    create_event_subscriber,
    event_subscriber_context,
)

__all__ = [
    # Core event classes
    "Event",
    "EventBuffer",
    "EventCapability",
    "EventDeliveryMode",
    "EventFilter",
    "EventHandler",
    "EventHandlerDescriptor",
    # Discovery system
    "EventHandlerMetadata",
    "EventHandlerNotFound",
    "EventHandlerNotInstalled",
    "EventHandlerResult",
    "EventHandlerStatus",
    "EventMetadata",
    "EventPriority",
    # Publisher classes
    "EventPublisher",
    "EventPublisherBase",
    "EventPublisherSettings",
    "EventRouter",
    "EventStatus",
    # Subscriber classes
    "EventSubscriber",
    "EventSubscription",
    # Service integration
    "EventsService",
    "EventsServiceSettings",
    "FunctionalEventHandler",
    "ManagedSubscription",
    "PublisherMetrics",
    "SubscriberSettings",
    "SubscriptionMode",
    "TypedEventHandler",
    "apply_event_handler_overrides",
    "create_event",
    "create_event_metadata_template",
    "create_event_publisher",
    "create_event_subscriber",
    "create_subscription",
    "disable_event_handler",
    "enable_event_handler",
    "event_handler",
    "event_publisher_context",
    "event_subscriber_context",
    "generate_event_handler_id",
    "generate_event_id",
    "get_event_handler_class",
    "get_event_handler_descriptor",
    "get_event_handler_info",
    "get_event_handler_override",
    "get_events_service",
    "import_event_handler",
    "list_available_event_handlers",
    "list_enabled_event_handlers",
    "list_event_handlers",
    "list_event_handlers_by_capability",
    "register_event_handlers",
    "setup_events_service",
    "try_import_event_handler",
]


# Events System metadata following ACB patterns
EVENTS_SYSTEM_VERSION = "1.0.0"
ACB_MIN_VERSION = "0.19.1"


# Service integration with ACB Services Layer
import typing as t

from acb.services import (
    ServiceBase,
    ServiceCapability,
    ServiceMetadata,
    ServiceSettings,
)
from acb.services.discovery import ServiceStatus, generate_service_id


class EventsServiceSettings(ServiceSettings):
    """Settings for the Events System service."""

    # Publisher settings
    enable_publisher: bool = True
    event_topic_prefix: str = "events"  # Topic prefix for queue adapter
    max_concurrent_events: int = 100

    # Subscriber settings
    enable_subscriber: bool = True
    max_subscriptions: int = 1000
    default_subscription_mode: SubscriptionMode = SubscriptionMode.PUSH

    # Performance settings
    enable_buffering: bool = True
    buffer_size: int = 1000
    enable_batching: bool = False
    batch_size: int = 10

    # Health monitoring
    enable_health_checks: bool = True
    health_check_interval: float = 60.0

    # Retry configuration
    enable_retries: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0


class EventsService(ServiceBase):
    """Events System service for ACB framework integration."""

    SERVICE_METADATA = ServiceMetadata(
        service_id=generate_service_id(),
        name="Events Service",
        category="events",
        service_type="messaging",
        version=EVENTS_SYSTEM_VERSION,
        acb_min_version=ACB_MIN_VERSION,
        author="ACB Framework",
        created_date="2024-01-01",
        last_modified="2024-01-01",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.HEALTH_MONITORING,
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.ERROR_HANDLING,
        ],
        description="Event-driven messaging service with pub-sub capabilities",
        settings_class="EventsServiceSettings",
    )

    def __init__(self, settings: EventsServiceSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or EventsServiceSettings()
        self._publisher: EventPublisher | None = None
        self._subscriber: EventSubscriber | None = None

    async def _initialize(self) -> None:
        """Initialize the events service."""
        # Start publisher if enabled
        if self._settings.enable_publisher:
            publisher_settings = EventPublisherSettings(
                event_topic_prefix=self._settings.event_topic_prefix,
                max_concurrent_events=self._settings.max_concurrent_events,
                default_max_retries=self._settings.max_retries,
                default_retry_delay=self._settings.retry_delay,
            )
            self._publisher = EventPublisher(publisher_settings)
            await self._publisher.initialize()

        # Start subscriber if enabled
        if self._settings.enable_subscriber:
            subscriber_settings = SubscriberSettings(
                default_mode=self._settings.default_subscription_mode,
                max_subscriptions=self._settings.max_subscriptions,
                enable_buffering=self._settings.enable_buffering,
                buffer_size=self._settings.buffer_size,
                enable_batching=self._settings.enable_batching,
                batch_size=self._settings.batch_size,
                enable_health_checks=self._settings.enable_health_checks,
                health_check_interval=self._settings.health_check_interval,
                enable_retries=self._settings.enable_retries,
                max_retries=self._settings.max_retries,
                retry_delay=self._settings.retry_delay,
            )
            self._subscriber = EventSubscriber(subscriber_settings)
            await self._subscriber.initialize()

    async def _shutdown(self) -> None:
        """Shutdown the events service."""
        if self._publisher:
            await self._publisher.shutdown()
            self._publisher = None

        if self._subscriber:
            await self._subscriber.shutdown()
            self._subscriber = None

    @property
    def publisher(self) -> EventPublisher | None:
        """Get the event publisher."""
        return self._publisher

    @property
    def subscriber(self) -> EventSubscriber | None:
        """Get the event subscriber."""
        return self._subscriber

    async def publish(self, event: Event) -> None:
        """Publish an event."""
        if not self._publisher:
            msg = "Publisher not enabled"
            raise RuntimeError(msg)
        await self._publisher.publish(event)

    async def subscribe(
        self,
        handler: EventHandler,
        event_type: str | None = None,
        **kwargs: t.Any,
    ) -> str:
        """Subscribe to events."""
        if not self._subscriber:
            msg = "Subscriber not enabled"
            raise RuntimeError(msg)
        sub_id = await self._subscriber.subscribe(handler, event_type, **kwargs)
        return str(sub_id)

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if not self._subscriber:
            return False
        from uuid import UUID

        return await self._subscriber.unsubscribe(UUID(subscription_id))


# Global events service instance
_events_service: EventsService | None = None


def get_events_service() -> EventsService:
    """Get the global events service instance."""
    global _events_service
    if _events_service is None:
        _events_service = EventsService()
    return _events_service


async def setup_events_service(
    settings: EventsServiceSettings | None = None,
) -> EventsService:
    """Setup and start the events service.

    Args:
        settings: Events service settings

    Returns:
        Initialized EventsService instance
    """
    global _events_service
    _events_service = EventsService(settings)
    await _events_service.initialize()

    # Register with ACB dependency injection
    from acb.depends import depends

    depends.set(EventsService, _events_service)

    return _events_service


# Integration with Services Layer discovery
from acb.services.discovery import enable_service

# Register events service in service discovery
with suppress(Exception):
    enable_service("events", "events_service")
# Service registry may not be initialized yet
