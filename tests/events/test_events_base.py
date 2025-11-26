"""Tests for base event classes and functionality."""

from uuid import UUID

import asyncio
from datetime import datetime

from acb.events import (
    Event,
    EventDeliveryMode,
    EventHandler,
    EventHandlerResult,
    EventMetadata,
    EventPriority,
    EventStatus,
    FunctionalEventHandler,
    TypedEventHandler,
    create_event,
    event_handler,
)


class TestEventMetadata:
    """Test event metadata functionality."""

    def test_event_metadata_creation(self):
        """Test creating event metadata."""
        metadata = EventMetadata(
            event_type="test.event",
            source="test_service",
        )

        assert metadata.event_type == "test.event"
        assert metadata.source == "test_service"
        assert isinstance(metadata.event_id, UUID)
        assert isinstance(metadata.timestamp, datetime)
        assert metadata.priority == EventPriority.NORMAL.value
        assert metadata.delivery_mode == EventDeliveryMode.FIRE_AND_FORGET.value

    def test_event_metadata_with_custom_fields(self):
        """Test event metadata with custom fields."""
        metadata = EventMetadata(
            event_type="user.created",
            source="user_service",
            priority=EventPriority.HIGH,
            delivery_mode=EventDeliveryMode.AT_LEAST_ONCE,
            routing_key="users",
            correlation_id="corr-123",
            max_retries=5,
            retry_delay=2.0,
            timeout=30.0,
            headers={"version": "1.0"},
            tags=["user", "create"],
        )

        assert metadata.event_type == "user.created"
        assert metadata.source == "user_service"
        assert metadata.priority == EventPriority.HIGH.value
        assert metadata.delivery_mode == EventDeliveryMode.AT_LEAST_ONCE.value
        assert metadata.routing_key == "users"
        assert metadata.correlation_id == "corr-123"
        assert metadata.max_retries == 5
        assert metadata.retry_delay == 2.0
        assert metadata.timeout == 30.0
        assert metadata.headers == {"version": "1.0"}
        assert metadata.tags == ["user", "create"]


class TestEvent:
    """Test event functionality."""

    def test_event_creation(self):
        """Test creating an event."""
        event = create_event(
            event_type="test.event",
            source="test_service",
            payload={"key": "value"},
        )

        assert event.metadata.event_type == "test.event"
        assert event.metadata.source == "test_service"
        assert event.payload == {"key": "value"}
        assert event.status == EventStatus.PENDING
        assert event.retry_count == 0
        assert event.error_message is None

    def test_event_status_management(self):
        """Test event status transitions."""
        event = create_event("test.event", "test_service")

        # Test processing status
        event.mark_processing()
        assert event.status == EventStatus.PROCESSING

        # Test completed status
        event.mark_completed()
        assert event.status == EventStatus.COMPLETED

        # Test failed status
        event.mark_failed("Test error")
        assert event.status == EventStatus.FAILED
        assert event.error_message == "Test error"

        # Test retry status
        event.mark_retrying()
        assert event.status == EventStatus.RETRYING
        assert event.retry_count == 1

    def test_event_expiration(self):
        """Test event expiration checking."""
        # Event without timeout should not expire
        event = create_event("test.event", "test_service")
        assert not event.is_expired()

        # Event with timeout in future should not expire
        event = create_event(
            "test.event",
            "test_service",
            timeout=60.0,  # 60 seconds
        )
        assert not event.is_expired()

        # Event with timeout in past should expire
        event = create_event(
            "test.event",
            "test_service",
            timeout=0.001,  # 1ms
        )
        import time

        time.sleep(0.002)  # Wait longer than timeout
        assert event.is_expired()

    def test_event_retry_logic(self):
        """Test event retry checking."""
        event = create_event(
            "test.event",
            "test_service",
            max_retries=3,
        )

        # Fresh event should be retryable after failure
        event.mark_failed("Test error")
        assert event.can_retry()

        # Event at max retries should not be retryable
        event.retry_count = 3
        assert not event.can_retry()

        # Completed event should not be retryable
        event.retry_count = 0
        event.mark_completed()
        assert not event.can_retry()

    def test_event_string_representation(self):
        """Test event string representations."""
        event = create_event("test.event", "test_service")

        str_repr = str(event)
        assert "test.event" in str_repr
        assert str(event.metadata.event_id) in str_repr

        repr_str = repr(event)
        assert "test.event" in repr_str
        assert "PENDING" in repr_str


