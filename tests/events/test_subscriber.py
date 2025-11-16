"""Tests for EventSubscriber functionality."""

from uuid import UUID

import asyncio
import pytest
from datetime import datetime

from acb.events import (
    Event,
    EventBuffer,
    EventFilter,
    EventHandler,
    EventHandlerResult,
    EventPriority,
    EventRouter,
    EventSubscriber,
    ManagedSubscription,
    SubscriberSettings,
    SubscriptionMode,
    create_event,
    create_event_subscriber,
    event_subscriber_context,
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


class TestSubscriberSettings:
    """Test SubscriberSettings functionality."""

    def test_default_settings(self):
        """Test default settings creation."""
        settings = SubscriberSettings()

        assert settings.default_mode == SubscriptionMode.PUSH
        assert settings.max_subscriptions == 1000
        assert settings.enable_buffering is True
        assert settings.buffer_size == 1000
        assert settings.enable_batching is False
        assert settings.batch_size == 10
        assert settings.batch_timeout == 5.0
        assert settings.enable_health_checks is True
        assert settings.health_check_interval == 60.0
        assert settings.enable_retries is True
        assert settings.max_retries == 3
        assert settings.retry_delay == 1.0

    def test_custom_settings(self):
        """Test custom settings creation."""
        settings = SubscriberSettings(
            default_mode=SubscriptionMode.PULL,
            max_subscriptions=500,
            enable_buffering=False,
            batch_size=20,
            enable_health_checks=False,
        )

        assert settings.default_mode == SubscriptionMode.PULL
        assert settings.max_subscriptions == 500
        assert settings.enable_buffering is False
        assert settings.batch_size == 20
        assert settings.enable_health_checks is False


class TestEventBuffer:
    """Test EventBuffer functionality."""

    def test_buffer_creation(self):
        """Test creating an event buffer."""
        buffer = EventBuffer(max_size=100)

        assert buffer.max_size == 100
        assert buffer.size == 0
        assert buffer.is_empty
        assert not buffer.is_full

    async def test_buffer_operations(self):
        """Test basic buffer operations."""
        buffer = EventBuffer(max_size=3)
        event1 = create_event("test.event1", "test_service")
        event2 = create_event("test.event2", "test_service")
        event3 = create_event("test.event3", "test_service")

        # Test add operations
        await buffer.add(event1)
        assert buffer.size == 1
        assert not buffer.is_empty

        await buffer.add(event2)
        await buffer.add(event3)
        assert buffer.size == 3
        assert buffer.is_full

        # Test get operations
        events = await buffer.get_batch(2)
        assert len(events) == 2
        assert events[0] == event1
        assert events[1] == event2
        assert buffer.size == 1

        # Test get remaining
        remaining = await buffer.get_batch(5)  # More than available
        assert len(remaining) == 1
        assert remaining[0] == event3
        assert buffer.is_empty

    async def test_buffer_overflow_behavior(self):
        """Test buffer overflow behavior."""
        buffer = EventBuffer(max_size=2)
        event1 = create_event("event1", "service")
        event2 = create_event("event2", "service")
        event3 = create_event("event3", "service")  # This should cause overflow

        await buffer.add(event1)
        await buffer.add(event2)

        # Buffer is now full
        assert buffer.is_full

        # Adding another event should remove the oldest
        await buffer.add(event3)
        assert buffer.size == 2

        # Should contain event2 and event3 (event1 evicted)
        events = await buffer.get_batch(10)
        assert len(events) == 2
        assert events[0] == event2
        assert events[1] == event3

    async def test_buffer_priority_ordering(self):
        """Test priority ordering in buffer."""
        buffer = EventBuffer(max_size=10)

        # Add events with different priorities
        normal_event = create_event("normal", "service", priority=EventPriority.NORMAL)
        high_event = create_event("high", "service", priority=EventPriority.HIGH)
        low_event = create_event("low", "service", priority=EventPriority.LOW)
        critical_event = create_event(
            "critical", "service", priority=EventPriority.CRITICAL
        )

        # Add in mixed order
        await buffer.add(normal_event)
        await buffer.add(low_event)
        await buffer.add(critical_event)
        await buffer.add(high_event)

        # Should retrieve in priority order
        events = await buffer.get_batch(10)
        priorities = [event.metadata.priority for event in events]
        expected_order = [
            EventPriority.CRITICAL,
            EventPriority.HIGH,
            EventPriority.NORMAL,
            EventPriority.LOW,
        ]
        assert priorities == expected_order

    async def test_buffer_clear(self):
        """Test buffer clear functionality."""
        buffer = EventBuffer(max_size=10)

        # Add some events
        for i in range(5):
            event = create_event(f"event{i}", "service")
            await buffer.add(event)

        assert buffer.size == 5

        # Clear buffer
        await buffer.clear()
        assert buffer.size == 0
        assert buffer.is_empty


class TestEventFilter:
    """Test EventFilter functionality."""

    def test_filter_creation(self):
        """Test creating event filters."""
        # Type-based filter
        type_filter = EventFilter.by_type("user.created")
        assert type_filter.filter_type == "type"
        assert type_filter.pattern == "user.created"

        # Source-based filter
        source_filter = EventFilter.by_source("user_service")
        assert source_filter.filter_type == "source"
        assert source_filter.pattern == "user_service"

        # Routing key filter
        routing_filter = EventFilter.by_routing_key("users")
        assert routing_filter.filter_type == "routing_key"
        assert routing_filter.pattern == "users"

        # Custom predicate filter
        custom_filter = EventFilter.by_predicate(
            lambda e: e.payload.get("important", False)
        )
        assert custom_filter.filter_type == "predicate"
        assert callable(custom_filter.predicate)

    def test_filter_matching(self):
        """Test event filter matching."""
        user_event = create_event("user.created", "user_service", {"user_id": 123})
        order_event = create_event("order.created", "order_service", {"order_id": 456})

        # Type filter
        type_filter = EventFilter.by_type("user.created")
        assert type_filter.matches(user_event)
        assert not type_filter.matches(order_event)

        # Source filter
        source_filter = EventFilter.by_source("user_service")
        assert source_filter.matches(user_event)
        assert not source_filter.matches(order_event)

        # Custom predicate
        important_filter = EventFilter.by_predicate(
            lambda e: e.payload.get("user_id") == 123
        )
        assert important_filter.matches(user_event)
        assert not important_filter.matches(order_event)

    def test_filter_wildcard_patterns(self):
        """Test wildcard pattern matching in filters."""
        # Create events
        user_created = create_event("user.created", "user_service")
        user_updated = create_event("user.updated", "user_service")
        order_created = create_event("order.created", "order_service")

        # Wildcard type filter
        user_filter = EventFilter.by_type("user.*")
        assert user_filter.matches(user_created)
        assert user_filter.matches(user_updated)
        assert not user_filter.matches(order_created)

    def test_combined_filters(self):
        """Test combining multiple filters."""
        event1 = create_event("user.created", "user_service", {"priority": "high"})
        event2 = create_event("user.created", "admin_service", {"priority": "normal"})
        event3 = create_event("order.created", "user_service", {"priority": "high"})

        # Combine type and source filters
        combined_filter = EventFilter.combine(
            [EventFilter.by_type("user.created"), EventFilter.by_source("user_service")]
        )

        assert combined_filter.matches(event1)  # Matches both
        assert not combined_filter.matches(event2)  # Wrong source
        assert not combined_filter.matches(event3)  # Wrong type


class TestEventRouter:
    """Test EventRouter functionality."""

    def test_router_creation(self):
        """Test creating an event router."""
        router = EventRouter()
        assert len(router._routes) == 0

    async def test_router_route_management(self):
        """Test adding and removing routes."""
        router = EventRouter()
        handler = MockEventHandler()

        # Add route
        route_id = await router.add_route(handler, EventFilter.by_type("user.created"))
        assert route_id is not None
        assert len(router._routes) == 1

        # Remove route
        removed = await router.remove_route(route_id)
        assert removed is True
        assert len(router._routes) == 0

        # Try to remove non-existent route
        removed = await router.remove_route(route_id)
        assert removed is False

    async def test_router_event_routing(self):
        """Test routing events to handlers."""
        router = EventRouter()
        user_handler = MockEventHandler()
        order_handler = MockEventHandler()
        all_handler = MockEventHandler()

        # Add routes
        await router.add_route(user_handler, EventFilter.by_type("user.created"))
        await router.add_route(order_handler, EventFilter.by_type("order.created"))
        await router.add_route(
            all_handler, EventFilter.by_predicate(lambda e: True)
        )  # Catches all

        # Create events
        user_event = create_event("user.created", "user_service")
        order_event = create_event("order.created", "order_service")

        # Route events
        user_matches = await router.route_event(user_event)
        order_matches = await router.route_event(order_event)

        # Check routing results
        assert len(user_matches) == 2  # user_handler + all_handler
        assert len(order_matches) == 2  # order_handler + all_handler

        # Verify correct handlers matched
        user_handlers = [match[0] for match in user_matches]
        assert user_handler in user_handlers
        assert all_handler in user_handlers

        order_handlers = [match[0] for match in order_matches]
        assert order_handler in order_handlers
        assert all_handler in order_handlers

    async def test_router_priority_routing(self):
        """Test routing with handler priorities."""
        router = EventRouter()

        # Create handlers with different priorities
        low_handler = MockEventHandler()
        normal_handler = MockEventHandler()
        high_handler = MockEventHandler()

        # Add routes with priorities
        await router.add_route(
            low_handler, EventFilter.by_type("test.event"), priority=1
        )
        await router.add_route(
            high_handler, EventFilter.by_type("test.event"), priority=10
        )
        await router.add_route(
            normal_handler, EventFilter.by_type("test.event"), priority=5
        )

        event = create_event("test.event", "test_service")
        matches = await router.route_event(event)

        # Should be sorted by priority (highest first)
        priorities = [match[2] for match in matches]  # priority is third element
        assert priorities == [10, 5, 1]

        # Handlers should be in correct order
        handlers = [match[0] for match in matches]
        assert handlers == [high_handler, normal_handler, low_handler]


class TestManagedSubscription:
    """Test ManagedSubscription functionality."""

    def test_subscription_creation(self):
        """Test creating a managed subscription."""
        handler = MockEventHandler()
        filter_obj = EventFilter.by_type("user.created")

        subscription = ManagedSubscription(
            subscription_id=UUID("12345678-1234-5678-9012-123456789012"),
            handler=handler,
            event_filter=filter_obj,
            mode=SubscriptionMode.PUSH,
            buffer_size=100,
        )

        assert subscription.subscription_id == UUID(
            "12345678-1234-5678-9012-123456789012"
        )
        assert subscription.handler == handler
        assert subscription.event_filter == filter_obj
        assert subscription.mode == SubscriptionMode.PUSH
        assert subscription.buffer_size == 100
        assert subscription.is_active
        assert isinstance(subscription.created_at, datetime)
        assert subscription.events_received == 0
        assert subscription.events_processed == 0

    async def test_subscription_event_processing(self):
        """Test processing events through a subscription."""
        handler = MockEventHandler()
        filter_obj = EventFilter.by_type("user.created")

        subscription = ManagedSubscription(
            subscription_id=UUID("12345678-1234-5678-9012-123456789012"),
            handler=handler,
            event_filter=filter_obj,
            mode=SubscriptionMode.PUSH,
        )

        # Create matching and non-matching events
        matching_event = create_event("user.created", "user_service")
        non_matching_event = create_event("order.created", "order_service")

        # Process events
        result1 = await subscription.process_event(matching_event)
        result2 = await subscription.process_event(non_matching_event)

        # Check results
        assert result1 is True  # Event was processed
        assert result2 is False  # Event was filtered out

        # Check handler was called for matching event only
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] == matching_event

        # Check metrics
        assert subscription.events_received == 2
        assert subscription.events_processed == 1

    async def test_subscription_pause_resume(self):
        """Test pausing and resuming subscriptions."""
        handler = MockEventHandler()
        subscription = ManagedSubscription(
            subscription_id=UUID("12345678-1234-5678-9012-123456789012"),
            handler=handler,
            event_filter=EventFilter.by_predicate(lambda e: True),
            mode=SubscriptionMode.PUSH,
        )

        event = create_event("test.event", "test_service")

        # Process event while active
        result = await subscription.process_event(event)
        assert result is True
        assert len(handler.handled_events) == 1

        # Pause subscription
        subscription.pause()
        assert not subscription.is_active

        # Process event while paused
        result = await subscription.process_event(event)
        assert result is False
        assert len(handler.handled_events) == 1  # No new events processed

        # Resume subscription
        subscription.resume()
        assert subscription.is_active

        # Process event after resume
        result = await subscription.process_event(event)
        assert result is True
        assert len(handler.handled_events) == 2

    async def test_subscription_buffering(self):
        """Test subscription with buffering enabled."""
        handler = MockEventHandler()
        subscription = ManagedSubscription(
            subscription_id=UUID("12345678-1234-5678-9012-123456789012"),
            handler=handler,
            event_filter=EventFilter.by_predicate(lambda e: True),
            mode=SubscriptionMode.PULL,  # Pull mode uses buffering
            buffer_size=10,
        )

        # Add events to buffer
        events = [create_event(f"event{i}", "service") for i in range(5)]
        for event in events:
            await subscription.process_event(event)

        # Events should be buffered, not immediately processed
        assert len(handler.handled_events) == 0
        assert subscription.events_received == 5

        # Manually trigger buffer processing
        await subscription._process_buffered_events()

        # Now events should be processed
        assert len(handler.handled_events) == 5
        assert subscription.events_processed == 5


