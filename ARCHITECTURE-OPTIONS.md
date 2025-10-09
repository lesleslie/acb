# ACB Architecture Options: Events, Tasks, and Messaging Infrastructure

## Current State Analysis

### What We Have Now

```
acb/
├── adapters/queue/       # "Universal" queue backend (trying to do both)
│   └── _base.py         # QueueBackend interface (pub/sub + task queues)
├── queues/              # Actually task/job processing system
│   └── _base.py         # TaskData, TaskHandler, scheduling
└── events/              # Event-driven messaging
    └── _base.py         # Event, EventMetadata, pub/sub patterns
```

### The Core Problem

The `QueueBackend` tries to be universal for both events and tasks, but they have fundamentally different semantics:

**Events (Pub/Sub Pattern)**:

- Multiple subscribers to same event
- Fire-and-forget delivery
- Topic/channel based routing
- No acknowledgment needed
- Broadcast capability
- Real-time streaming

**Tasks (Work Queue Pattern)**:

- Single worker processes each task
- Guaranteed execution with retries
- Queue-based distribution
- Acknowledgment required
- Priority ordering
- Scheduled/delayed execution

## Architectural Options

### Option 1: Separate Backends (Clean Separation)

```
acb/
├── adapters/
│   ├── messaging/       # For events (pub/sub)
│   │   ├── _base.py    # MessagingBackend interface
│   │   ├── memory.py   # In-memory pub/sub
│   │   ├── redis.py    # Redis pub/sub
│   │   └── rabbitmq.py # RabbitMQ exchanges
│   └── queuing/        # For tasks (work queues)
│       ├── _base.py    # QueuingBackend interface
│       ├── memory.py   # In-memory job queue
│       ├── redis.py    # Redis lists/streams
│       └── rabbitmq.py # RabbitMQ work queues
├── events/             # High-level event system
│   └── _base.py       # Uses MessagingBackend
└── tasks/              # High-level task system (renamed from queues/)
    └── _base.py       # Uses QueuingBackend
```

**Pros**:

- Crystal clear separation of concerns
- Each backend optimized for its use case
- No conceptual confusion
- Events use messaging semantics (topics, broadcasts)
- Tasks use queuing semantics (FIFO, acknowledgments)

**Cons**:

- Some code duplication between backends
- Two sets of adapters to maintain
- Redis/RabbitMQ can do both - we'd have two adapters

### Option 2: Unified Transport with Semantic Layers

```
acb/
├── adapters/
│   └── transport/      # Low-level message transport
│       ├── _base.py    # TransportBackend interface (minimal)
│       ├── memory.py   # In-memory transport
│       ├── redis.py    # Redis transport
│       └── rabbitmq.py # RabbitMQ transport
├── messaging/          # Pub/sub semantics layer
│   └── _base.py       # MessagingLayer(TransportBackend)
├── queuing/           # Work queue semantics layer
│   └── _base.py       # QueuingLayer(TransportBackend)
├── events/            # High-level event system
│   └── _base.py      # Uses MessagingLayer
└── tasks/             # High-level task system
    └── _base.py      # Uses QueuingLayer
```

**Pros**:

- Single transport adapter per backend (Redis, RabbitMQ, etc.)
- Clear semantic separation at the layer level
- Reuses transport connections efficiently
- Easier to add new transports

**Cons**:

- More complex layering
- Transport interface must be generic enough for both patterns
- Performance overhead from abstraction layers

### Option 3: Pattern-Based Backends (Current Approach, Refined)

```
acb/
├── adapters/
│   └── queue/         # Keep as "queue" but make patterns explicit
│       ├── _base.py   # QueueBackend with explicit pattern support
│       ├── memory.py  # Memory implementation (both patterns)
│       ├── redis.py   # Redis (pub/sub + lists)
│       └── rabbitmq.py # RabbitMQ (exchanges + queues)
├── events/            # Event system
│   └── _base.py      # Uses QueueBackend in pub/sub mode
└── tasks/            # Task system (renamed from queues/)
    └── _base.py      # Uses QueueBackend in work queue mode
```

```python
class QueueBackend:
    """Backend supporting both patterns explicitly."""

    # Pub/Sub Pattern (for events)
    async def publish(self, topic: str, message: bytes) -> None: ...
    async def subscribe(self, topic: str) -> AsyncIterator[bytes]: ...

    # Work Queue Pattern (for tasks)
    async def enqueue(self, queue: str, message: bytes) -> None: ...
    async def dequeue(self, queue: str) -> bytes | None: ...
    async def acknowledge(self, message_id: str) -> None: ...
```

**Pros**:

- Single backend implementation per technology
- Both patterns explicitly supported
- Clear method naming shows intent
- Matches what Redis/RabbitMQ actually provide

