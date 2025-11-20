"""Integration tests for Events System."""

from unittest.mock import Mock, patch

import asyncio
import pytest

from acb.events import (
    # Core events
    Event,
    EventDeliveryMode,
    EventHandler,
    EventHandlerResult,
    EventPriority,
    # Publisher/Subscriber
    EventsService,
    EventsServiceSettings,
    create_event,
    create_event_publisher,
    create_event_subscriber,
    create_subscription,
    event_handler,
    event_publisher_context,
    event_subscriber_context,
    get_events_service,
    # Discovery
    import_event_handler,
    setup_events_service,
)


class SampleEventHandler(EventHandler):
    """Test event handler for integration tests."""

    def __init__(self, handler_id: str = "test_handler"):
        super().__init__()
        self._handler_id = handler_id
        self.handled_events = []
        self.handle_call_count = 0

    @property
    def handler_name(self) -> str:
        return f"TestEventHandler_{self._handler_id}"

    def can_handle(self, event: Event) -> bool:
        return True

    async def handle(self, event: Event) -> EventHandlerResult:
        self.handled_events.append(event)
        self.handle_call_count += 1
        return EventHandlerResult(
            success=True, metadata={"handler_id": self._handler_id}
        )


class SpecializedEventHandler(EventHandler):
    """Specialized event handler for specific event types."""

    def __init__(self, event_type: str):
        super().__init__()
        self.event_type = event_type
        self.handled_events = []

    def can_handle(self, event: Event) -> bool:
        return event.metadata.event_type == self.event_type

    async def handle(self, event: Event) -> EventHandlerResult:
        self.handled_events.append(event)
        return EventHandlerResult(
            success=True, metadata={"specialized_for": self.event_type}
        )


