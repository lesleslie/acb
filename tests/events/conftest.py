"""Shared fixtures for Events System tests."""

from unittest.mock import MagicMock
from uuid import uuid4

import asyncio
import pytest
from typing import Any

from acb.adapters.messaging import MessagePriority, QueueMessage


class MockQueueSubscription:
    """Async context manager wrapper for queue subscription."""

    def __init__(self, queue: "MockQueue", topic: str):
        self._queue = queue
        self._topic = topic
        self._message_queue: asyncio.Queue | None = None

    async def __aenter__(self):
        """Start subscription."""
        # Create queue for this subscription
        self._message_queue = asyncio.Queue()

        # Register subscription
        if self._topic not in self._queue._subscriptions:
            self._queue._subscriptions[self._topic] = []
        self._queue._subscriptions[self._topic].append(self._message_queue)

        return self._iterate_messages()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup subscription."""
        if self._topic in self._queue._subscriptions and self._message_queue:
            self._queue._subscriptions[self._topic].remove(self._message_queue)

    async def _iterate_messages(self):
        """Async generator that yields messages."""
        while True:
            try:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=0.1)
                yield message
            except TimeoutError:
                # Check if we should stop (connection closed)
                if not self._queue._connected:
                    break
                continue


class MockQueue:
    """Mock queue adapter for testing events system."""

    def __init__(self):
        self._connected = False
        self._messages = []
        self._subscriptions = {}
        self._acknowledged_messages = []
        self._rejected_messages = []
        self.published_messages = []  # For test verification

    @staticmethod
    def _matches_pattern(topic: str, pattern: str) -> bool:
        """Check if topic matches pattern (supports * wildcard).

        Wildcard matching rules:
        - 'events.*' matches 'events.foo', 'events.bar', etc. (single level)
        - 'events.*.created' matches 'events.user.created', 'events.order.created', etc.
        - Exact match always works
        """
        if pattern == topic:
            return True
        if "*" not in pattern:
            return False

        # Split into parts
        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")

        # If last part of pattern is *, it can match one or more topic parts
        if pattern_parts[-1] == "*":
            # 'events.*' should match 'events.test.event' (zero or more levels)
            prefix_parts = pattern_parts[:-1]
            if len(topic_parts) < len(prefix_parts):
                return False
            # Check that prefix matches
            return all(
                p == t for p, t in zip(prefix_parts, topic_parts[: len(prefix_parts)])
            )

        # Otherwise, must have same number of parts
        if len(pattern_parts) != len(topic_parts):
            return False

        # Check each part matches (allowing * wildcard)
        return all(p == "*" or p == t for p, t in zip(pattern_parts, topic_parts))

    async def connect(self) -> None:
        """Connect to mock queue."""
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from mock queue."""
        self._connected = False
        self._messages.clear()
        self._subscriptions.clear()

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def publish(
        self,
        topic: str,
        payload: bytes,
        priority: MessagePriority | None = None,
        headers: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> str:
        """Publish message to topic."""
        message = QueueMessage(
            message_id=str(uuid4()),
            topic=topic,
            payload=payload,
            priority=priority or MessagePriority.NORMAL,
            headers=headers or {},
            correlation_id=correlation_id,
        )
        self._messages.append(message)
        self.published_messages.append(message)

        # Notify subscribers - support wildcard pattern matching
        for pattern, queues in self._subscriptions.items():
            if self._matches_pattern(topic, pattern):
                for queue in queues:
                    await queue.put(message)

        return message.message_id

    async def enqueue(
        self,
        topic: str,
        payload: bytes,
        priority: MessagePriority | None = None,
        delay_seconds: float | None = None,
        **kwargs,
    ) -> str:
        """Enqueue message (simpler publish for task queue pattern)."""
        # For delayed messages, we simulate delay by scheduling
        if delay_seconds and delay_seconds > 0:
            # In real implementation, queue adapter handles delays
            # For tests, we just publish immediately
            pass

        return await self.publish(
            topic=topic,
            payload=payload,
            priority=priority,
            **kwargs,
        )

    def subscribe(self, topic: str, prefetch: int | None = None):
        """Subscribe to topic pattern."""
        return MockQueueSubscription(self, topic)

    async def acknowledge(
        self, message: QueueMessage, timeout: float | None = None
    ) -> None:
        """Acknowledge message processing."""
        self._acknowledged_messages.append(message)

    async def reject(
        self,
        message: QueueMessage,
        requeue: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Reject message."""
        self._rejected_messages.append((message, requeue))


@pytest.fixture
def mock_queue():
    """Create mock queue adapter for testing."""
    return MockQueue()


@pytest.fixture
async def connected_mock_queue(mock_queue):
    """Create and connect mock queue adapter."""
    await mock_queue.connect()
    yield mock_queue
    await mock_queue.disconnect()


@pytest.fixture(scope="function")
def mock_queue_adapter_import(mock_queue, monkeypatch):
    """Patch ACB's testing mode to return our mock queue for queue adapter.

    ACB automatically returns MagicMock() for all adapters when pytest is running.
    This fixture overrides that behavior specifically for the queue adapter.
    """
    import acb.adapters
    from acb.depends import depends

    # Create mock logger with all necessary attributes
    mock_logger = MagicMock()
    mock_logger.info = MagicMock()
    mock_logger.debug = MagicMock()
    mock_logger.error = MagicMock()
    mock_logger.warning = MagicMock()
    mock_logger.exception = MagicMock()

    # Create a stable class for the mock queue that we can register with bevy
    class MockQueueAdapter:
        """Marker class for mock queue adapter."""

        pass

    # Store the original _handle_testing_mode function
    original_testing_mode = acb.adapters._handle_testing_mode

    def custom_testing_mode(adapter_categories):
        """Custom testing mode that returns MockQueueAdapter for queue, MagicMock for others."""
        # Handle both string and list forms
        if adapter_categories == "queue" or adapter_categories == ["queue"]:
            return MockQueueAdapter

        # For everything else, use the original behavior
        return original_testing_mode(adapter_categories)

    # Patch _handle_testing_mode
    monkeypatch.setattr("acb.adapters._handle_testing_mode", custom_testing_mode)

    # Register the mock_queue instance with bevy's dependency injection
    # so when EventPublisher calls depends.get(MockQueueAdapter), it gets our mock
    depends.set(MockQueueAdapter, mock_queue)

    # Register mock logger with bevy's dependency injection
    from acb.logger import Logger

    depends.set(Logger, mock_logger)

    # Also patch ServiceBase.logger to directly return the mock
    from acb.services._base import ServiceBase

    original_logger = ServiceBase.logger

    def mock_logger_property(self):
        return mock_logger

    monkeypatch.setattr(ServiceBase, "logger", property(mock_logger_property))

    yield mock_queue

    # Restore original logger
    monkeypatch.setattr(ServiceBase, "logger", original_logger)

    # Cleanup: Remove the registration to avoid test pollution
    # Note: bevy doesn't have a clean "remove" API, so we rely on test isolation
