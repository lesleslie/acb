"""Event Publisher implementation for ACB Events System.

Provides a high-performance, async-first event publisher using the unified queue
adapter backend. Supports pub-sub patterns, event ordering, and delivery guarantees
through pluggable queue backends (memory, Redis, RabbitMQ).

Features:
- Unified queue adapter backend integration
- In-memory and distributed messaging support
- Event ordering and delivery guarantees
- Automatic retries and error handling
- Metrics collection and health monitoring
"""

import asyncio
import logging
import typing as t
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from pydantic import BaseModel, Field
from acb.adapters import import_adapter
from acb.depends import depends
from acb.services import ServiceSettings

from ._base import (
    Event,
    EventHandlerResult,
    EventPublisherBase,
    EventSubscription,
)


class EventPublisherSettings(ServiceSettings):
    """Settings for event publisher configuration."""

    # Queue backend configuration (uses queue adapter from settings/adapters.yml)
    event_topic_prefix: str = Field(
        default="events",
        description="Prefix for event topics",
    )

    # Performance settings
    max_concurrent_events: int = Field(
        default=100,
        description="Maximum concurrent event processing",
    )
    batch_size: int = Field(default=10, description="Batch size for bulk operations")
    flush_interval: float = Field(
        default=1.0,
        description="Batch flush interval in seconds",
    )

    # Retry configuration
    default_max_retries: int = Field(default=3)
    default_retry_delay: float = Field(default=1.0)
    exponential_backoff: bool = Field(default=True)
    max_retry_delay: float = Field(default=30.0)

    # Timeout settings
    default_timeout: float = Field(default=30.0)
    subscription_timeout: float = Field(default=5.0)

    # Queue configuration
    queue_max_size: int = Field(default=10000)
    dead_letter_queue: bool = Field(default=True)

    # Monitoring
    enable_metrics: bool = Field(default=True)
    log_events: bool = Field(default=False)


class PublisherMetrics(BaseModel):
    """Metrics for event publisher monitoring."""

    # ServiceMetrics base fields
    initialized_at: float | None = None
    requests_handled: int = 0
    errors_count: int = 0
    last_error: str | None = None

    # Publisher-specific metrics
    events_published: int = 0
    events_processed: int = 0
    events_failed: int = 0
    events_retried: int = 0

    subscriptions_active: int = 0
    handlers_registered: int = 0

    processing_time_total: float = 0.0
    processing_time_avg: float = 0.0

    queue_size: int = 0
    dead_letter_queue_size: int = 0

    def record_event_published(self) -> None:
        """Record an event publication."""
        self.events_published += 1

    def record_event_processed(self, processing_time: float) -> None:
        """Record successful event processing."""
        self.events_processed += 1
        self.processing_time_total += processing_time
        if self.events_processed > 0:
            self.processing_time_avg = (
                self.processing_time_total / self.events_processed
            )

    def record_event_failed(self) -> None:
        """Record failed event processing."""
        self.events_failed += 1

    def record_event_retried(self) -> None:
        """Record event retry."""
        self.events_retried += 1


