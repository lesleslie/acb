"""Tests for EventPublisher functionality."""

import asyncio
import pytest
from datetime import datetime
from uuid import UUID
from unittest.mock import AsyncMock, Mock, patch

from acb.events import (
    Event,
    EventPublisher,
    EventPublisherSettings,
    EventQueue,
    PublisherBackend,
    PublisherMetrics,
    create_event,
    create_event_publisher,
    event_publisher_context,
    EventHandler,
    EventHandlerResult,
    EventStatus,
    EventPriority,
    EventDeliveryMode,
)


class MockEventHandler(EventHandler):
    """Mock event handler for testing."""

    def __init__(self, can_handle_result: bool = True, success: bool = True):
        super().__init__()
        self._can_handle_result = can_handle_result
        self._success = success
        self.handled_events = []
        self.handle_call_count = 0

    def can_handle(self, event: Event) -> bool:
        return self._can_handle_result

    async def handle(self, event: Event) -> EventHandlerResult:
        self.handled_events.append(event)
        self.handle_call_count += 1

        if not self._success:
            return EventHandlerResult(
                success=False,
                error_message="Mock handler error"
            )

        return EventHandlerResult(success=True)


class TestEventPublisherSettings:
    """Test EventPublisher settings."""

    def test_default_settings(self):
        """Test default settings creation."""
        settings = EventPublisherSettings()

        assert settings.backend == PublisherBackend.MEMORY
        assert settings.max_concurrent_events == 100
        assert settings.enable_health_checks is True
        assert settings.health_check_interval == 60.0
        assert settings.enable_retries is True
        assert settings.default_max_retries == 3
        assert settings.default_retry_delay == 1.0
        assert settings.enable_dead_letter_queue is True
        assert settings.dead_letter_queue_size == 1000

    def test_custom_settings(self):
        """Test custom settings creation."""
        settings = EventPublisherSettings(
            backend=PublisherBackend.REDIS,
            max_concurrent_events=50,
            enable_health_checks=False,
            default_max_retries=5,
            default_retry_delay=2.0,
        )

        assert settings.backend == PublisherBackend.REDIS
        assert settings.max_concurrent_events == 50
        assert settings.enable_health_checks is False
        assert settings.default_max_retries == 5
        assert settings.default_retry_delay == 2.0


class TestEventQueue:
    """Test EventQueue functionality."""

    def test_event_queue_creation(self):
        """Test creating an event queue."""
        queue = EventQueue(max_size=100)

        assert queue.max_size == 100
        assert queue.size == 0
        assert queue.is_empty
        assert not queue.is_full

    async def test_event_queue_operations(self):
        """Test basic queue operations."""
        queue = EventQueue(max_size=2)
        event1 = create_event("test.event1", "test_service")
        event2 = create_event("test.event2", "test_service")

        # Test put operations
        await queue.put(event1)
        assert queue.size == 1
        assert not queue.is_empty

        await queue.put(event2)
        assert queue.size == 2
        assert queue.is_full

        # Test get operations
        retrieved_event1 = await queue.get()
        assert retrieved_event1 == event1
        assert queue.size == 1

        retrieved_event2 = await queue.get()
        assert retrieved_event2 == event2
        assert queue.size == 0
        assert queue.is_empty

    async def test_event_queue_priority_ordering(self):
        """Test priority ordering in queue."""
        queue = EventQueue(max_size=10)

        # Add events with different priorities
        normal_event = create_event("normal.event", "test_service")
        high_event = create_event("high.event", "test_service", priority=EventPriority.HIGH)
        low_event = create_event("low.event", "test_service", priority=EventPriority.LOW)
        critical_event = create_event("critical.event", "test_service", priority=EventPriority.CRITICAL)

        # Add in mixed order
        await queue.put(normal_event)
        await queue.put(low_event)
        await queue.put(critical_event)
        await queue.put(high_event)

        # Should retrieve in priority order: CRITICAL, HIGH, NORMAL, LOW
        assert (await queue.get()) == critical_event
        assert (await queue.get()) == high_event
        assert (await queue.get()) == normal_event
        assert (await queue.get()) == low_event

    async def test_event_queue_timeout(self):
        """Test queue timeout operations."""
        queue = EventQueue(max_size=1)

        # Test get timeout on empty queue
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

        # Fill queue to capacity
        event = create_event("test.event", "test_service")
        await queue.put(event)

        # Test put timeout on full queue
        another_event = create_event("another.event", "test_service")
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.put(another_event), timeout=0.1)