class TestEndToEndEventFlow:
    """Test complete end-to-end event flow."""

    async def test_basic_pub_sub_flow(self):
        """Test basic publish-subscribe flow."""
        # Create publisher and subscriber
        async with event_publisher_context() as publisher:
            async with event_subscriber_context() as subscriber:
                # Create handler
                handler = SampleEventHandler("basic_flow")

                # Create subscription for publisher
                subscription = create_subscription(handler)
                await publisher.subscribe(subscription)

                # Subscribe handler to subscriber
                await subscriber.subscribe(handler)

                # Create and publish event
                event = create_event(
                    "test.integration", "integration_test", {"test_data": "basic_flow"}
                )

                # Publish via publisher
                await publisher.publish(event)

                # Deliver to subscriber
                await subscriber.deliver_event(event)

                # Allow processing
                await asyncio.sleep(0.1)

                # Verify event was handled by both
                assert len(handler.handled_events) == 2
                assert all(
                    e.metadata.event_type == "test.integration"
                    for e in handler.handled_events
                )
                assert all(
                    e.payload["test_data"] == "basic_flow"
                    for e in handler.handled_events
                )

    async def test_event_filtering_and_routing(self):
        """Test event filtering and routing between handlers."""
        async with event_publisher_context() as publisher:
            # Create specialized handlers
            user_handler = SpecializedEventHandler("user.created")
            order_handler = SpecializedEventHandler("order.created")
            all_handler = SampleEventHandler("catch_all")

            # Subscribe handlers with filters
            user_subscription = create_subscription(
                user_handler, event_type="user.created"
            )
            await publisher.subscribe(user_subscription)

            order_subscription = create_subscription(
                order_handler, event_type="order.created"
            )
            await publisher.subscribe(order_subscription)

            all_subscription = create_subscription(
                all_handler
            )  # No filter - catches all
            await publisher.subscribe(all_subscription)

            # Create different event types
            user_event = create_event("user.created", "user_service", {"user_id": 123})
            order_event = create_event(
                "order.created", "order_service", {"order_id": 456}
            )
            system_event = create_event(
                "system.started", "system_service", {"version": "1.0"}
            )

            # Publish events
            await publisher.publish(user_event)
            await publisher.publish(order_event)
            await publisher.publish(system_event)

            await asyncio.sleep(0.1)

            # Verify correct routing
            assert len(user_handler.handled_events) == 1
            assert user_handler.handled_events[0] == user_event

            assert len(order_handler.handled_events) == 1
            assert order_handler.handled_events[0] == order_event

            assert len(all_handler.handled_events) == 3  # Catches all events

            # Verify metrics
            assert publisher.metrics.events_published == 3
            assert publisher.metrics.handlers_executed == 5  # 1+1+3

    async def test_priority_based_processing(self):
        """Test priority-based event processing."""
        async with event_publisher_context() as publisher:
            handler = SampleEventHandler("priority_test")
            subscription = create_subscription(handler)
            await publisher.subscribe(subscription)

            # Create events with different priorities
            events = [
                create_event(
                    "low.priority", "service", {"order": 4}, priority=EventPriority.LOW
                ),
                create_event(
                    "normal.priority",
                    "service",
                    {"order": 3},
                    priority=EventPriority.NORMAL,
                ),
                create_event(
                    "high.priority",
                    "service",
                    {"order": 2},
                    priority=EventPriority.HIGH,
                ),
                create_event(
                    "critical.priority",
                    "service",
                    {"order": 1},
                    priority=EventPriority.CRITICAL,
                ),
            ]

            # Publish in mixed order
            for event in reversed(events):  # Publish in reverse priority order
                await publisher.publish(event)

            await asyncio.sleep(0.1)

            # Verify events were processed in priority order
            assert len(handler.handled_events) == 4

            processed_orders = [
                event.payload["order"] for event in handler.handled_events
            ]
            assert processed_orders == [
                1,
                2,
                3,
                4,
            ]  # Should be processed in priority order

    async def test_error_handling_and_retries(self):
        """Test error handling and retry mechanisms."""

        class FailingHandler(EventHandler):
            def __init__(self, fail_count: int = 2):
                super().__init__()
                self.fail_count = fail_count
                self.attempt_count = 0
                self.handled_events = []

            def can_handle(self, event: Event) -> bool:
                return True

            async def handle(self, event: Event) -> EventHandlerResult:
                self.attempt_count += 1

                if self.attempt_count <= self.fail_count:
                    return EventHandlerResult(
                        success=False,
                        error_message=f"Attempt {self.attempt_count} failed",
                    )

                self.handled_events.append(event)
                return EventHandlerResult(success=True)

        async with event_publisher_context() as publisher:
            failing_handler = FailingHandler(fail_count=2)
            subscription = create_subscription(failing_handler)
            await publisher.subscribe(subscription)

            # Create event with retry configuration
            event = create_event(
                "test.retry",
                "retry_service",
                {"attempt": "retry_test"},
                max_retries=3,
                retry_delay=0.01,  # Fast retry for testing
            )

            await publisher.publish(event)
            await asyncio.sleep(0.5)  # Wait for retries

            # Verify event was eventually handled after retries
            assert len(failing_handler.handled_events) == 1
            assert (
                failing_handler.attempt_count == 3
            )  # Failed twice, succeeded on third

            # Verify retry metrics
            assert publisher.metrics.events_retried > 0

    async def test_concurrent_event_processing(self):
        """Test concurrent event processing capabilities."""
        async with event_publisher_context() as publisher:
            handler = SampleEventHandler("concurrent_test")
            subscription = create_subscription(handler)
            await publisher.subscribe(subscription)

            # Create multiple events
            events = [
                create_event(
                    f"concurrent.event.{i}", "concurrent_service", {"index": i}
                )
                for i in range(20)
            ]

            # Publish all events concurrently
            publish_tasks = [publisher.publish(event) for event in events]
            await asyncio.gather(*publish_tasks)

            await asyncio.sleep(0.2)

            # Verify all events were handled
            assert len(handler.handled_events) == 20

            # Verify all events were processed
            handled_indices = {
                event.payload["index"] for event in handler.handled_events
            }
            expected_indices = set(range(20))
            assert handled_indices == expected_indices

            # Verify metrics
            assert publisher.metrics.events_published == 20
            assert publisher.metrics.handlers_executed == 20

    async def test_event_correlation_workflow(self):
        """Test event correlation in workflow scenarios."""
        async with event_publisher_context() as publisher:
            workflow_handler = SampleEventHandler("workflow")
            subscription = create_subscription(workflow_handler)
            await publisher.subscribe(subscription)

            correlation_id = "workflow-123"

            # Create related events with same correlation ID
            workflow_events = [
                create_event(
                    "workflow.started",
                    "workflow_service",
                    {"step": "start"},
                    correlation_id=correlation_id,
                ),
                create_event(
                    "workflow.step1.completed",
                    "workflow_service",
                    {"step": "step1"},
                    correlation_id=correlation_id,
                ),
                create_event(
                    "workflow.step2.completed",
                    "workflow_service",
                    {"step": "step2"},
                    correlation_id=correlation_id,
                ),
                create_event(
                    "workflow.completed",
                    "workflow_service",
                    {"step": "end"},
                    correlation_id=correlation_id,
                ),
            ]

            # Publish workflow events
            for event in workflow_events:
                await publisher.publish(event)

            await asyncio.sleep(0.1)

            # Verify all events were handled
            assert len(workflow_handler.handled_events) == 4

            # Verify correlation IDs match
            for event in workflow_handler.handled_events:
                assert event.metadata.correlation_id == correlation_id

            # Verify workflow steps
            steps = [event.payload["step"] for event in workflow_handler.handled_events]
            assert "start" in steps
            assert "step1" in steps
            assert "step2" in steps
            assert "end" in steps

    async def test_delivery_modes(self):
        """Test different event delivery modes."""
        async with event_publisher_context() as publisher:
            handler = SampleEventHandler("delivery_modes")
            subscription = create_subscription(handler)
            await publisher.subscribe(subscription)

            # Test different delivery modes
            fire_forget_event = create_event(
                "delivery.fire_forget",
                "delivery_service",
                {"mode": "fire_and_forget"},
                delivery_mode=EventDeliveryMode.FIRE_AND_FORGET,
            )

            at_least_once_event = create_event(
                "delivery.at_least_once",
                "delivery_service",
                {"mode": "at_least_once"},
                delivery_mode=EventDeliveryMode.AT_LEAST_ONCE,
            )

            exactly_once_event = create_event(
                "delivery.exactly_once",
                "delivery_service",
                {"mode": "exactly_once"},
                delivery_mode=EventDeliveryMode.EXACTLY_ONCE,
            )

            # Publish events with different delivery modes
            await publisher.publish(fire_forget_event)
            await publisher.publish(at_least_once_event)
            await publisher.publish(exactly_once_event)

            await asyncio.sleep(0.1)

            # All events should be handled regardless of delivery mode
            assert len(handler.handled_events) == 3

            # Verify delivery modes
            delivery_modes = [
                event.metadata.delivery_mode for event in handler.handled_events
            ]
            assert EventDeliveryMode.FIRE_AND_FORGET in delivery_modes
            assert EventDeliveryMode.AT_LEAST_ONCE in delivery_modes
            assert EventDeliveryMode.EXACTLY_ONCE in delivery_modes