class MockEventHandler(EventHandler):
    """Mock event handler for testing."""

    def __init__(self, can_handle_result: bool = True):
        super().__init__()
        self._can_handle_result = can_handle_result
        self.handled_events = []

    def can_handle(self, event: Event) -> bool:
        return self._can_handle_result

    async def handle(self, event: Event) -> EventHandlerResult:
        self.handled_events.append(event)
        return EventHandlerResult(success=True)


class TestEventHandler:
    """Test event handler functionality."""

    def test_event_handler_creation(self):
        """Test creating an event handler."""
        handler = MockEventHandler()

        assert handler.handler_name == "MockEventHandler"
        assert isinstance(handler.handler_id, str)
        assert len(handler.handled_events) == 0

    async def test_event_handler_basic_handling(self):
        """Test basic event handling."""
        handler = MockEventHandler()
        event = create_event("test.event", "test_service")

        assert handler.can_handle(event)

        result = await handler.handle(event)
        assert result.success
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] == event

    async def test_event_handler_error_handling(self):
        """Test event handler error handling."""
        handler = MockEventHandler()
        event = create_event("test.event", "test_service")
        error = Exception("Test error")

        result = await handler.handle_error(event, error)
        assert not result.success
        assert result.error_message == "Test error"

    def test_event_handler_string_representation(self):
        """Test event handler string representations."""
        handler = MockEventHandler()

        str_repr = str(handler)
        assert "MockEventHandler" in str_repr
        assert handler.handler_id in str_repr

        repr_str = repr(handler)
        assert "MockEventHandler" in repr_str
        assert handler.handler_id in repr_str


class TestTypedEventHandler:
    """Test typed event handler functionality."""

    def test_typed_event_handler_creation(self):
        """Test creating a typed event handler."""
        handler = TypedEventHandler("user.created")

        assert handler.event_type == "user.created"
        assert handler.handler_name == "TypedEventHandler"

    def test_typed_event_handler_matching(self):
        """Test typed event handler matching."""
        handler = TypedEventHandler("user.created")

        # Should match correct event type
        matching_event = create_event("user.created", "user_service")
        assert handler.can_handle(matching_event)

        # Should not match different event type
        non_matching_event = create_event("user.deleted", "user_service")
        assert not handler.can_handle(non_matching_event)


