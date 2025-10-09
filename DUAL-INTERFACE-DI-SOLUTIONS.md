# Dependency Injection Solutions for Dual-Interface Adapters

## The Challenge

With our proposed architecture:

```python
# acb/adapters/messaging/_base.py
class PubSubBackend(ABC):
    """For events - pub/sub pattern"""

    async def publish(self, topic: str, message: bytes) -> None: ...
    async def subscribe(self, topic: str) -> AsyncIterator[bytes]: ...


class QueueBackend(ABC):
    """For tasks - work queue pattern"""

    async def enqueue(self, queue: str, task: bytes) -> str: ...
    async def dequeue(self, queue: str) -> bytes | None: ...
    async def acknowledge(self, task_id: str) -> None: ...


# acb/adapters/messaging/redis.py
class RedisMessaging(PubSubBackend, QueueBackend):
    """Redis implements both interfaces"""

    # Implementation of both interfaces
```

**The problem**: How does `import_adapter("messaging")` know which interface to return?

## Solution Options

### Solution 1: Two Separate Adapter Categories ✅ (Recommended)

Register them as two distinct adapter types in the registry:

```python
# acb/adapters/__init__.py
static_mappings = {
    # Events use pubsub adapters
    "pubsub.memory": ("acb.adapters.messaging.memory", "MemoryPubSub"),
    "pubsub.redis": ("acb.adapters.messaging.redis", "RedisPubSub"),
    "pubsub.rabbitmq": ("acb.adapters.messaging.rabbitmq", "RabbitMQPubSub"),
    # Tasks use queue adapters
    "queue.memory": ("acb.adapters.messaging.memory", "MemoryQueue"),
    "queue.redis": ("acb.adapters.messaging.redis", "RedisQueue"),
    "queue.rabbitmq": ("acb.adapters.messaging.rabbitmq", "RabbitMQQueue"),
}
```

```python
# acb/adapters/messaging/redis.py
class RedisMessaging(PubSubBackend, QueueBackend):
    """Unified implementation"""

    async def publish(self, topic: str, message: bytes) -> None:
        # Redis pub/sub implementation
        ...

    async def enqueue(self, queue: str, task: bytes) -> str:
        # Redis list implementation
        ...


# Export with different names for DI
RedisPubSub = RedisMessaging  # For events
RedisQueue = RedisMessaging  # For tasks
```

**Usage**:

```python
# Events system
from acb.depends import depends, Inject
from acb.adapters import import_adapter

PubSub = import_adapter("pubsub")  # Gets RedisPubSub (which is RedisMessaging)


@depends.inject
async def publish_event(pubsub: Inject[PubSub]):
    await pubsub.publish("events", b"data")


# Tasks system
Queue = import_adapter("queue")  # Gets RedisQueue (which is also RedisMessaging)


@depends.inject
async def enqueue_task(queue: Inject[Queue]):
    await queue.enqueue("tasks", b"work")
```

**Pros**:

- ✅ Works with existing DI system unchanged
- ✅ Clear separation in usage
- ✅ Type safety maintained
- ✅ Single implementation class

**Cons**:

- Two adapter categories for what's really one backend
- Slight naming redundancy

### Solution 2: Composite Adapter with Properties

Make the adapter return a composite object with both interfaces:

```python
# acb/adapters/messaging/redis.py
class RedisMessaging:
    """Composite adapter with both interfaces"""

    def __init__(self):
        self._pubsub = RedisPubSubImpl()
        self._queue = RedisQueueImpl()

    @property
    def pubsub(self) -> PubSubBackend:
        """Get pub/sub interface"""
        return self._pubsub

    @property
    def queue(self) -> QueueBackend:
        """Get queue interface"""
        return self._queue


# Export as Messaging
Messaging = RedisMessaging
```

**Usage**:

```python
Messaging = import_adapter("messaging")


@depends.inject
async def my_function(messaging: Inject[Messaging]):
    # For events
    await messaging.pubsub.publish("topic", b"data")

    # For tasks
    await messaging.queue.enqueue("queue", b"task")
```

**Pros**:

- Single adapter registration
- Both interfaces accessible

