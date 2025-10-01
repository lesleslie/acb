"""ACB Queue Adapter Package.

Unified queue backend implementations for task queues and event pub/sub.

This package provides a common interface for different queue backends:
- Memory: In-memory queue for development/testing
- Redis: Redis-backed queue for distributed systems
- RabbitMQ: RabbitMQ-backed queue for enterprise messaging

All adapters implement the QueueBackend interface with support for:
- Task queue operations (enqueue/dequeue)
- Event pub/sub operations (publish/subscribe)
- Priority-based message ordering
- Delayed message delivery
- Dead letter queue handling
- Connection pooling and health monitoring

Example Usage:
    ```python
    from acb.adapters import import_adapter
    from acb.depends import depends

    # Import the queue adapter (configured in settings/adapters.yml)
    Queue = import_adapter("queue")
    queue = depends.get(Queue)

    # Task queue pattern
    await queue.enqueue("tasks", b"task data", priority=MessagePriority.HIGH)
    message = await queue.dequeue("tasks")
    if message:
        # Process task
        await queue.acknowledge(message)

    # Pub/sub pattern
    await queue.publish("events", b"event data")
    async with queue.subscribe("events") as messages:
        async for message in messages:
            # Process event
            await queue.acknowledge(message)
    ```
"""

from acb.adapters.queue._base import (
    DeliveryMode,
    MessagePriority,
    QueueBackend,
    QueueCapability,
    QueueConnectionError,
    QueueEmptyError,
    QueueException,
    QueueFullError,
    QueueMessage,
    QueueOperationError,
    QueueSettings,
    QueueTimeoutError,
)

# Export commonly used types
__all__ = [
    # Base interface
    "QueueBackend",
    "QueueSettings",
    "QueueMessage",
    # Enums
    "MessagePriority",
    "DeliveryMode",
    "QueueCapability",
    # Exceptions
    "QueueException",
    "QueueConnectionError",
    "QueueOperationError",
    "QueueTimeoutError",
    "QueueFullError",
    "QueueEmptyError",
]
