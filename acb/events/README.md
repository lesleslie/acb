> **ACB Documentation**: [Main](<../../README.md>) | [Core Systems](<../README.md>) | [Events](<./README.md>) | [Services](<../services/README.md>) | [Adapters](<../adapters/README.md>)

# ACB: Events

The events layer delivers asynchronous, event-driven messaging for the ACB
framework. It combines strongly typed event models, discovery-driven handler
registration, and transport-agnostic publishers/subscribers that ride on top of
queue adapters such as Redis, RabbitMQ, Kafka, or in-memory backends.

## Table of Contents

- [Overview](<#overview>)
- [Core Building Blocks](<#core-building-blocks>)
- [Discovery & Metadata](<#discovery--metadata>)
- [Publishing Events](<#publishing-events>)
- [Consuming & Routing](<#consuming--routing>)
- [Integration Patterns](<#integration-patterns>)
- [Best Practices](<#best-practices>)
- [Related Resources](<#related-resources>)

## Overview

Events provide structured messages (`Event`) with rich metadata describing
delivery guarantees, priorities, routing keys, and correlation identifiers. The
layer exposes tools for generating UUIDv7/UUID4 identifiers, capturing retry
state, and enforcing deadlines so that handlers can focus on business logic
instead of transport plumbing.

## Core Building Blocks

- `EventMetadata`: Tracks source, timestamps, delivery mode, routing headers,
  and retry/timeout configuration.
- `Event`: Wraps a payload dict plus mutable processing status such as retry
  count, error message, and completion state.
- Enumerations: `EventPriority`, `EventStatus`, and `EventDeliveryMode` codify
  ordering and reliability semantics.
- `EventHandler` / `FunctionalEventHandler`: Base classes that support both
  object-oriented and decorator-based handler registration.
- `EventHandlerResult`: Communicates success, retry hints, and custom metadata
  back to publishers or orchestrators.
- `EventSubscription`: Describes active subscriptions with pattern matching and
  delivery preferences, reusable by publishers or subscribers.

## Discovery & Metadata

Handler discovery mirrors the broader ACB registry pattern:

- `register_event_handlers()` scans the package for handler modules and stores
  descriptors (`EventHandlerDescriptor`) in the discovery registry.
- Helper APIs such as `list_event_handlers()`, `list_enabled_event_handlers()`,
  and `list_event_handlers_by_capability()` expose the catalog for diagnostics
  or UI surfaces.
- Capability flags (`EventCapability`) and metadata factories (`create_event_metadata_template()`)
  document expectations for latency, durability, and payload shape.
- `apply_event_handler_overrides()` and `enable_event_handler()` allow operators
  to toggle handlers at runtime without code changes.

## Publishing Events

`EventPublisher` coordinates publication across adapters with support for batch
flush, exponential backoff, dead-letter queues, and metrics:

- Configure with `EventPublisherSettings` (topic prefix, concurrency, retry
  policy, logging).
- Collect runtime stats through `PublisherMetrics`, surfaced to health checks
  and dashboards.
- Instantiate via `create_event_publisher()` or the `event_publisher_context()`
  async context manager for dependency-injected lifecycles.
- Fallback mocks ensure tests can run without real queues; once adapters are
  registered, dependency injection (`depends.get`) binds the actual backend.

```python
from acb.events import EventPublisher, EventPublisherSettings, create_event

event = create_event(
    event_type="user.created",
    source="accounts",
    payload={"user_id": "abc-123"},
)

async with EventPublisher(EventPublisherSettings(log_events=True)) as publisher:
    await publisher.publish(event)
```

## Consuming & Routing

Message consumption is driven by the subscriber toolkit:

- `EventSubscriber` manages long-lived consumers, connection pooling, and
  backpressure via `SubscriberSettings`.
- `EventRouter` fans out messages to registered handlers, while `EventFilter`
  applies predicate logic (headers, tags, priority).
- `SubscriptionMode` toggles between push, polling, and replay behaviors, and
  `ManagedSubscription` encapsulates acknowledgement and checkpoint handling.
- Use `create_event_subscriber()` or `event_subscriber_context()` to bootstrap a
  managed subscriber from configuration.

```python
from acb.events import EventSubscriber, event_handler


@event_handler("user.created")
async def onboard_user(event):
    user_id = event.payload["user_id"]
    # hydrate account, provision resources, etc.
    return {"provisioned": True, "user_id": user_id}


async with EventSubscriber() as subscriber:
    await subscriber.add_handler(onboard_user)
    await subscriber.consume_forever()
```

## Integration Patterns

- **Services**: `EventsService` wraps publisher/subscriber lifecycles so that the
  services layer can monitor health, expose metrics, and respect startup order.
- **Adapters**: Queue adapters are imported dynamically (`import_adapter('queue')`)
  keeping event logic transport-agnostic and easily testable.
- **Workflows & Tasks**: Combine the events layer with scheduled jobs (`acb.tasks`)
  to emit recurring or delayed messages.
- **Observability**: Surface `PublisherMetrics` and subscriber statistics through
  the logging helpers and health endpoints in `acb.services`.

## Best Practices

- Generate events through `create_event()` to guarantee metadata completeness
  and consistent UUID generation.
- Keep handlers idempotent; leverage correlation IDs and custom headers for
  deduplication across retries.
- Apply filters and routing keys instead of branching on payload contents to
  keep subscriptions declarative.
- Run publishers/subscribers inside dependency-injected contexts so resource
  cleanup (connections, background tasks) happens deterministically.
- Enable metrics and structured logging (`log_events=True`) in production to aid
  incident response and replay decisions.

## Related Resources

- [Services](<../services/README.md>)
- [Adapters](<../adapters/README.md>)
- [Tasks](<../tasks/README.md>)
- [Main Documentation](<../../README.md>)