**Cons**:

- ❌ Breaks existing patterns
- ❌ Users must know to use `.pubsub` or `.queue`
- ❌ Less type safety

### Solution 3: Factory Functions

Use factory functions to get the right interface:

```python
# acb/adapters/messaging/__init__.py
def import_pubsub(backend: str = None) -> type[PubSubBackend]:
    """Import pub/sub backend"""
    backend = backend or get_configured_backend()
    module = import_module(f"acb.adapters.messaging.{backend}")
    return module.PubSub


def import_queue(backend: str = None) -> type[QueueBackend]:
    """Import queue backend"""
    backend = backend or get_configured_backend()
    module = import_module(f"acb.adapters.messaging.{backend}")
    return module.Queue
```

**Usage**:

```python
from acb.adapters.messaging import import_pubsub, import_queue

PubSub = import_pubsub()  # Gets Redis pub/sub
Queue = import_queue()  # Gets Redis queue


@depends.inject
async def event_handler(pubsub: Inject[PubSub]):
    await pubsub.publish("events", b"data")
```

**Pros**:

- Explicit interface selection
- Clean separation

**Cons**:

- ❌ Different from standard `import_adapter()` pattern
- ❌ Requires new import functions

### Solution 4: Protocol-Based Type Narrowing

Use Python protocols and type narrowing:

```python
# acb/adapters/messaging/_base.py
from typing import Protocol, runtime_checkable


@runtime_checkable
class PubSubProtocol(Protocol):
    async def publish(self, topic: str, message: bytes) -> None: ...
    async def subscribe(self, topic: str) -> AsyncIterator[bytes]: ...


@runtime_checkable
class QueueProtocol(Protocol):
    async def enqueue(self, queue: str, task: bytes) -> str: ...
    async def dequeue(self, queue: str) -> bytes | None: ...


class MessagingBackend(PubSubProtocol, QueueProtocol):
    """Combined interface"""

    pass
```

**Usage**:

```python
Messaging = import_adapter("messaging")


@depends.inject
async def event_handler(messaging: Inject[Messaging]):
    # Type checker sees both protocols available
    if isinstance(messaging, PubSubProtocol):
        await messaging.publish("topic", b"data")
```

**Pros**:

- Type safe with protocols
- Single adapter

**Cons**:

- ❌ Runtime type checking needed
- ❌ Less explicit than separate interfaces

## Configuration Approach

Regardless of solution, configuration would look like:

### For Solution 1 (Recommended):

```yaml
# settings/adapters.yml
pubsub: redis    # For events
queue: redis     # For tasks

# Or use different backends
pubsub: rabbitmq
queue: redis
```

### For Other Solutions:

```yaml
# settings/adapters.yml
messaging: redis  # Single backend for both
```

## Recommendation

**Use Solution 1: Two Separate Adapter Categories**

This approach:

1. **Works with existing ACB patterns** - No changes to DI system
1. **Provides clarity** - `import_adapter("pubsub")` vs `import_adapter("queue")`
1. **Maintains type safety** - Each interface is separate
1. **Allows flexibility** - Could use Redis for events, RabbitMQ for tasks

**Implementation structure**:

```
acb/
├── adapters/
│   └── messaging/           # Physical location
│       ├── _base.py         # Both interfaces defined
│       ├── memory.py        # MemoryMessaging class
│       ├── redis.py         # RedisMessaging class
│       └── rabbitmq.py      # RabbitMQMessaging class
```

**Registration**:

```python
# Each implementation exports two names
# acb/adapters/messaging/redis.py


class RedisMessaging(PubSubBackend, QueueBackend):
    """Single implementation, dual interface"""

    # ... implementation ...


# Export with role-specific names
RedisPubSub = RedisMessaging
RedisQueue = RedisMessaging
```

This gives us:

- ✅ **Clean DI**: `PubSub = import_adapter("pubsub")`
- ✅ **Type safety**: Events can only see PubSub methods
- ✅ **Single implementation**: No code duplication
- ✅ **Flexible configuration**: Can mix backends if needed

The slight redundancy in registration is a small price for maintaining ACB's clean adapter pattern and type safety.