class TestEventsServiceIntegration:
    """Test Events Service integration with ACB Services Layer."""

    async def test_events_service_lifecycle(self):
        """Test Events Service start/stop lifecycle."""
        settings = EventsServiceSettings(
            enable_publisher=True,
            enable_subscriber=True,
            enable_health_checks=False,  # Disable for testing
        )

        service = EventsService(settings)

        assert not service.is_running
        assert service.publisher is None
        assert service.subscriber is None

        # Start service
        await service.start()

        assert service.is_running
        assert service.publisher is not None
        assert service.subscriber is not None
        assert service.publisher.is_running
        assert service.subscriber.is_running

        # Stop service
        await service.stop()

        assert not service.is_running
        assert service.publisher is None
        assert service.subscriber is None

    async def test_events_service_pub_sub_integration(self):
        """Test Events Service publish/subscribe integration."""
        settings = EventsServiceSettings(
            enable_publisher=True,
            enable_subscriber=True,
            enable_health_checks=False,
        )

        service = EventsService(settings)
        await service.start()

        try:
            # Create handler
            handler = SampleEventHandler("service_integration")

            # Subscribe through service
            subscription_id = await service.subscribe(
                handler, event_type="service.test"
            )
            assert subscription_id is not None

            # Create and publish event through service
            event = create_event(
                "service.test", "events_service", {"integration": "test"}
            )

            await service.publish(event)
            await asyncio.sleep(0.1)

            # Verify event was handled
            assert len(handler.handled_events) == 1
            assert handler.handled_events[0].metadata.event_type == "service.test"

            # Unsubscribe
            result = await service.unsubscribe(subscription_id)
            assert result is True

        finally:
            await service.stop()

    async def test_setup_events_service(self):
        """Test setup_events_service function."""
        settings = EventsServiceSettings(
            enable_publisher=True,
            enable_subscriber=True,
            enable_health_checks=False,
        )

        # Setup service
        service = await setup_events_service(settings)

        try:
            assert isinstance(service, EventsService)
            assert service.is_running

            # Test that global service is set
            global_service = get_events_service()
            assert global_service == service

        finally:
            await service.stop()

    async def test_events_service_error_handling(self):
        """Test Events Service error handling."""
        # Test service with publisher disabled
        settings = EventsServiceSettings(
            enable_publisher=False,
            enable_subscriber=True,
            enable_health_checks=False,
        )

        service = EventsService(settings)
        await service.start()

        try:
            # Trying to publish should raise error
            event = create_event("test.event", "test_service")
            with pytest.raises(RuntimeError, match="Publisher not enabled"):
                await service.publish(event)

        finally:
            await service.stop()

        # Test service with subscriber disabled
        settings = EventsServiceSettings(
            enable_publisher=True,
            enable_subscriber=False,
            enable_health_checks=False,
        )

        service = EventsService(settings)
        await service.start()

        try:
            # Trying to subscribe should raise error
            handler = SampleEventHandler()
            with pytest.raises(RuntimeError, match="Subscriber not enabled"):
                await service.subscribe(handler)

            # Trying to unsubscribe should return False
            result = await service.unsubscribe("fake-id")
            assert result is False

        finally:
            await service.stop()