**Cons**:

- Backend interface is larger
- Risk of using wrong pattern
- Still some conceptual mixing

### Option 4: Hybrid Approach (Recommended)

```
acb/
├── adapters/
│   └── messaging/     # Renamed from "queue" for clarity
│       ├── _base.py   # Two interfaces: PubSubBackend and QueueBackend
│       ├── memory.py  # Implements both interfaces
│       ├── redis.py   # Implements both interfaces
│       └── rabbitmq.py # Implements both interfaces
├── events/            # Event-driven system
│   └── _base.py      # Uses PubSubBackend interface
└── tasks/             # Task processing system
    └── _base.py      # Uses QueueBackend interface
```

```python
# acb/adapters/messaging/_base.py


class PubSubBackend(ABC):
    """Interface for pub/sub messaging patterns."""

    async def publish(self, topic: str, message: Message) -> None: ...
    async def subscribe(self, pattern: str) -> Subscription: ...
    async def unsubscribe(self, subscription: Subscription) -> None: ...


class QueueBackend(ABC):
    """Interface for work queue patterns."""

    async def enqueue(self, queue: str, task: Task, priority: int) -> str: ...
    async def dequeue(self, queue: str, timeout: float) -> Task | None: ...
    async def acknowledge(self, task_id: str) -> None: ...
    async def reject(self, task_id: str, requeue: bool) -> None: ...


class UnifiedMessagingBackend(PubSubBackend, QueueBackend):
    """Backends that support both patterns inherit both interfaces."""

    pass


# Each implementation
class RedisBackend(UnifiedMessagingBackend):
    """Redis supports both pub/sub and queues."""

    # Implement both interfaces
```

**Pros**:

- Clear interface separation
- Single implementation per technology
- Type safety - events can only use PubSubBackend
- Flexibility - some backends might only implement one interface
- Natural upgrade path from memory to Redis/RabbitMQ

**Cons**:

- Two interfaces to understand
- Backends need to implement both (but that's reality)

## Pattern for `_base.py` Files

### Proposed Standard

**Rule**: Use `_base.py` when you need to define an abstract interface or protocol that multiple implementations will follow.

**Where to use `_base.py`**:

1. ✅ **All adapter categories** - Define the adapter interface
1. ✅ **High-level systems with multiple backends** (events, tasks, workflows)
1. ✅ **Services that have multiple implementations** (repository pattern)
1. ❌ **Concrete implementations** - Don't need \_base.py
1. ❌ **Single-implementation modules** - Don't need \_base.py

**Current Status**:

```
✅ Correct Usage:
- acb/adapters/*/_base.py    # All adapter interfaces
- acb/events/_base.py        # Multiple event backends
- acb/tasks/_base.py         # Multiple task backends
- acb/workflows/_base.py     # Multiple workflow engines
- acb/services/repository/_base.py  # Repository pattern

❌ Questionable/Remove:
- acb/services/_base.py      # ServiceBase could be in __init__.py
- acb/migration/_base.py     # If only one implementation
```

**Standard Structure**:

```python
# _base.py
"""Interface definition for [component type].

This module defines the abstract interface that all [component]
implementations must follow. It should NOT contain any concrete
implementation code.
"""

from abc import ABC, abstractmethod


class ComponentInterface(ABC):
    """Abstract interface for components."""

    @abstractmethod
    async def required_method(self) -> None:
        """Every implementation MUST have this."""
        ...

    def optional_method(self) -> None:
        """Implementations MAY override this."""
        return self._default_behavior()
```

## Recommendation

**Go with Option 4 (Hybrid Approach)** because it:

1. **Provides clear separation** between pub/sub and queue patterns
1. **Acknowledges reality** that Redis/RabbitMQ support both patterns
1. **Maintains type safety** - events can't accidentally use queue methods
1. **Allows gradual migration** from the current mixed approach
1. **Follows principle of least surprise** - messaging backends do messaging

**Implementation Plan**:

1. **Phase 1**: Rename and restructure

   - `acb/queues/` → `acb/tasks/`
   - `acb/adapters/queue/` → `acb/adapters/messaging/`

1. **Phase 2**: Split interfaces in `messaging/_base.py`

   - Create `PubSubBackend` interface
   - Create `QueueBackend` interface
   - Create `UnifiedMessagingBackend` combining both

1. **Phase 3**: Update implementations

   - Update events to use `PubSubBackend`
   - Update tasks to use `QueueBackend`
   - Messaging adapters implement `UnifiedMessagingBackend`

1. **Phase 4**: Clean up `_base.py` usage across codebase

   - Remove unnecessary `_base.py` files
   - Ensure consistent pattern usage

This approach provides the best balance of clarity, maintainability, and pragmatism.