class EventPublisher(EventPublisherBase):
    """High-performance event publisher using queue adapter backend."""

    def __init__(self, settings: EventPublisherSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or EventPublisherSettings()
        self._metrics = PublisherMetrics()

        # Queue adapter integration
        Queue = import_adapter("queue")
        self._queue = depends.get(Queue)

        # Event routing
        self._subscriptions: list[EventSubscription] = []

        # Processing control
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._processing_semaphore = asyncio.Semaphore(
            self._settings.max_concurrent_events,
        )
        self._shutdown_event = asyncio.Event()

        # Subscription management
        self._subscription_lock = asyncio.Lock()
        self._subscription_tasks: dict[UUID, list[asyncio.Task[None]]] = defaultdict(
            list
        )

        # Event routing maps for performance
        self._type_subscriptions: dict[str, list[EventSubscription]] = defaultdict(list)
        self._wildcard_subscriptions: list[EventSubscription] = []

        self._logger = logging.getLogger(__name__)

    @property
    def metrics(self) -> PublisherMetrics:
        """Get publisher metrics."""
        self._metrics.subscriptions_active = len(
            [s for s in self._subscriptions if s.active],
        )
        self._metrics.handlers_registered = len(self._subscriptions)
        # Queue metrics are managed by the queue adapter
        self._metrics.queue_size = 0  # Would need queue adapter API for this
        self._metrics.dead_letter_queue_size = (
            0  # Would need queue adapter API for this
        )
        return self._metrics

    async def _initialize(self) -> None:
        """Initialize the event publisher (ServiceBase requirement)."""
        # Connect to queue backend
        await self._queue.connect()

        # Start worker tasks
        num_workers = min(self._settings.max_concurrent_events, 10)
        for i in range(num_workers):
            task = asyncio.create_task(self._event_worker(f"worker-{i}"))
            self._worker_tasks.append(task)

        if self._settings.log_events:
            self._logger.info("Event publisher started with %d workers", num_workers)

    async def _shutdown(self) -> None:
        """Shutdown the event publisher (ServiceBase requirement)."""
        self._shutdown_event.set()

        # Cancel all worker tasks
        for task in self._worker_tasks:
            if not task.done():
                task.cancel()

        # Cancel subscription tasks
        for task_list in self._subscription_tasks.values():
            for task in task_list:
                if not task.done():
                    task.cancel()

        # Wait for tasks to complete
        try:
            if self._worker_tasks:
                await asyncio.gather(*self._worker_tasks, return_exceptions=True)

            for task_list in self._subscription_tasks.values():
                if task_list:
                    await asyncio.gather(*task_list, return_exceptions=True)
        except Exception:
            pass  # Ignore cancellation exceptions

        self._worker_tasks.clear()
        self._subscription_tasks.clear()

        # Disconnect from queue backend
        await self._queue.disconnect()

        if self._settings.log_events:
            self._logger.info("Event publisher stopped")

    async def start(self) -> None:
        """Start the event publisher (public API)."""
        await self.initialize()

    async def stop(self) -> None:
        """Stop the event publisher (public API)."""
        await self.shutdown()

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: Event to publish
        """
        if self._shutdown_event.is_set():
            msg = "Publisher is shutting down"
            raise RuntimeError(msg)

        # Apply default settings if not specified
        if not event.metadata.timeout:
            event.metadata.timeout = self._settings.default_timeout

        if event.metadata.max_retries == 3:  # Default value
            event.metadata.max_retries = self._settings.default_max_retries

        if event.metadata.retry_delay == 1.0:  # Default value
            event.metadata.retry_delay = self._settings.default_retry_delay

        # Serialize event and publish via queue adapter
        import msgpack
        from acb.adapters.queue import MessagePriority

        # Map event priority to queue priority
        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "critical": MessagePriority.CRITICAL,
        }
        # Handle both EventPriority enum and string (after serialization)
        priority_value = (
            event.metadata.priority.value
            if hasattr(event.metadata.priority, "value")
            else event.metadata.priority
        )
        queue_priority = priority_map.get(priority_value, MessagePriority.NORMAL)

        # Create topic from event type
        topic = f"{self._settings.event_topic_prefix}.{event.metadata.event_type}"

        # Serialize event payload (convert UUIDs to strings for msgpack)
        event_dict = event.model_dump(mode="json")
        payload = msgpack.packb(event_dict)

        # Publish to queue
        await self._queue.publish(
            topic=topic,
            payload=payload,
            priority=queue_priority,
            headers=event.metadata.headers,
            correlation_id=str(event.metadata.event_id),
        )

        self._metrics.record_event_published()

        if self._settings.log_events:
            self._logger.debug(
                "Published event: %s (type=%s, priority=%s)",
                event.metadata.event_id,
                event.metadata.event_type,
                event.metadata.priority.value,
            )

    async def subscribe(self, subscription: EventSubscription) -> None:
        """Add an event subscription.

        Args:
            subscription: Subscription configuration
        """
        async with self._subscription_lock:
            self._subscriptions.append(subscription)

            # Update routing maps for performance
            if subscription.event_type:
                self._type_subscriptions[subscription.event_type].append(subscription)
            else:
                self._wildcard_subscriptions.append(subscription)

        if self._settings.log_events:
            self._logger.debug(
                "Added subscription: %s (event_type=%s, handler=%s)",
                subscription.subscription_id,
                subscription.event_type,
                subscription.handler.handler_name,
            )

    async def unsubscribe(self, subscription_id: UUID) -> bool:
        """Remove an event subscription.

        Args:
            subscription_id: ID of subscription to remove

        Returns:
            True if subscription was found and removed
        """
        async with self._subscription_lock:
            # Find and remove subscription
            for i, sub in enumerate(self._subscriptions):
                if sub.subscription_id == subscription_id:
                    removed_sub = self._subscriptions.pop(i)

                    # Update routing maps
                    if removed_sub.event_type:
                        type_subs = self._type_subscriptions[removed_sub.event_type]
                        if removed_sub in type_subs:
                            type_subs.remove(removed_sub)
                    elif removed_sub in self._wildcard_subscriptions:
                        self._wildcard_subscriptions.remove(removed_sub)

                    # Cancel any active tasks for this subscription
                    tasks = self._subscription_tasks.get(subscription_id, [])
                    for task in tasks:
                        if not task.done():
                            task.cancel()

                    if subscription_id in self._subscription_tasks:
                        del self._subscription_tasks[subscription_id]

                    if self._settings.log_events:
                        self._logger.debug("Removed subscription: %s", subscription_id)

                    return True

        return False

    async def publish_and_wait(
        self,
        event: Event,
        timeout: float | None = None,
    ) -> list[EventHandlerResult]:
        """Publish an event and wait for all handlers to complete.

        Args:
            event: Event to publish
            timeout: Maximum time to wait for completion

        Returns:
            List of handler results
        """
        # Find matching subscriptions
        matching_subs = await self._find_matching_subscriptions(event)

        if not matching_subs:
            return []

        # Process handlers directly
        tasks = []
        for subscription in matching_subs:
            task = asyncio.create_task(
                self._process_event_with_handler(event, subscription),
            )
            tasks.append(task)

        # Wait for all handlers to complete
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout or self._settings.default_timeout,
            )

            # Convert exceptions to failed results
            processed_results = []
            for result in results:
                if isinstance(result, Exception):
                    processed_results.append(
                        EventHandlerResult(
                            success=False,
                            error_message=str(result),
                        ),
                    )
                else:
                    processed_results.append(result)

            return processed_results

        except TimeoutError:
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()

            raise

    async def _event_worker(self, worker_name: str) -> None:
        """Worker task for processing events from the queue."""
        import msgpack

        # Subscribe to all event topics
        topic_pattern = f"{self._settings.event_topic_prefix}.*"

        while not self._shutdown_event.is_set():
            try:
                # Subscribe to event messages via queue adapter
                async with self._queue.subscribe(topic_pattern) as messages:
                    async for queue_message in messages:
                        if self._shutdown_event.is_set():
                            break

                        try:
                            # Deserialize event
                            event_data = msgpack.unpackb(queue_message.payload)
                            event = Event.model_validate(event_data)

                            # Process the event
                            await self._process_event(event)

                            # Acknowledge message
                            await self._queue.acknowledge(queue_message)

                        except Exception as e:
                            self._logger.exception(
                                "Worker %s failed to process message: %s",
                                worker_name,
                                e,
                            )
                            # Reject message (will go to DLQ if configured)
                            await self._queue.reject(queue_message, requeue=False)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception("Worker %s error: %s", worker_name, e)
                await asyncio.sleep(1.0)  # Back off on errors

    async def _process_event(self, event: Event) -> None:
        """Process a single event with all matching handlers."""
        if event.is_expired():
            event.mark_failed("Event expired")
            await self._handle_failed_event(event)
            return

        # Find matching subscriptions
        matching_subs = await self._find_matching_subscriptions(event)

        if not matching_subs:
            if self._settings.log_events:
                self._logger.debug(
                    "No handlers for event: %s",
                    event.metadata.event_type,
                )
            return

        # Process with each matching subscription
        event.mark_processing()
        processing_start = asyncio.get_event_loop().time()

        tasks = []
        for subscription in matching_subs:
            # Check concurrency limits
            active_tasks = self._subscription_tasks[subscription.subscription_id]
            if len(active_tasks) >= subscription.max_concurrent:
                continue  # Skip if at concurrency limit

            task = asyncio.create_task(
                self._process_event_with_handler(event, subscription),
            )
            tasks.append(task)
            active_tasks.append(task)

        if not tasks:
            return

        # Wait for all handlers to complete
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            success_count = 0
            for result in results:
                if isinstance(result, Exception):
                    self._logger.error(
                        "Handler error for event %s: %s",
                        event.metadata.event_id,
                        result,
                    )
                elif isinstance(result, EventHandlerResult) and result.success:
                    success_count += 1

            # Mark event as completed if any handler succeeded
            if success_count > 0:
                event.mark_completed()
                processing_time = asyncio.get_event_loop().time() - processing_start
                self._metrics.record_event_processed(processing_time)
            else:
                event.mark_failed("All handlers failed")
                await self._handle_failed_event(event)

        except Exception as e:
            event.mark_failed(f"Processing error: {e}")
            await self._handle_failed_event(event)
            self._logger.exception("Event processing error: %s", e)

        finally:
            # Clean up completed tasks
            for subscription in matching_subs:
                active_tasks = self._subscription_tasks[subscription.subscription_id]
                completed_tasks = [t for t in active_tasks if t.done()]
                for task in completed_tasks:
                    active_tasks.remove(task)

    async def _process_event_with_handler(
        self,
        event: Event,
        subscription: EventSubscription,
    ) -> EventHandlerResult:
        """Process an event with a specific handler."""
        async with self._processing_semaphore:
            try:
                # Apply subscription timeout if specified
                timeout = self._settings.subscription_timeout
                return await asyncio.wait_for(
                    subscription.handler.handle(event),
                    timeout=timeout,
                )

            except TimeoutError:
                return EventHandlerResult(
                    success=False,
                    error_message=f"Handler timeout after {timeout}s",
                )
            except Exception as e:
                return await subscription.handler.handle_error(event, e)

    async def _find_matching_subscriptions(
        self,
        event: Event,
    ) -> list[EventSubscription]:
        """Find all subscriptions that match the given event."""
        matching = []

        # Check type-specific subscriptions
        type_subs = self._type_subscriptions.get(event.metadata.event_type, [])
        for sub in type_subs:
            if sub.matches(event):
                matching.append(sub)

        # Check wildcard subscriptions
        for sub in self._wildcard_subscriptions:
            if sub.matches(event):
                matching.append(sub)

        return matching

    async def _handle_failed_event(self, event: Event) -> None:
        """Handle a failed event (retry or dead letter)."""
        import msgpack
        from acb.adapters.queue import MessagePriority

        self._metrics.record_event_failed()

        if event.can_retry():
            # Calculate retry delay with exponential backoff
            delay = event.metadata.retry_delay
            if self._settings.exponential_backoff:
                delay *= 2**event.retry_count
                delay = min(delay, self._settings.max_retry_delay)

            event.mark_retrying()
            self._metrics.record_event_retried()

            # Re-publish with delay for retry
            topic = f"{self._settings.event_topic_prefix}.{event.metadata.event_type}"
            payload = msgpack.packb(event.model_dump(mode="json"))

            await self._queue.enqueue(
                topic=topic,
                payload=payload,
                priority=MessagePriority.NORMAL,
                delay_seconds=delay,
            )

            if self._settings.log_events:
                self._logger.debug(
                    "Retrying event %s (attempt %d/%d) after %0.2fs",
                    event.metadata.event_id,
                    event.retry_count,
                    event.metadata.max_retries,
                    delay,
                )
        else:
            # Failed events that can't retry will go to dead letter queue via queue adapter
            if self._settings.log_events:
                self._logger.warning(
                    "Event %s exhausted retries (will go to DLQ): %s",
                    event.metadata.event_id,
                    event.error_message,
                )
            # The queue adapter will handle DLQ when message is rejected

    # Context manager support (delegating to ServiceBase)
    async def __aenter__(self) -> "EventPublisher":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        await self.shutdown()


# Factory function for creating event publishers
def create_event_publisher(
    **settings_kwargs: t.Any,
) -> EventPublisher:
    """Create an event publisher with specified settings.

    The queue backend is determined by settings/adapters.yml configuration.

    Args:
        **settings_kwargs: Additional settings

    Returns:
        Configured EventPublisher instance
    """
    settings = EventPublisherSettings(**settings_kwargs)
    return EventPublisher(settings)


# Convenience functions
@asynccontextmanager
async def event_publisher_context(
    settings: EventPublisherSettings | None = None,
) -> AsyncGenerator[EventPublisher]:
    """Context manager for event publisher lifecycle.

    Args:
        settings: Publisher settings

    Yields:
        Started EventPublisher instance
    """
    publisher = EventPublisher(settings)
    try:
        await publisher.initialize()
        yield publisher
    finally:
        await publisher.shutdown()