class TestPublisherMetrics:
    """Test PublisherMetrics functionality."""

    def test_metrics_creation(self):
        """Test metrics creation and initial values."""
        metrics = PublisherMetrics()

        assert metrics.events_published == 0
        assert metrics.events_failed == 0
        assert metrics.events_retried == 0
        assert metrics.handlers_executed == 0
        assert metrics.handlers_failed == 0
        assert isinstance(metrics.start_time, datetime)
        assert metrics.get_success_rate() == 0.0
        assert metrics.get_failure_rate() == 0.0

    def test_metrics_operations(self):
        """Test metrics operations."""
        metrics = PublisherMetrics()

        # Test recording events
        metrics.record_event_published()
        metrics.record_event_published()
        metrics.record_event_failed()

        assert metrics.events_published == 2
        assert metrics.events_failed == 1
        assert metrics.get_success_rate() == 66.67  # 2 out of 3
        assert metrics.get_failure_rate() == 33.33  # 1 out of 3

        # Test recording handlers
        metrics.record_handler_executed()
        metrics.record_handler_failed()

        assert metrics.handlers_executed == 1
        assert metrics.handlers_failed == 1

        # Test retry recording
        metrics.record_event_retried()
        assert metrics.events_retried == 1

    def test_metrics_uptime(self):
        """Test metrics uptime calculation."""
        metrics = PublisherMetrics()

        # Small delay to ensure uptime > 0
        import time
        time.sleep(0.01)

        uptime = metrics.get_uptime()
        assert uptime > 0.0

    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        metrics = PublisherMetrics()

        # Record some metrics
        metrics.record_event_published()
        metrics.record_event_failed()
        metrics.record_handler_executed()

        # Reset metrics
        metrics.reset()

        assert metrics.events_published == 0
        assert metrics.events_failed == 0
        assert metrics.handlers_executed == 0