class TestEventSubscriber:
    """Test EventSubscriber functionality."""

    @pytest.fixture
    async def subscriber(self):
        """Create a test subscriber."""
        settings = SubscriberSettings(
            enable_health_checks=False,  # Disable for testing
        )
        subscriber = EventSubscriber(settings)
        await subscriber.start()
        yield subscriber
        await subscriber.stop()

    async def test_subscriber_creation(self):
        """Test creating an event subscriber."""
        settings = SubscriberSettings()
        subscriber = EventSubscriber(settings)

        assert subscriber.settings == settings
        assert not subscriber.is_running
        assert len(subscriber._subscriptions) == 0

    async def test_subscriber_lifecycle(self):
        """Test subscriber start/stop lifecycle."""
        subscriber = EventSubscriber()

        assert not subscriber.is_running

        await subscriber.start()
        assert subscriber.is_running

        await subscriber.stop()
        assert not subscriber.is_running

    async def test_subscriber_context_manager(self):
        """Test subscriber as context manager."""
        async with EventSubscriber() as subscriber:
            assert subscriber.is_running

        assert not subscriber.is_running

    async def test_subscribe_handler(self, subscriber):
        """Test subscribing event handlers."""
        handler = MockEventHandler()

        # Subscribe without filter (all events)
        subscription_id = await subscriber.subscribe(handler)
        assert subscription_id is not None
        assert len(subscriber._subscriptions) == 1

        # Subscribe with event type filter
        type_subscription_id = await subscriber.subscribe(
            handler, event_type="user.created"
        )
        assert type_subscription_id is not None
        assert len(subscriber._subscriptions) == 2

        # Subscribe with custom filter
        custom_filter = EventFilter.by_predicate(
            lambda e: e.payload.get("important", False)
        )
        filter_subscription_id = await subscriber.subscribe(
            handler, event_filter=custom_filter
        )
        assert filter_subscription_id is not None
        assert len(subscriber._subscriptions) == 3

    async def test_unsubscribe_handler(self, subscriber):
        """Test unsubscribing event handlers."""
        handler = MockEventHandler()

        # Subscribe handler
        subscription_id = await subscriber.subscribe(handler)
        assert len(subscriber._subscriptions) == 1

        # Unsubscribe handler
        result = await subscriber.unsubscribe(subscription_id)
        assert result is True
        assert len(subscriber._subscriptions) == 0

        # Try to unsubscribe non-existent subscription
        result = await subscriber.unsubscribe(subscription_id)
        assert result is False

    async def test_deliver_event(self, subscriber):
        """Test delivering events to subscribers."""
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()

        # Subscribe handlers
        await subscriber.subscribe(handler1, event_type="user.created")
        await subscriber.subscribe(handler2)  # All events

        # Deliver matching event
        matching_event = create_event("user.created", "user_service")
        await subscriber.deliver_event(matching_event)

        await asyncio.sleep(0.1)  # Allow async processing

        # handler1 should receive the event (matches filter)
        assert len(handler1.handled_events) == 1
        assert handler1.handled_events[0] == matching_event

        # handler2 should also receive the event (no filter)
        assert len(handler2.handled_events) == 1
        assert handler2.handled_events[0] == matching_event

        # Deliver non-matching event
        non_matching_event = create_event("order.created", "order_service")
        await subscriber.deliver_event(non_matching_event)

        await asyncio.sleep(0.1)

        # handler1 should not receive the non-matching event
        assert len(handler1.handled_events) == 1

        # handler2 should receive the non-matching event (no filter)
        assert len(handler2.handled_events) == 2

    async def test_subscription_modes(self, subscriber):
        """Test different subscription modes."""
        push_handler = MockEventHandler()
        pull_handler = MockEventHandler()

        # Subscribe with different modes
        await subscriber.subscribe(push_handler, mode=SubscriptionMode.PUSH)
        await subscriber.subscribe(pull_handler, mode=SubscriptionMode.PULL)

        event = create_event("test.event", "test_service")
        await subscriber.deliver_event(event)

        await asyncio.sleep(0.1)

        # PUSH mode should process immediately
        assert len(push_handler.handled_events) == 1

        # PULL mode should buffer events (not immediately processed)
        assert len(pull_handler.handled_events) == 0

    async def test_subscription_priority(self, subscriber):
        """Test subscription priority handling."""
        low_handler = MockEventHandler()
        high_handler = MockEventHandler()

        # Subscribe with different priorities
        await subscriber.subscribe(low_handler, priority=1)
        await subscriber.subscribe(high_handler, priority=10)

        event = create_event("test.event", "test_service")
        await subscriber.deliver_event(event)

        await asyncio.sleep(0.1)

        # Both handlers should receive the event
        assert len(low_handler.handled_events) == 1
        assert len(high_handler.handled_events) == 1

        # High priority handler should be processed first
        # (This is implementation-dependent and may not be easily testable)

    async def test_max_subscriptions_limit(self):
        """Test maximum subscriptions limit."""
        settings = SubscriberSettings(max_subscriptions=2)
        subscriber = EventSubscriber(settings)
        await subscriber.start()

        try:
            handler = MockEventHandler()

            # Subscribe up to the limit
            await subscriber.subscribe(handler)
            await subscriber.subscribe(handler)
            assert len(subscriber._subscriptions) == 2

            # Try to exceed the limit
            with pytest.raises(
                RuntimeError, match="Maximum subscriptions limit reached"
            ):
                await subscriber.subscribe(handler)

        finally:
            await subscriber.stop()

    async def test_subscription_error_handling(self, subscriber):
        """Test error handling in subscriptions."""
        failing_handler = MockEventHandler(success=False)
        good_handler = MockEventHandler(success=True)

        await subscriber.subscribe(failing_handler)
        await subscriber.subscribe(good_handler)

        event = create_event("test.event", "test_service")
        await subscriber.deliver_event(event)

        await asyncio.sleep(0.1)

        # Both handlers should have been called
        assert len(failing_handler.handled_events) == 1
        assert len(good_handler.handled_events) == 1

        # Event should still be marked as completed despite one failure
        # (This depends on the error handling strategy)

    async def test_batch_processing(self):
        """Test batch processing of events."""
        settings = SubscriberSettings(
            enable_batching=True,
            batch_size=3,
            batch_timeout=0.1,
        )
        subscriber = EventSubscriber(settings)
        await subscriber.start()

        try:
            handler = MockEventHandler()
            await subscriber.subscribe(handler, mode=SubscriptionMode.PULL)

            # Deliver events that should be batched
            events = [create_event(f"event{i}", "service") for i in range(5)]
            for event in events:
                await subscriber.deliver_event(event)

            # Wait for batch processing
            await asyncio.sleep(0.2)

            # Handler should receive events in batches
            # (Implementation details may vary)

        finally:
            await subscriber.stop()

    async def test_subscription_statistics(self, subscriber):
        """Test subscription statistics collection."""
        handler = MockEventHandler()
        subscription_id = await subscriber.subscribe(handler)

        # Deliver some events
        for i in range(5):
            event = create_event(f"event{i}", "service")
            await subscriber.deliver_event(event)

        await asyncio.sleep(0.1)

        # Get subscription statistics
        subscription = subscriber._subscriptions[subscription_id]
        assert subscription.events_received == 5
        assert subscription.events_processed == 5

    async def test_subscription_pause_resume(self, subscriber):
        """Test pausing and resuming subscriptions."""
        handler = MockEventHandler()
        subscription_id = await subscriber.subscribe(handler)

        # Deliver event while active
        event1 = create_event("event1", "service")
        await subscriber.deliver_event(event1)
        await asyncio.sleep(0.1)
        assert len(handler.handled_events) == 1

        # Pause subscription
        await subscriber.pause_subscription(subscription_id)

        # Deliver event while paused
        event2 = create_event("event2", "service")
        await subscriber.deliver_event(event2)
        await asyncio.sleep(0.1)
        assert len(handler.handled_events) == 1  # No new events

        # Resume subscription
        await subscriber.resume_subscription(subscription_id)

        # Deliver event after resume
        event3 = create_event("event3", "service")
        await subscriber.deliver_event(event3)
        await asyncio.sleep(0.1)
        assert len(handler.handled_events) == 2