class SampleEventHandlerDecorators:
    """Test event handler decorators integration."""

    async def test_event_handler_decorator_basic(self):
        """Test basic event handler decorator functionality."""

        @event_handler()
        def handle_any_event(event: Event) -> EventHandlerResult:
            return EventHandlerResult(
                success=True,
                metadata={"decorated": True, "event_type": event.metadata.event_type},
            )

        async with event_publisher_context() as publisher:
            # Subscribe decorated handler
            subscription_id = await publisher.subscribe(handle_any_event)
            assert subscription_id is not None

            # Publish event
            event = create_event(
                "decorator.test", "test_service", {"test": "decorator"}
            )
            await publisher.publish(event)

            await asyncio.sleep(0.1)

            # Verify event was processed
            assert publisher.metrics.handlers_executed == 1

    async def test_event_handler_decorator_with_type(self):
        """Test event handler decorator with event type filtering."""

        @event_handler(event_type="user.created")
        def handle_user_created(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True, metadata={"user_handler": True})

        @event_handler(event_type="order.created")
        def handle_order_created(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True, metadata={"order_handler": True})

        async with event_publisher_context() as publisher:
            # Subscribe decorated handlers
            await publisher.subscribe(handle_user_created)
            await publisher.subscribe(handle_order_created)

            # Publish different event types
            user_event = create_event("user.created", "user_service")
            order_event = create_event("order.created", "order_service")
            other_event = create_event("other.event", "other_service")

            await publisher.publish(user_event)
            await publisher.publish(order_event)
            await publisher.publish(other_event)

            await asyncio.sleep(0.1)

            # Only matching events should be processed
            assert publisher.metrics.handlers_executed == 2  # user + order, not other

    async def test_event_handler_decorator_with_predicate(self):
        """Test event handler decorator with custom predicate."""

        def is_high_priority(event: Event) -> bool:
            return event.metadata.priority == EventPriority.HIGH

        @event_handler(predicate=is_high_priority)
        def handle_high_priority(event: Event) -> EventHandlerResult:
            return EventHandlerResult(success=True, metadata={"high_priority": True})

        async with event_publisher_context() as publisher:
            await publisher.subscribe(handle_high_priority)

            # Publish events with different priorities
            normal_event = create_event(
                "test.normal", "service", priority=EventPriority.NORMAL
            )
            high_event = create_event(
                "test.high", "service", priority=EventPriority.HIGH
            )

            await publisher.publish(normal_event)
            await publisher.publish(high_event)

            await asyncio.sleep(0.1)

            # Only high priority event should be processed
            assert publisher.metrics.handlers_executed == 1

    async def test_event_handler_decorator_async(self):
        """Test event handler decorator with async function."""

        @event_handler()
        async def handle_async_event(event: Event) -> EventHandlerResult:
            await asyncio.sleep(0.01)  # Simulate async work
            return EventHandlerResult(success=True, metadata={"async_handled": True})

        async with event_publisher_context() as publisher:
            await publisher.subscribe(handle_async_event)

            event = create_event("async.test", "test_service")
            await publisher.publish(event)

            await asyncio.sleep(0.1)

            assert publisher.metrics.handlers_executed == 1


