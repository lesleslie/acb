> **ACB Documentation**: [Main](<../../../README.md>) | [Core Systems](<../../README.md>) | [Actions](<../../actions/README.md>) | [Adapters](<../README.md>) | [Messaging](<./README.md>)

# Messaging Adapter

The Messaging adapter delivers a unified abstraction for pub/sub and task queue
backends. It powers the events layer, task schedulers, and workflow engines by
normalizing message formats, delivery guarantees, and connection management
across Redis, RabbitMQ, AIORMQ, and in-memory transports.

## Table of Contents

- [Overview](<#overview>)
- [Message Models](<#message-models>)
- [Capabilities](<#capabilities>)
- [Settings](<#settings>)
- [Interfaces](<#interfaces>)
- [Built-in Implementations](<#built-in-implementations>)
- [Usage Examples](<#usage-examples>)
- [Queue Acknowledgement Example](<#queue-acknowledgement-example>)
- [Error Handling](<#error-handling>)
- [Best Practices](<#best-practices>)
- [Related Adapters](<#related-adapters>)

## Overview

`MessagingSettings`, `PubSubBackend`, and `QueueBackend` define the core contract
that adapters implement. Each backend can opt into one or both interfaces, and
`UnifiedMessagingBackend` offers convenience for transports that support both
patterns through a single connection pool.

## Message Models

- `PubSubMessage`: Contains topic, payload, headers, correlation ID, and
  timestamp metadata.
- `QueueMessage`: Adds queue names, priority, delayed delivery, retry counts,
  and headers for task-oriented workflows.
- Messages use UUID identifiers and UTC timestamps to support tracing and
  replay across distributed systems.

## Capabilities

`MessagingCapability` enumerates supported features such as:

- `PUB_SUB`, `PATTERN_SUBSCRIBE`, `BROADCAST` for fan-out workloads.
- `PRIORITY_QUEUE`, `DELAYED_MESSAGES`, `DEAD_LETTER_QUEUE` for task routing.
- Persistence, transactions, and clustering flags to surface reliability and
  scalability characteristics.

The discovery system reads capability metadata to wire adapters to the right
services (e.g., events publishers vs. task schedulers).

## Settings

`MessagingSettings` offers:

- Connection details (`connection_url`, `connection_timeout`, `max_connections`).
- Performance tuning (`batch_size`, `prefetch_count`) and retry policies.
- Feature toggles (`enable_persistence`, `enable_transactions`) that map to
  backend-specific options.

Adapters extend these settings with transport-specific fields (e.g., Redis
database index, RabbitMQ exchange/queue declarations).

## Interfaces

- `PubSubBackend` exposes `publish()`, `subscribe()`, and `unsubscribe()`
  primitives returning async iterators for message consumption.
- `QueueBackend` covers `enqueue()`, `dequeue()`, `acknowledge()`, `reject()`,
  and batch helpers.
- Async context managers manage connections, guaranteeing cleanup thanks to
  `CleanupMixin`.

## Built-in Implementations

| Module | Backend | Highlights |
| ------ | ------- | ---------- |
| `redis` | Redis Streams / PubSub | Fast in-memory transport with persistence and consumer groups. |
| `rabbitmq` | RabbitMQ via `aio-pika` | Rich routing, acknowledgements, DLQ, priority queues. |
| `aiormq` | Low-level AMQP backend | Minimal overhead for advanced RabbitMQ usage. |
| `memory` | In-memory transport | Useful for local development, unit tests, and CI. |

Each implementation registers module metadata and health checks so services can
verify readiness before accepting traffic.

## Usage Examples

```python
import json

from acb.adapters import import_adapter
from acb.adapters.messaging import QueueMessage
from acb.depends import depends

Messaging = import_adapter("messaging")


async def enqueue_job(payload: dict[str, object]) -> None:
    backend = await depends.get(Messaging)
    message = QueueMessage(
        queue="jobs",
        payload=json.dumps(payload).encode("utf-8"),
    )
    await backend.enqueue(message)
```

Consuming with pub/sub:

```python
from acb.adapters.messaging import PubSubMessage


async def consume_events(topic: str):
    backend = await depends.get(Messaging)
    async with backend.subscribe(topic) as stream:
        async for message in stream:
            assert isinstance(message, PubSubMessage)
            process(message)
```

## Queue Acknowledgement Example

```python
async def worker() -> None:
    backend = await depends.get(Messaging)
    while True:
        message = await backend.dequeue("jobs", timeout=2.0)
        if message is None:
            continue
        try:
            await handle_job(json.loads(message.payload))
        except Exception:
            await backend.reject(message.queue, message.message_id, requeue=True)
        else:
            await backend.acknowledge(message.queue, message.message_id)
```

This pattern ensures failed jobs are re-queued while successful work is
acknowledged immediately, keeping retry counts accurate across deployments.

## Error Handling

- `MessagingConnectionError`, `MessagingTimeoutError`, and `MessagingOperationError`
  help distinguish retryable vs. fatal failures.
- Queue-specific issues raise `QueueFullError` or `QueueEmptyError`, enabling
  graceful backpressure management.
- Implementations convert native driver exceptions into these types for
  consistent telemetry and alerting.

## Best Practices

- Set explicit `DeliveryMode` and `MessagePriority` to communicate intent to the
  backend; defaults assume at-least-once delivery.
- Use async context managers for subscribers to ensure connections close cleanly
  during deployment restarts.
- Monitor queue depth and retry counts via adapter-provided metrics to detect
  bottlenecks early.
- Combine with the [Events layer](<../../events/README.md>) to power event-driven
  systems, or with [Tasks](<../../tasks/README.md>) for background job queues.
- In tests, wire the memory backend via dependency overrides to avoid external
  infrastructure requirements.

## Related Adapters

- [Events](<../../events/README.md>)
- [Tasks](<../../tasks/README.md>)
- [Adapters Overview](<../README.md>)