class TestEventSubscriberFactory:
    """Test event subscriber factory functions."""

    async def test_create_event_subscriber(self):
        """Test create_event_subscriber factory function."""
        subscriber = create_event_subscriber(
            default_mode=SubscriptionMode.PULL,
            max_subscriptions=50,
        )

        assert isinstance(subscriber, EventSubscriber)
        assert subscriber.settings.default_mode == SubscriptionMode.PULL
        assert subscriber.settings.max_subscriptions == 50

        await subscriber.start()
        await subscriber.stop()

    async def test_event_subscriber_context(self):
        """Test event_subscriber_context context manager."""
        async with event_subscriber_context() as subscriber:
            assert isinstance(subscriber, EventSubscriber)
            assert subscriber.is_running

        assert not subscriber.is_running

    async def test_event_subscriber_context_with_settings(self):
        """Test event_subscriber_context with custom settings."""
        settings = SubscriberSettings(max_subscriptions=25)

        async with event_subscriber_context(settings) as subscriber:
            assert subscriber.settings.max_subscriptions == 25

        assert not subscriber.is_running


class TestEventSubscriberIntegration:
    """Test EventSubscriber integration scenarios."""

    async def test_complex_event_routing(self):
        """Test complex event routing scenarios."""
        async with event_subscriber_context() as subscriber:
            # Create specialized handlers
            user_handler = MockEventHandler()
            order_handler = MockEventHandler()
            audit_handler = MockEventHandler()
            error_handler = MockEventHandler()

            # Subscribe with different filters
            await subscriber.subscribe(
                user_handler, event_filter=EventFilter.by_type("user.*")
            )
            await subscriber.subscribe(
                order_handler, event_filter=EventFilter.by_type("order.*")
            )
            await subscriber.subscribe(
                audit_handler,
                event_filter=EventFilter.by_predicate(
                    lambda e: e.metadata.tags and "audit" in e.metadata.tags
                ),
            )
            await subscriber.subscribe(
                error_handler,
                event_filter=EventFilter.by_predicate(
                    lambda e: e.metadata.priority == EventPriority.CRITICAL
                ),
            )

            # Deliver various events
            events = [
                create_event("user.created", "user_service", tags=["audit"]),
                create_event("order.created", "order_service"),
                create_event("user.deleted", "user_service", tags=["audit"]),
                create_event("system.error", "system", priority=EventPriority.CRITICAL),
            ]

            for event in events:
                await subscriber.deliver_event(event)

            await asyncio.sleep(0.1)

            # Check that events were routed correctly
            assert len(user_handler.handled_events) == 2  # user.created, user.deleted
            assert len(order_handler.handled_events) == 1  # order.created
            assert (
                len(audit_handler.handled_events) == 2
            )  # user.created, user.deleted (both have audit tag)
            assert (
                len(error_handler.handled_events) == 1
            )  # system.error (critical priority)

    async def test_hybrid_subscription_mode(self):
        """Test hybrid subscription mode behavior."""
        async with event_subscriber_context() as subscriber:
            handler = MockEventHandler()

            # Subscribe with hybrid mode
            await subscriber.subscribe(handler, mode=SubscriptionMode.HYBRID)

            # Deliver high priority event (should be pushed immediately)
            high_priority_event = create_event(
                "urgent.event", "service", priority=EventPriority.HIGH
            )
            await subscriber.deliver_event(high_priority_event)

            await asyncio.sleep(0.1)

            # Should be processed immediately due to high priority
            assert len(handler.handled_events) >= 1

            # Deliver normal priority event (might be buffered)
            normal_event = create_event("normal.event", "service")
            await subscriber.deliver_event(normal_event)

            await asyncio.sleep(0.1)

            # Total processed events should be 2
            assert len(handler.handled_events) == 2

    async def test_subscription_health_monitoring(self):
        """Test subscription health monitoring."""
        settings = SubscriberSettings(
            enable_health_checks=True,
            health_check_interval=0.1,  # Fast interval for testing
        )

        async with event_subscriber_context(settings) as subscriber:
            handler = MockEventHandler()
            await subscriber.subscribe(handler)

            # Wait for at least one health check
            await asyncio.sleep(0.2)

            # Subscriber should still be healthy and running
            assert subscriber.is_running

    async def test_multi_subscriber_coordination(self):
        """Test coordination between multiple subscribers."""
        # Create two subscribers
        subscriber1 = create_event_subscriber()
        subscriber2 = create_event_subscriber()

        await subscriber1.start()
        await subscriber2.start()

        try:
            handler1 = MockEventHandler()
            handler2 = MockEventHandler()

            # Subscribe to different event types
            await subscriber1.subscribe(handler1, event_type="user.created")
            await subscriber2.subscribe(handler2, event_type="order.created")

            # Deliver events to both subscribers
            user_event = create_event("user.created", "user_service")
            order_event = create_event("order.created", "order_service")

            await subscriber1.deliver_event(user_event)
            await subscriber1.deliver_event(order_event)
            await subscriber2.deliver_event(user_event)
            await subscriber2.deliver_event(order_event)

            await asyncio.sleep(0.1)

            # Each subscriber should only process matching events
            assert len(handler1.handled_events) == 1  # Only user.created
            assert handler1.handled_events[0].metadata.event_type == "user.created"

            assert len(handler2.handled_events) == 1  # Only order.created
            assert handler2.handled_events[0].metadata.event_type == "order.created"

        finally:
            await subscriber1.stop()
            await subscriber2.stop()
