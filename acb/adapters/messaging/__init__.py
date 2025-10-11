"""ACB Messaging Adapter Package.

Dual-interface messaging backends supporting both pub/sub and queue patterns.

This package provides unified messaging backends with two interfaces:

1. **PubSubBackend**: For event-driven pub/sub patterns (events system)
   - Multiple subscribers per message
   - Topic-based routing
   - Pattern-based subscriptions
   - Fire-and-forget semantics

2. **QueueBackend**: For work queue patterns (tasks system)
   - Single consumer per message
   - Priority-based ordering
   - Message acknowledgments
   - Retry and dead-letter handling

Available Implementations:
- Memory: In-memory for development/testing
- Redis: Redis-backed for distributed systems
- RabbitMQ: Enterprise messaging with AMQP (via aio-pika)
- aiormq: RabbitMQ messaging with aiormq library

Example Usage:
    ```python
    from acb.adapters import import_adapter
    from acb.depends import depends

    # For events system (pub/sub pattern)
    PubSub = import_adapter("pubsub")
    pubsub = depends.get(PubSub)

    subscription = await pubsub.subscribe("events.user.*")
    await pubsub.publish("events.user.created", b"user data")

    # For tasks system (queue pattern)
    Queue = import_adapter("queue")
    queue = depends.get(Queue)

    await queue.enqueue("tasks", b"task data", priority=MessagePriority.HIGH)
    message = await queue.dequeue("tasks")
    if message:
        # Process task
        await queue.acknowledge("tasks", message.message_id)
    ```
"""

from ._base import (
    DeliveryMode,
    # Enums
    MessagePriority,
    MessagingCapability,
    MessagingConnectionError,
    # Exceptions
    MessagingException,
    MessagingOperationError,
    # Settings
    MessagingSettings,
    MessagingTimeoutError,
    # Interfaces
    PubSubBackend,
    # Messages
    PubSubMessage,
    QueueBackend,
    QueueEmptyError,
    QueueFullError,
    QueueMessage,
    UnifiedMessagingBackend,
)

# Export commonly used types
__all__ = [
    # Interfaces
    "PubSubBackend",
    "QueueBackend",
    "UnifiedMessagingBackend",
    # Settings
    "MessagingSettings",
    # Messages
    "PubSubMessage",
    "QueueMessage",
    # Enums
    "MessagePriority",
    "DeliveryMode",
    "MessagingCapability",
    # Exceptions
    "MessagingException",
    "MessagingConnectionError",
    "MessagingOperationError",
    "MessagingTimeoutError",
    "QueueFullError",
    "QueueEmptyError",
]