class TestFunctionalEventHandler:
    """Test functional event handler functionality."""

    async def test_functional_handler_sync_function(self):
        """Test functional handler with synchronous function."""

        def sync_handler(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True, metadata={"handled": True})

        handler = FunctionalEventHandler(sync_handler)
        event = create_event("test.event", "test_service")

        result = await handler.handle(event)
        assert result.success
        assert result.metadata["handled"]

    async def test_functional_handler_async_function(self):
        """Test functional handler with asynchronous function."""

        async def async_handler(event: Event) -> EventHandlerResult:
            await asyncio.sleep(0.01)  # Simulate async work
            return EventHandlerResult(success=True, metadata={"async_handled": True})

        handler = FunctionalEventHandler(async_handler)
        event = create_event("test.event", "test_service")

        result = await handler.handle(event)
        assert result.success
        assert result.metadata["async_handled"]

    async def test_functional_handler_with_event_type(self):
        """Test functional handler with event type filtering."""

        def handler_func(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True)

        handler = FunctionalEventHandler(handler_func, event_type="user.created")

        # Should handle matching event type
        matching_event = create_event("user.created", "user_service")
        assert handler.can_handle(matching_event)

        # Should not handle different event type
        non_matching_event = create_event("user.deleted", "user_service")
        assert not handler.can_handle(non_matching_event)

    async def test_functional_handler_with_predicate(self):
        """Test functional handler with custom predicate."""

        def handler_func(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True)

        def predicate(event: Event) -> bool:
            return event.payload.get("priority") == "high"

        handler = FunctionalEventHandler(handler_func, predicate=predicate)

        # Should handle event matching predicate
        matching_event = create_event(
            "test.event", "test_service", {"priority": "high"}
        )
        assert handler.can_handle(matching_event)

        # Should not handle event not matching predicate
        non_matching_event = create_event(
            "test.event", "test_service", {"priority": "low"}
        )
        assert not handler.can_handle(non_matching_event)

    async def test_functional_handler_error_handling(self):
        """Test functional handler error handling."""

        def failing_handler(event: Event) -> EventHandlerResult:
            raise ValueError("Handler error")

        handler = FunctionalEventHandler(failing_handler)
        event = create_event("test.event", "test_service")

        result = await handler.handle(event)
        assert not result.success
        assert "Handler error" in result.error_message


class TestEventHandlerDecorator:
    """Test event handler decorator functionality."""

    async def test_event_handler_decorator_basic(self):
        """Test basic event handler decorator usage."""

        @event_handler()
        def handle_any_event(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True, metadata={"decorated": True})

        assert isinstance(handle_any_event, FunctionalEventHandler)

        event = create_event("test.event", "test_service")
        assert handle_any_event.can_handle(event)

        result = await handle_any_event.handle(event)
        assert result.success
        assert result.metadata["decorated"]

    async def test_event_handler_decorator_with_type(self):
        """Test event handler decorator with event type."""

        @event_handler(event_type="user.created")
        def handle_user_created(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True)

        # Should handle matching event type
        matching_event = create_event("user.created", "user_service")
        assert handle_user_created.can_handle(matching_event)

        # Should not handle different event type
        non_matching_event = create_event("user.deleted", "user_service")
        assert not handle_user_created.can_handle(non_matching_event)

    async def test_event_handler_decorator_with_predicate(self):
        """Test event handler decorator with predicate."""

        def is_high_priority(event: Event) -> bool:
            return event.metadata.priority == EventPriority.HIGH

        @event_handler(predicate=is_high_priority)
        def handle_high_priority(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True)

        # Should handle high priority event
        high_priority_event = create_event(
            "test.event", "test_service", priority=EventPriority.HIGH
        )
        assert handle_high_priority.can_handle(high_priority_event)

        # Should not handle normal priority event
        normal_priority_event = create_event("test.event", "test_service")
        assert not handle_high_priority.can_handle(normal_priority_event)


class TestCreateEvent:
    """Test event creation helper function."""

    def test_create_event_basic(self):
        """Test basic event creation."""
        event = create_event("test.event", "test_service")

        assert event.metadata.event_type == "test.event"
        assert event.metadata.source == "test_service"
        assert event.payload == {}
        assert event.status == EventStatus.PENDING

    def test_create_event_with_payload(self):
        """Test event creation with payload."""
        payload = {"user_id": 123, "email": "test@example.com"}
        event = create_event("user.created", "user_service", payload)

        assert event.payload == payload

    def test_create_event_with_metadata_kwargs(self):
        """Test event creation with metadata kwargs."""
        event = create_event(
            "user.created",
            "user_service",
            {"user_id": 123},
            priority=EventPriority.HIGH,
            routing_key="users",
            correlation_id="corr-123",
        )

        assert event.metadata.priority == EventPriority.HIGH
        assert event.metadata.routing_key == "users"
        assert event.metadata.correlation_id == "corr-123"