class TestDiscoveryIntegration:
    """Test Events discovery system integration."""

    @patch("acb.events.discovery.try_import_event_handler")
    def test_import_event_handler_integration(self, mock_try_import):
        """Test event handler import integration."""
        # Mock successful import
        mock_class = Mock()
        mock_try_import.return_value = mock_class

        # Mock the descriptor lookup
        with patch(
            "acb.events.discovery.get_event_handler_descriptor"
        ) as mock_get_descriptor:
            mock_descriptor = Mock()
            mock_descriptor.name = "mock_publisher"
            mock_get_descriptor.return_value = mock_descriptor

            # Import handler
            result = import_event_handler("publisher")
            assert result == mock_class

            # Verify import was attempted
            mock_try_import.assert_called_once_with("publisher", "mock_publisher")

    async def test_events_service_discovery_integration(self):
        """Test Events Service integration with service discovery."""
        from acb.services.discovery import enable_service, get_service_descriptor

        # Enable events service
        enable_service("events", "events_service")

        # Get service descriptor
        descriptor = get_service_descriptor("events")

        if descriptor:
            assert descriptor.category == "events"
            assert descriptor.name == "events_service"
            assert descriptor.enabled is True

    async def test_full_stack_integration(self):
        """Test full stack integration across all Events components."""
        # Setup Events Service
        settings = EventsServiceSettings(
            enable_publisher=True,
            enable_subscriber=True,
            enable_health_checks=False,
        )

        service = await setup_events_service(settings)

        try:
            # Create multiple handlers using different methods

            # 1. Direct handler class
            direct_handler = SampleEventHandler("direct")

            # 2. Decorated handler
            @event_handler(event_type="decorated.event")
            def decorated_handler(event: Event) -> EventHandlerResult:
                return EventHandlerResult(success=True, metadata={"decorated": True})

            # 3. Specialized handler
            specialized_handler = SpecializedEventHandler("specialized.event")

            # Subscribe all handlers
            await service.subscribe(direct_handler)
            await service.subscribe(decorated_handler)
            await service.subscribe(specialized_handler)

            # Create events for all handlers
            events = [
                create_event("general.event", "service", {"handler": "direct"}),
                create_event("decorated.event", "service", {"handler": "decorated"}),
                create_event(
                    "specialized.event", "service", {"handler": "specialized"}
                ),
                create_event("broadcast.event", "service", {"handler": "all"}),
            ]

            # Publish all events
            for event in events:
                await service.publish(event)

            await asyncio.sleep(0.2)

            # Verify handling
            # Direct handler should receive general and broadcast events
            assert len(direct_handler.handled_events) >= 2

            # Specialized handler should receive specialized and broadcast events
            # (if it can handle broadcast events - depends on implementation)
            assert len(specialized_handler.handled_events) >= 1

            # Verify service metrics
            assert service.publisher.metrics.events_published == 4
            assert service.publisher.metrics.handlers_executed >= 4

        finally:
            await service.stop()