class TestEventPublisher:
    """Test EventPublisher functionality."""

    @pytest.fixture
    async def publisher(self):
        """Create a test publisher."""
        settings = EventPublisherSettings(
            enable_health_checks=False,  # Disable for testing
        )
        publisher = EventPublisher(settings)
        await publisher.start()
        yield publisher
        await publisher.stop()

    @pytest.fixture
    async def mock_handler(self):
        """Create a mock event handler."""
        return MockEventHandler()

    async def test_publisher_creation(self):
        """Test creating an event publisher."""
        settings = EventPublisherSettings()
        publisher = EventPublisher(settings)

        assert publisher.settings == settings
        assert not publisher.is_running
        assert isinstance(publisher.metrics, PublisherMetrics)

    async def test_publisher_lifecycle(self):
        """Test publisher start/stop lifecycle."""
        publisher = EventPublisher()

        assert not publisher.is_running

        await publisher.start()
        assert publisher.is_running

        await publisher.stop()
        assert not publisher.is_running

    async def test_publisher_context_manager(self):
        """Test publisher as context manager."""
        async with EventPublisher() as publisher:
            assert publisher.is_running

        assert not publisher.is_running

    async def test_publish_event_basic(self, publisher, mock_handler):
        """Test basic event publishing."""
        event = create_event("test.event", "test_service", {"key": "value"})

        # Subscribe handler
        subscription_id = await publisher.subscribe(mock_handler)
        assert subscription_id is not None

        # Publish event
        await publisher.publish(event)

        # Give some time for async processing
        await asyncio.sleep(0.1)

        # Verify handler was called
        assert len(mock_handler.handled_events) == 1
        assert mock_handler.handled_events[0] == event
        assert event.status == EventStatus.COMPLETED

        # Verify metrics
        assert publisher.metrics.events_published == 1
        assert publisher.metrics.handlers_executed == 1

    async def test_publish_event_no_subscribers(self, publisher):
        """Test publishing event with no subscribers."""
        event = create_event("test.event", "test_service")

        await publisher.publish(event)

        # Event should still be marked as completed
        assert event.status == EventStatus.COMPLETED
        assert publisher.metrics.events_published == 1

    async def test_subscribe_unsubscribe(self, publisher, mock_handler):
        """Test subscribing and unsubscribing handlers."""
        # Subscribe handler
        subscription_id = await publisher.subscribe(mock_handler)
        assert subscription_id is not None

        # Verify subscription exists
        assert len(publisher._subscriptions) == 1

        # Unsubscribe handler
        result = await publisher.unsubscribe(subscription_id)
        assert result is True

        # Verify subscription removed
        assert len(publisher._subscriptions) == 0

        # Try to unsubscribe non-existent subscription
        result = await publisher.unsubscribe(subscription_id)
        assert result is False

    async def test_event_filtering(self, publisher):
        """Test event filtering by type."""
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()

        # Subscribe handler1 to specific event type
        await publisher.subscribe(handler1, event_type="user.created")

        # Subscribe handler2 to all events
        await publisher.subscribe(handler2)

        # Publish matching event
        matching_event = create_event("user.created", "user_service")
        await publisher.publish(matching_event)

        # Publish non-matching event
        non_matching_event = create_event("order.created", "order_service")
        await publisher.publish(non_matching_event)

        await asyncio.sleep(0.1)

        # handler1 should only receive the matching event
        assert len(handler1.handled_events) == 1
        assert handler1.handled_events[0] == matching_event

        # handler2 should receive both events
        assert len(handler2.handled_events) == 2

    async def test_handler_error_handling(self, publisher):
        """Test error handling in event handlers."""
        failing_handler = MockEventHandler(success=False)
        good_handler = MockEventHandler(success=True)

        await publisher.subscribe(failing_handler)
        await publisher.subscribe(good_handler)

        event = create_event("test.event", "test_service")
        await publisher.publish(event)

        await asyncio.sleep(0.1)

        # Both handlers should have been called
        assert len(failing_handler.handled_events) == 1
        assert len(good_handler.handled_events) == 1

        # Metrics should reflect the failure
        assert publisher.metrics.handlers_executed == 2
        assert publisher.metrics.handlers_failed == 1

    async def test_event_retry_logic(self, publisher):
        """Test event retry logic."""
        # Create event with retry configuration
        event = create_event(
            "test.event",
            "test_service",
            max_retries=2,
            retry_delay=0.01,  # Fast retry for testing
        )

        # Handler that fails initially
        failing_handler = MockEventHandler(success=False)
        await publisher.subscribe(failing_handler)

        await publisher.publish(event)
        await asyncio.sleep(0.2)  # Wait for retries

        # Handler should have been called multiple times due to retries
        assert failing_handler.handle_call_count > 1
        assert publisher.metrics.events_retried > 0

    async def test_concurrent_event_publishing(self, publisher, mock_handler):
        """Test concurrent event publishing."""
        await publisher.subscribe(mock_handler)

        # Publish multiple events concurrently
        events = [
            create_event(f"test.event.{i}", "test_service")
            for i in range(10)
        ]

        tasks = [publisher.publish(event) for event in events]
        await asyncio.gather(*tasks)

        await asyncio.sleep(0.2)

        # All events should have been handled
        assert len(mock_handler.handled_events) == 10
        assert publisher.metrics.events_published == 10
        assert publisher.metrics.handlers_executed == 10

    async def test_max_concurrent_events_limit(self):
        """Test max concurrent events limitation."""
        settings = EventPublisherSettings(max_concurrent_events=2)
        publisher = EventPublisher(settings)
        await publisher.start()

        try:
            # Create slow handler to block processing
            slow_handler = MockEventHandler()

            # Mock the handle method to be slow
            original_handle = slow_handler.handle
            async def slow_handle(event):
                await asyncio.sleep(0.5)  # Slow processing
                return await original_handle(event)

            slow_handler.handle = slow_handle
            await publisher.subscribe(slow_handler)

            # Publish more events than the limit
            events = [
                create_event(f"test.event.{i}", "test_service")
                for i in range(5)
            ]

            # Start publishing tasks
            tasks = [asyncio.create_task(publisher.publish(event)) for event in events]

            # Give some time for processing to start
            await asyncio.sleep(0.1)

            # Some events should be queued due to concurrency limit
            assert len(publisher._event_queue._queue) > 0

            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        finally:
            await publisher.stop()

    async def test_health_checks(self):
        """Test publisher health checking."""
        settings = EventPublisherSettings(
            enable_health_checks=True,
            health_check_interval=0.1,  # Fast interval for testing
        )
        publisher = EventPublisher(settings)

        await publisher.start()

        # Wait for at least one health check
        await asyncio.sleep(0.2)

        # Publisher should still be healthy
        assert publisher.is_running

        await publisher.stop()

    async def test_publisher_metrics_collection(self, publisher, mock_handler):
        """Test comprehensive metrics collection."""
        await publisher.subscribe(mock_handler)

        # Publish some events
        for i in range(5):
            event = create_event(f"test.event.{i}", "test_service")
            await publisher.publish(event)

        await asyncio.sleep(0.1)

        metrics = publisher.metrics
        assert metrics.events_published == 5
        assert metrics.handlers_executed == 5
        assert metrics.get_success_rate() == 100.0
        assert metrics.get_uptime() > 0

    async def test_event_priority_processing(self, publisher, mock_handler):
        """Test that high priority events are processed first."""
        await publisher.subscribe(mock_handler)

        # Create events with different priorities
        low_event = create_event("low.event", "test_service", priority=EventPriority.LOW)
        normal_event = create_event("normal.event", "test_service", priority=EventPriority.NORMAL)
        high_event = create_event("high.event", "test_service", priority=EventPriority.HIGH)
        critical_event = create_event("critical.event", "test_service", priority=EventPriority.CRITICAL)

        # Publish in mixed order
        await publisher.publish(normal_event)
        await publisher.publish(low_event)
        await publisher.publish(critical_event)
        await publisher.publish(high_event)

        await asyncio.sleep(0.1)

        # Events should be processed in priority order
        handled_events = mock_handler.handled_events
        assert len(handled_events) == 4

        # Check that higher priority events were processed first
        priorities = [event.metadata.priority for event in handled_events]
        expected_order = [EventPriority.CRITICAL, EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW]
        assert priorities == expected_order


