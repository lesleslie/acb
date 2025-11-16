"""Tests for EventPublisher functionality."""

import asyncio
import pytest

from acb.events import (
    Event,
    EventDeliveryMode,
    EventHandler,
    EventHandlerResult,
    EventPriority,
    EventPublisher,
    EventPublisherSettings,
    EventStatus,
    EventSubscription,
    PublisherMetrics,
    create_event,
    create_event_publisher,
    event_publisher_context,
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
            return EventHandlerResult(success=False, error_message="Mock handler error")

        return EventHandlerResult(success=True)


class TestEventPublisherSettings:
    """Test EventPublisher settings."""

    def test_default_settings(self):
        """Test default settings creation."""
        settings = EventPublisherSettings()

        assert settings.event_topic_prefix == "events"
        assert settings.max_concurrent_events == 100
        assert settings.health_check_enabled is True
        assert settings.health_check_interval == 60.0
        assert settings.default_max_retries == 3
        assert settings.default_retry_delay == 1.0
        assert settings.dead_letter_queue is True
        assert settings.enable_metrics is True

    def test_custom_settings(self):
        """Test custom settings creation."""
        settings = EventPublisherSettings(
            event_topic_prefix="custom.events",
            max_concurrent_events=50,
            health_check_enabled=False,
            default_max_retries=5,
            default_retry_delay=2.0,
        )

        assert settings.event_topic_prefix == "custom.events"
        assert settings.max_concurrent_events == 50
        assert settings.health_check_enabled is False
        assert settings.default_max_retries == 5
        assert settings.default_retry_delay == 2.0


class TestPublisherMetrics:
    """Test PublisherMetrics functionality."""

    def test_metrics_creation(self):
        """Test metrics creation and initial values."""
        metrics = PublisherMetrics()

        assert metrics.events_published == 0
        assert metrics.events_processed == 0
        assert metrics.events_failed == 0
        assert metrics.events_retried == 0
        assert metrics.subscriptions_active == 0
        assert metrics.handlers_registered == 0
        assert metrics.processing_time_total == 0.0
        assert metrics.processing_time_avg == 0.0

    def test_metrics_operations(self):
        """Test metrics operations."""
        metrics = PublisherMetrics()

        # Test recording events
        metrics.record_event_published()
        metrics.record_event_published()
        metrics.record_event_processed(1.5)
        metrics.record_event_processed(2.5)
        metrics.record_event_failed()
        metrics.record_event_retried()

        assert metrics.events_published == 2
        assert metrics.events_processed == 2
        assert metrics.events_failed == 1
        assert metrics.events_retried == 1
        assert metrics.processing_time_total == 4.0
        assert metrics.processing_time_avg == 2.0


class TestEventPublisher:
    """Test EventPublisher functionality."""

    @pytest.fixture
    async def publisher(self, mock_queue_adapter_import):
        """Create a test publisher."""
        settings = EventPublisherSettings(
            health_check_enabled=False,  # Disable for testing
        )
        publisher = EventPublisher(settings)
        await publisher.start()
        yield publisher
        await publisher.stop()

    @pytest.fixture
    async def mock_handler(self):
        """Create a mock event handler."""
        return MockEventHandler()

    async def test_publisher_creation(self, mock_queue_adapter_import):
        """Test creating an event publisher."""
        from acb.services import ServiceStatus

        settings = EventPublisherSettings()
        publisher = EventPublisher(settings)

        assert publisher._settings == settings
        assert publisher.status == ServiceStatus.INACTIVE
        assert isinstance(publisher.metrics, PublisherMetrics)

    async def test_publisher_lifecycle(self, mock_queue_adapter_import):
        """Test publisher start/stop lifecycle."""
        from acb.services import ServiceStatus

        settings = EventPublisherSettings(health_check_enabled=False)
        publisher = EventPublisher(settings)

        assert publisher.status == ServiceStatus.INACTIVE

        await publisher.start()
        assert publisher.status == ServiceStatus.ACTIVE

        await publisher.stop()
        assert publisher.status == ServiceStatus.STOPPED

    async def test_publisher_context_manager(self, mock_queue_adapter_import):
        """Test publisher as context manager."""
        from acb.services import ServiceStatus

        settings = EventPublisherSettings(health_check_enabled=False)
        async with EventPublisher(settings) as publisher:
            assert publisher.status == ServiceStatus.ACTIVE

        assert publisher.status == ServiceStatus.STOPPED

    async def test_publish_event_basic(self, publisher, mock_handler):
        """Test basic event publishing."""
        event = create_event("test.event", "test_service", {"key": "value"})

        # Subscribe handler
        subscription = EventSubscription(handler=mock_handler, event_type="test.event")
        await publisher.subscribe(subscription)

        # Publish event
        await publisher.publish(event)

        # Give some time for async processing
        await asyncio.sleep(0.1)

        # Verify handler was called
        assert len(mock_handler.handled_events) == 1
        handled_event = mock_handler.handled_events[0]

        # Event goes through serialization, so compare key attributes
        assert handled_event.metadata.event_id == event.metadata.event_id
        assert handled_event.metadata.event_type == event.metadata.event_type
        assert handled_event.metadata.source == event.metadata.source
        assert handled_event.payload == event.payload
        assert handled_event.status == EventStatus.COMPLETED

        # Verify metrics
        assert publisher.metrics.events_published == 1
        assert publisher.metrics.events_processed >= 1

    async def test_publish_event_no_subscribers(self, publisher):
        """Test publishing event with no subscribers."""
        event = create_event("test.event", "test_service")

        await publisher.publish(event)

        # Event is published to queue even without subscribers
        # (original event object status not updated - event goes through serialization)
        assert publisher.metrics.events_published == 1

    async def test_subscribe_unsubscribe(self, publisher, mock_handler):
        """Test subscribing and unsubscribing handlers."""
        # Subscribe handler
        subscription = EventSubscription(handler=mock_handler)
        await publisher.subscribe(subscription)

        # Verify subscription exists
        assert len(publisher._subscriptions) == 1

        # Unsubscribe handler
        result = await publisher.unsubscribe(subscription.subscription_id)
        assert result is True

        # Verify subscription removed
        assert len(publisher._subscriptions) == 0

        # Try to unsubscribe non-existent subscription
        result = await publisher.unsubscribe(subscription.subscription_id)
        assert result is False

    async def test_event_filtering(self, publisher):
        """Test event filtering by type."""
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()

        # Subscribe handler1 to specific event type
        subscription1 = EventSubscription(handler=handler1, event_type="user.created")
        await publisher.subscribe(subscription1)

        # Subscribe handler2 to all events (no event_type filter)
        subscription2 = EventSubscription(handler=handler2)
        await publisher.subscribe(subscription2)

        # Publish matching event
        matching_event = create_event("user.created", "user_service")
        await publisher.publish(matching_event)

        # Publish non-matching event
        non_matching_event = create_event("order.created", "order_service")
        await publisher.publish(non_matching_event)

        await asyncio.sleep(0.1)

        # handler1 should only receive the matching event
        assert len(handler1.handled_events) == 1
        handled_event = handler1.handled_events[0]
        assert handled_event.metadata.event_id == matching_event.metadata.event_id
        assert handled_event.metadata.event_type == matching_event.metadata.event_type
        assert handled_event.status == EventStatus.COMPLETED

        # handler2 should receive both events
        assert len(handler2.handled_events) == 2

    async def test_handler_error_handling(self, publisher):
        """Test error handling in event handlers."""
        failing_handler = MockEventHandler(success=False)
        good_handler = MockEventHandler(success=True)

        subscription1 = EventSubscription(handler=failing_handler)
        subscription2 = EventSubscription(handler=good_handler)
        await publisher.subscribe(subscription1)
        await publisher.subscribe(subscription2)

        event = create_event("test.event", "test_service")
        await publisher.publish(event)

        await asyncio.sleep(0.1)

        # Both handlers should have been called
        assert len(failing_handler.handled_events) == 1
        assert len(good_handler.handled_events) == 1

        # Event is still processed even if individual handlers fail
        assert publisher.metrics.events_published == 1
        assert publisher.metrics.events_processed == 1

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
        subscription = EventSubscription(handler=failing_handler)
        await publisher.subscribe(subscription)

        await publisher.publish(event)
        await asyncio.sleep(0.2)  # Wait for retries

        # Handler should have been called multiple times due to retries
        assert failing_handler.handle_call_count > 1
        assert publisher.metrics.events_retried > 0

    async def test_concurrent_event_publishing(self, publisher, mock_handler):
        """Test concurrent event publishing."""
        subscription = EventSubscription(handler=mock_handler)
        await publisher.subscribe(subscription)

        # Publish multiple events concurrently
        events = [create_event(f"test.event.{i}", "test_service") for i in range(10)]

        tasks = [publisher.publish(event) for event in events]
        await asyncio.gather(*tasks)

        await asyncio.sleep(0.2)

        # All events should have been handled
        assert len(mock_handler.handled_events) == 10
        assert publisher.metrics.events_published == 10
        assert publisher.metrics.events_processed >= 10

    async def test_max_concurrent_events_limit(self, mock_queue_adapter_import):
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
            subscription = EventSubscription(handler=slow_handler)
            await publisher.subscribe(subscription)

            # Publish more events than the limit
            events = [create_event(f"test.event.{i}", "test_service") for i in range(5)]

            # Start publishing tasks
            tasks = [asyncio.create_task(publisher.publish(event)) for event in events]

            # Give some time for processing to start
            await asyncio.sleep(0.1)

            # Note: Queue adapter now handles queuing internally
            # We can't easily assert on queue state, but we can verify all events complete

            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

            # Wait for all events to be processed (slow handler takes 0.5s per event)
            await asyncio.sleep(3.0)  # 5 events * 0.5s + buffer

            # All events should eventually be handled
            assert len(slow_handler.handled_events) == 5

        finally:
            await publisher.stop()

    async def test_health_checks(self, mock_queue_adapter_import):
        """Test publisher health checking."""
        settings = EventPublisherSettings(
            health_check_enabled=True,
            health_check_interval=0.1,  # Fast interval for testing
        )
        publisher = EventPublisher(settings)

        await publisher.start()

        # Wait for at least one health check
        await asyncio.sleep(0.2)

        # Publisher should still be active
        from acb.services import ServiceStatus

        assert publisher.status == ServiceStatus.ACTIVE

        await publisher.stop()

    async def test_publisher_metrics_collection(self, publisher, mock_handler):
        """Test comprehensive metrics collection."""
        subscription = EventSubscription(handler=mock_handler)
        await publisher.subscribe(subscription)

        # Publish some events
        for i in range(5):
            event = create_event(f"test.event.{i}", "test_service")
            await publisher.publish(event)

        await asyncio.sleep(0.1)

        metrics = publisher.metrics
        assert metrics.events_published == 5
        assert metrics.events_processed >= 5

    async def test_event_priority_processing(self, publisher, mock_handler):
        """Test that events with different priorities can be published and processed."""
        subscription = EventSubscription(handler=mock_handler)
        await publisher.subscribe(subscription)

        # Create events with different priorities
        low_event = create_event(
            "low.event", "test_service", priority=EventPriority.LOW
        )
        normal_event = create_event(
            "normal.event", "test_service", priority=EventPriority.NORMAL
        )
        high_event = create_event(
            "high.event", "test_service", priority=EventPriority.HIGH
        )
        critical_event = create_event(
            "critical.event", "test_service", priority=EventPriority.CRITICAL
        )

        # Publish in mixed order
        await publisher.publish(normal_event)
        await publisher.publish(low_event)
        await publisher.publish(critical_event)
        await publisher.publish(high_event)

        await asyncio.sleep(0.1)

        # All events should be processed (priority ordering requires priority queue backend)
        handled_events = mock_handler.handled_events
        assert len(handled_events) == 4

        # Verify all events were received (order depends on queue backend)
        handled_event_ids = {e.metadata.event_id for e in handled_events}
        expected_event_ids = {
            critical_event.metadata.event_id,
            high_event.metadata.event_id,
            normal_event.metadata.event_id,
            low_event.metadata.event_id,
        }
        assert handled_event_ids == expected_event_ids

        # Verify priorities were preserved through serialization
        priorities_handled = {e.metadata.priority for e in handled_events}
        expected_priorities = {"critical", "high", "normal", "low"}
        assert priorities_handled == expected_priorities


class TestEventPublisherFactory:
    """Test event publisher factory functions."""

    async def test_create_event_publisher(self, mock_queue_adapter_import):
        """Test create_event_publisher factory function."""
        publisher = create_event_publisher(
            event_topic_prefix="test.events",
            max_concurrent_events=50,
        )

        assert isinstance(publisher, EventPublisher)
        # Check internal settings (no public accessor)
        assert publisher._settings.event_topic_prefix == "test.events"
        assert publisher._settings.max_concurrent_events == 50

        await publisher.start()
        await publisher.stop()

    async def test_event_publisher_context(self, mock_queue_adapter_import):
        """Test event_publisher_context context manager."""
        from acb.services._base import ServiceStatus

        async with event_publisher_context() as publisher:
            assert isinstance(publisher, EventPublisher)
            # Check service status instead of is_running
            assert publisher.status == ServiceStatus.ACTIVE

        # After context exit, service should be stopped
        assert publisher.status == ServiceStatus.STOPPED

    async def test_event_publisher_context_with_settings(
        self, mock_queue_adapter_import
    ):
        """Test event_publisher_context with custom settings."""
        from acb.services._base import ServiceStatus

        settings = EventPublisherSettings(max_concurrent_events=25)

        async with event_publisher_context(settings) as publisher:
            assert publisher._settings.max_concurrent_events == 25
            assert publisher.status == ServiceStatus.ACTIVE

        assert publisher.status == ServiceStatus.STOPPED


class TestEventPublisherIntegration:
    """Test EventPublisher integration scenarios."""

    async def test_multiple_event_types(self, mock_queue_adapter_import):
        """Test handling multiple event types."""
        async with event_publisher_context() as publisher:
            user_handler = MockEventHandler()
            order_handler = MockEventHandler()

            # Subscribe handlers to specific event types
            user_subscription = EventSubscription(
                handler=user_handler, event_type="user.created"
            )
            order_subscription = EventSubscription(
                handler=order_handler, event_type="order.created"
            )
            await publisher.subscribe(user_subscription)
            await publisher.subscribe(order_subscription)

            # Give workers time to subscribe to queue
            await asyncio.sleep(0.2)

            # Publish different event types
            user_event = create_event("user.created", "user_service", {"user_id": 123})
            order_event = create_event(
                "order.created", "order_service", {"order_id": 456}
            )
            other_event = create_event("other.event", "other_service")

            await publisher.publish(user_event)
            await publisher.publish(order_event)
            await publisher.publish(other_event)

            # Wait for all events to be processed
            await asyncio.sleep(1.0)

            # Check that handlers only received their specific events
            assert len(user_handler.handled_events) == 1
            assert user_handler.handled_events[0].metadata.event_type == "user.created"

            assert len(order_handler.handled_events) == 1
            assert (
                order_handler.handled_events[0].metadata.event_type == "order.created"
            )

    async def test_delivery_modes(self, mock_queue_adapter_import):
        """Test different delivery modes."""
        async with event_publisher_context() as publisher:
            handler = MockEventHandler()
            subscription = EventSubscription(handler=handler)
            await publisher.subscribe(subscription)

            # Give workers time to subscribe to queue
            await asyncio.sleep(0.2)

            # Test fire-and-forget (default)
            fire_forget_event = create_event(
                "test.event",
                "test_service",
                delivery_mode=EventDeliveryMode.FIRE_AND_FORGET,
            )
            await publisher.publish(fire_forget_event)

            # Test at-least-once
            at_least_once_event = create_event(
                "test.event",
                "test_service",
                delivery_mode=EventDeliveryMode.AT_LEAST_ONCE,
            )
            await publisher.publish(at_least_once_event)

            # Wait for all events to be processed
            await asyncio.sleep(1.0)

            # Both events should be handled
            assert len(handler.handled_events) == 2

    async def test_event_correlation(self, mock_queue_adapter_import):
        """Test event correlation with correlation IDs."""
        async with event_publisher_context() as publisher:
            handler = MockEventHandler()
            subscription = EventSubscription(handler=handler)
            await publisher.subscribe(subscription)

            # Give workers time to subscribe to queue
            await asyncio.sleep(0.2)

            correlation_id = "corr-123"

            # Publish related events with same correlation ID
            event1 = create_event(
                "step1.completed", "workflow_service", correlation_id=correlation_id
            )
            event2 = create_event(
                "step2.completed", "workflow_service", correlation_id=correlation_id
            )

            await publisher.publish(event1)
            await publisher.publish(event2)

            # Wait for all events to be processed
            await asyncio.sleep(1.0)

            # Check that events have same correlation ID
            handled_events = handler.handled_events
            assert len(handled_events) == 2
            assert all(
                event.metadata.correlation_id == correlation_id
                for event in handled_events
            )

    async def test_event_routing_keys(self, mock_queue_adapter_import):
        """Test event routing with routing keys."""
        async with event_publisher_context() as publisher:
            MockEventHandler()
            MockEventHandler()

            # Subscribe with predicate functions for routing
            def is_user_event(event: Event) -> bool:
                return event.metadata.routing_key == "users"

            def is_admin_event(event: Event) -> bool:
                return event.metadata.routing_key == "admin"

            from acb.events import FunctionalEventHandler

            user_functional_handler = FunctionalEventHandler(
                lambda e: EventHandlerResult(success=True), predicate=is_user_event
            )
            admin_functional_handler = FunctionalEventHandler(
                lambda e: EventHandlerResult(success=True), predicate=is_admin_event
            )

            user_subscription = EventSubscription(
                handler=user_functional_handler, predicate=is_user_event
            )
            admin_subscription = EventSubscription(
                handler=admin_functional_handler, predicate=is_admin_event
            )
            await publisher.subscribe(user_subscription)
            await publisher.subscribe(admin_subscription)

            # Give workers time to subscribe to queue
            await asyncio.sleep(0.2)

            # Publish events with different routing keys
            user_event = create_event(
                "action.performed", "app_service", routing_key="users"
            )
            admin_event = create_event(
                "action.performed", "app_service", routing_key="admin"
            )

            await publisher.publish(user_event)
            await publisher.publish(admin_event)

            # Wait for all events to be processed
            await asyncio.sleep(1.0)

            # Check metrics show events were routed correctly
            assert publisher.metrics.events_published == 2
            assert publisher.metrics.events_processed == 2