class TestPerformanceAndScalability:
    """Test performance and scalability aspects."""

    async def test_high_volume_event_processing(self):
        """Test processing high volume of events."""
        async with event_publisher_context() as publisher:
            handler = SampleEventHandler("high_volume")
            subscription = create_subscription(handler)
            await publisher.subscribe(subscription)

            # Create many events
            num_events = 100
            events = [
                create_event(f"volume.event.{i}", "volume_service", {"index": i})
                for i in range(num_events)
            ]

            # Measure processing time
            start_time = asyncio.get_event_loop().time()

            # Publish all events
            publish_tasks = [publisher.publish(event) for event in events]
            await asyncio.gather(*publish_tasks)

            # Wait for processing
            await asyncio.sleep(1.0)

            end_time = asyncio.get_event_loop().time()
            processing_time = end_time - start_time

            # Verify all events were processed
            assert len(handler.handled_events) == num_events

            # Verify performance (should process 100 events in reasonable time)
            assert processing_time < 10.0  # Should complete within 10 seconds

            # Verify metrics
            assert publisher.metrics.events_published == num_events
            assert publisher.metrics.handlers_executed == num_events

            # Calculate throughput
            throughput = num_events / processing_time
            print(f"Event processing throughput: {throughput:.2f} events/second")

    async def test_memory_usage_stability(self):
        """Test memory usage stability under load."""
        import gc

        async with event_publisher_context() as publisher:
            handler = SampleEventHandler("memory_test")
            subscription = create_subscription(handler)
            await publisher.subscribe(subscription)

            # Process events in batches to test memory stability
            batch_size = 50
            num_batches = 10

            for batch in range(num_batches):
                # Create batch of events
                events = [
                    create_event(f"memory.batch.{batch}.event.{i}", "memory_service")
                    for i in range(batch_size)
                ]

                # Publish batch
                for event in events:
                    await publisher.publish(event)

                # Wait for processing
                await asyncio.sleep(0.1)

                # Force garbage collection
                gc.collect()

                # Verify batch was processed
                expected_total = (batch + 1) * batch_size
                assert len(handler.handled_events) == expected_total

            # Verify total processing
            total_events = batch_size * num_batches
            assert len(handler.handled_events) == total_events
            assert publisher.metrics.events_published == total_events

    async def test_concurrent_publishers_and_subscribers(self):
        """Test concurrent publishers and subscribers."""
        # Create multiple publishers and subscribers
        num_publishers = 3
        num_subscribers = 2

        publishers = []
        subscribers = []
        handlers = []

        # Setup publishers
        for i in range(num_publishers):
            publisher = create_event_publisher()
            await publisher.start()
            publishers.append(publisher)

        # Setup subscribers
        for i in range(num_subscribers):
            subscriber = create_event_subscriber()
            await subscriber.start()
            subscribers.append(subscriber)

            # Create handler for each subscriber
            handler = SampleEventHandler(f"subscriber_{i}")
            await subscriber.subscribe(handler)
            handlers.append(handler)

        try:
            # Publish events from all publishers
            events_per_publisher = 10
            publish_tasks = []

            for pub_idx, publisher in enumerate(publishers):
                for event_idx in range(events_per_publisher):
                    event = create_event(
                        f"concurrent.pub{pub_idx}.event{event_idx}",
                        f"publisher_{pub_idx}",
                        {"publisher": pub_idx, "event": event_idx},
                    )
                    publish_tasks.append(publisher.publish(event))

            # Execute all publishes concurrently
            await asyncio.gather(*publish_tasks)

            # Manually deliver events to subscribers
            # (In real scenario, this would be handled by message queue)
            for pub_idx, publisher in enumerate(publishers):
                for event_idx in range(events_per_publisher):
                    event = create_event(
                        f"concurrent.pub{pub_idx}.event{event_idx}",
                        f"publisher_{pub_idx}",
                        {"publisher": pub_idx, "event": event_idx},
                    )

                    # Deliver to all subscribers
                    for subscriber in subscribers:
                        await subscriber.deliver_event(event)

            await asyncio.sleep(0.5)

            # Verify all events were processed
            total_expected_per_handler = num_publishers * events_per_publisher
            for handler in handlers:
                assert len(handler.handled_events) == total_expected_per_handler

            # Verify publisher metrics
            for publisher in publishers:
                assert publisher.metrics.events_published == events_per_publisher

        finally:
            # Cleanup
            for publisher in publishers:
                await publisher.stop()
            for subscriber in subscribers:
                await subscriber.stop()