class TestEventPublisherFactory:
    """Test event publisher factory functions."""

    async def test_create_event_publisher(self):
        """Test create_event_publisher factory function."""
        publisher = create_event_publisher(
            backend=PublisherBackend.REDIS,
            max_concurrent_events=50,
        )

        assert isinstance(publisher, EventPublisher)
        assert publisher.settings.backend == PublisherBackend.REDIS
        assert publisher.settings.max_concurrent_events == 50

        await publisher.start()
        await publisher.stop()

    async def test_event_publisher_context(self):
        """Test event_publisher_context context manager."""
        async with event_publisher_context() as publisher:
            assert isinstance(publisher, EventPublisher)
            assert publisher.is_running

        assert not publisher.is_running

    async def test_event_publisher_context_with_settings(self):
        """Test event_publisher_context with custom settings."""
        settings = EventPublisherSettings(max_concurrent_events=25)

        async with event_publisher_context(settings) as publisher:
            assert publisher.settings.max_concurrent_events == 25

        assert not publisher.is_running


class TestEventPublisherIntegration:
    """Test EventPublisher integration scenarios."""

    async def test_multiple_event_types(self):
        """Test handling multiple event types."""
        async with event_publisher_context() as publisher:
            user_handler = MockEventHandler()
            order_handler = MockEventHandler()

            # Subscribe handlers to specific event types
            await publisher.subscribe(user_handler, event_type="user.created")
            await publisher.subscribe(order_handler, event_type="order.created")

            # Publish different event types
            user_event = create_event("user.created", "user_service", {"user_id": 123})
            order_event = create_event("order.created", "order_service", {"order_id": 456})
            other_event = create_event("other.event", "other_service")

            await publisher.publish(user_event)
            await publisher.publish(order_event)
            await publisher.publish(other_event)

            await asyncio.sleep(0.1)

            # Check that handlers only received their specific events
            assert len(user_handler.handled_events) == 1
            assert user_handler.handled_events[0].metadata.event_type == "user.created"

            assert len(order_handler.handled_events) == 1
            assert order_handler.handled_events[0].metadata.event_type == "order.created"

    async def test_delivery_modes(self):
        """Test different delivery modes."""
        async with event_publisher_context() as publisher:
            handler = MockEventHandler()
            await publisher.subscribe(handler)

            # Test fire-and-forget (default)
            fire_forget_event = create_event(
                "test.event",
                "test_service",
                delivery_mode=EventDeliveryMode.FIRE_AND_FORGET
            )
            await publisher.publish(fire_forget_event)

            # Test at-least-once
            at_least_once_event = create_event(
                "test.event",
                "test_service",
                delivery_mode=EventDeliveryMode.AT_LEAST_ONCE
            )
            await publisher.publish(at_least_once_event)

            await asyncio.sleep(0.1)

            # Both events should be handled
            assert len(handler.handled_events) == 2

    async def test_event_correlation(self):
        """Test event correlation with correlation IDs."""
        async with event_publisher_context() as publisher:
            handler = MockEventHandler()
            await publisher.subscribe(handler)

            correlation_id = "corr-123"

            # Publish related events with same correlation ID
            event1 = create_event(
                "step1.completed",
                "workflow_service",
                correlation_id=correlation_id
            )
            event2 = create_event(
                "step2.completed",
                "workflow_service",
                correlation_id=correlation_id
            )

            await publisher.publish(event1)
            await publisher.publish(event2)

            await asyncio.sleep(0.1)

            # Check that events have same correlation ID
            handled_events = handler.handled_events
            assert len(handled_events) == 2
            assert all(
                event.metadata.correlation_id == correlation_id
                for event in handled_events
            )

    async def test_event_routing_keys(self):
        """Test event routing with routing keys."""
        async with event_publisher_context() as publisher:
            user_handler = MockEventHandler()
            admin_handler = MockEventHandler()

            # Subscribe with predicate functions for routing
            def is_user_event(event: Event) -> bool:
                return event.metadata.routing_key == "users"

            def is_admin_event(event: Event) -> bool:
                return event.metadata.routing_key == "admin"

            from acb.events import FunctionalEventHandler

            user_functional_handler = FunctionalEventHandler(
                lambda e: EventHandlerResult(success=True),
                predicate=is_user_event
            )
            admin_functional_handler = FunctionalEventHandler(
                lambda e: EventHandlerResult(success=True),
                predicate=is_admin_event
            )

            await publisher.subscribe(user_functional_handler)
            await publisher.subscribe(admin_functional_handler)

            # Publish events with different routing keys
            user_event = create_event(
                "action.performed",
                "app_service",
                routing_key="users"
            )
            admin_event = create_event(
                "action.performed",
                "app_service",
                routing_key="admin"
            )

            await publisher.publish(user_event)
            await publisher.publish(admin_event)

            await asyncio.sleep(0.1)

            # Check metrics show events were routed correctly
            assert publisher.metrics.events_published == 2
            assert publisher.metrics.handlers_executed == 2