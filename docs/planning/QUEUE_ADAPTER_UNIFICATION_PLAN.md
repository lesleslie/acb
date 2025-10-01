---
id: 01K6GMDSGR3SST4YMX1YG34AF2
---
______________________________________________________________________

## id: 01K6GKSXXJT16VT27CMKS6J4WD

______________________________________________________________________

## id: 01K6GKJPYH4WE31JHDV90HWY4D

______________________________________________________________________

## id: 01K6GJYHT5HFZVX53K38AFGGQ1

______________________________________________________________________

## id: 01K6GGMBZSMSM8YKD1V0MPRFVB

______________________________________________________________________

## id: 01K6G68703TCCKCE3WVZ03060V

______________________________________________________________________

## id: 01K6G5HQ8PAXX3DGS91WG1NG72

______________________________________________________________________

## id: 01K6G58F76KJ18NMS70W773S5W

______________________________________________________________________

## id: 01K6G4MF4DEBKWRAZ7KB85MYV7

______________________________________________________________________

## id: 01K6G3R7C1XEC87Q19TZCAE0TQ

______________________________________________________________________

## id: 01K6G39661493PRJ3QJN8QD0VA

______________________________________________________________________

## id: 01K6G25MNW0V36KB2G9S52G5JB

# Queue Adapter Unification Implementation Plan

**Version:** 0.20.0
**Status:** Draft
**Date:** 2025-10-01
**Breaking Change:** Yes

## Executive Summary

This plan unifies the queue backend implementations into a single adapter layer, with separate orchestration layers for events and tasks. This eliminates code duplication, provides clearer architecture, and simplifies configuration.

## Current State Analysis

### Problems

1. **Code Duplication**: Queue backends (memory, redis, rabbitmq) are duplicated between:

   - `acb/queues/memory.py`, `acb/queues/redis.py`, `acb/queues/rabbitmq.py`
   - Event backends embedded in `acb/events/publisher.py`

1. **Architectural Confusion**:

   - `acb/queues/` mixes adapter implementations with orchestration logic
   - `acb/events/` has backend logic embedded in orchestration code
   - Unclear separation of concerns

1. **Inconsistent with ACB Patterns**:

   - Other adapters (cache, storage, sql) are in `acb/adapters/`
   - Queue backends should follow same pattern

### Current Structure

```
acb/
├── queues/
│   ├── _base.py          # TaskQueue interface
│   ├── memory.py         # Memory queue implementation
│   ├── redis.py          # Redis queue implementation
│   ├── rabbitmq.py       # RabbitMQ queue implementation
│   ├── scheduler.py      # Task scheduling orchestration
│   └── discovery.py      # Queue discovery
│
└── events/
    ├── _base.py          # Event interfaces
    ├── publisher.py      # EventPublisher with embedded backends
    ├── subscriber.py     # EventSubscriber
    └── discovery.py      # Event discovery
```

## Target Architecture

### New Structure

```
acb/
├── adapters/
│   └── queue/            # UNIFIED queue adapter
│       ├── __init__.py
│       ├── _base.py      # QueueBackend interface
│       ├── memory.py     # In-memory queue (with MODULE_METADATA)
│       ├── redis.py      # Redis queue (with MODULE_METADATA)
│       └── rabbitmq.py   # RabbitMQ queue (with MODULE_METADATA)
│
├── events/               # Event orchestration layer
│   ├── __init__.py
│   ├── _base.py          # Event types and interfaces
│   ├── publisher.py      # EventPublisher (uses queue adapter)
│   ├── subscriber.py     # EventSubscriber (uses queue adapter)
│   └── discovery.py      # Event system discovery
│
└── queues/               # Task orchestration layer
    ├── __init__.py
    ├── _base.py          # Task types and interfaces
    ├── scheduler.py      # TaskScheduler (uses queue adapter)
    ├── worker.py         # Task worker management
    └── discovery.py      # Task queue discovery
```

### Key Principles

1. **Single Responsibility**:

   - `adapters/queue/` = low-level message queue interface
   - `events/` = pub/sub event orchestration
   - `queues/` = task queue orchestration

1. **DRY**: One implementation of each backend (redis, rabbitmq, memory)

1. **Layered Architecture**:

   ```
   Events/Tasks (orchestration)
        ↓ uses
   Queue Adapter (backends)
        ↓ connects to
   External Systems (Redis, RabbitMQ)
   ```

1. **Configuration**: Single `queue` adapter selection in `settings/adapters.yml`

## Implementation Phases

### Phase 1: Create Queue Adapter Foundation (2-3 hours)

**Tasks:**

1. **Create adapter directory structure**:

   ```bash
   mkdir -p acb/adapters/queue
   touch acb/adapters/queue/__init__.py
   ```

1. **Design unified QueueBackend interface** (`acb/adapters/queue/_base.py`):

   ```python
   from abc import ABC, abstractmethod
   from typing import Any, AsyncGenerator


   class QueueBackend(ABC):
       """Unified queue backend interface for events and tasks."""

       @abstractmethod
       async def publish(self, topic: str, message: Any) -> None:
           """Publish message to topic."""

       @abstractmethod
       async def subscribe(self, topic: str) -> AsyncGenerator[Any, None]:
           """Subscribe to topic and yield messages."""

       @abstractmethod
       async def create_queue(self, name: str) -> None:
           """Create a named queue."""

       @abstractmethod
       async def delete_queue(self, name: str) -> None:
           """Delete a named queue."""

       @abstractmethod
       async def get_queue_size(self, name: str) -> int:
           """Get number of messages in queue."""
   ```

1. **Add MODULE_METADATA** to each adapter:

   ```python
   from acb.adapters import AdapterMetadata, AdapterStatus, generate_adapter_id

   MODULE_METADATA = AdapterMetadata(
       module_id=generate_adapter_id(),
       name="Redis Queue",
       category="queue",
       provider="redis",
       version="1.0.0",
       acb_min_version="0.20.0",
       status=AdapterStatus.STABLE,
       capabilities=[
           AdapterCapability.ASYNC_OPERATIONS,
           AdapterCapability.CONNECTION_POOLING,
       ],
       required_packages=["redis>=4.0.0", "coredis>=4.24"],
   )
   ```

**Deliverables:**

- `acb/adapters/queue/_base.py` with QueueBackend interface
- Empty adapter module files with MODULE_METADATA stubs

### Phase 2: Migrate Queue Backends (3-4 hours)

**Tasks:**

1. **Move and refactor MemoryQueue**:

   - Source: `acb/queues/memory.py` → `acb/adapters/queue/memory.py`
   - Implement `QueueBackend` interface
   - Add MODULE_METADATA
   - Add comprehensive docstrings
   - Ensure thread-safe operations

1. **Move and refactor RedisQueue**:

   - Source: `acb/queues/redis.py` → `acb/adapters/queue/redis.py`
   - Implement `QueueBackend` interface
   - Add MODULE_METADATA
   - Add connection pooling support
   - Handle reconnection logic

1. **Move and refactor RabbitMQQueue**:

   - Source: `acb/queues/rabbitmq.py` → `acb/adapters/queue/rabbitmq.py`
   - Implement `QueueBackend` interface
   - Add MODULE_METADATA
   - Add connection management
   - Handle channel creation/cleanup

1. **Update adapter registry**:

   - Add static mappings in `acb/adapters/__init__.py`:
     ```python
     "queue.memory": ("acb.adapters.queue.memory", "Queue"),
     "queue.redis": ("acb.adapters.queue.redis", "Queue"),
     "queue.rabbitmq": ("acb.adapters.queue.rabbitmq", "Queue"),
     ```

**Deliverables:**

- Three working queue adapter modules
- Updated adapter registry
- Basic unit tests for each adapter

### Phase 3: Refactor Events Layer (2-3 hours)

**Tasks:**

1. **Update EventPublisher** (`acb/events/publisher.py`):

   ```python
   from acb.depends import depends
   from acb.adapters import import_adapter


   class EventPublisher:
       def __init__(self, settings: EventPublisherSettings | None = None):
           self._settings = settings or depends.get(EventPublisherSettings)
           Queue = import_adapter("queue")
           self._queue_backend = depends.get(Queue)

       async def publish(self, event: Event) -> None:
           await self._queue_backend.publish(
               topic=event.metadata.event_type, message=event.model_dump_json()
           )
   ```

1. **Update EventSubscriber** (`acb/events/subscriber.py`):

   ```python
   async def subscribe(self, event_type: str) -> AsyncGenerator[Event, None]:
       async for message in self._queue_backend.subscribe(event_type):
           yield Event.model_validate_json(message)
   ```

1. **Remove embedded backend logic**:

   - Delete `PublisherBackend` enum
   - Remove backend selection code
   - Simplify to use queue adapter

1. **Update tests**:

   - Refactor event tests to use queue adapter
   - Add integration tests with different backends

**Deliverables:**

- Refactored EventPublisher using queue adapter
- Refactored EventSubscriber using queue adapter
- Updated event system tests

### Phase 4: Refactor Tasks Layer (2-3 hours)

**Tasks:**

1. **Update TaskScheduler** (`acb/queues/scheduler.py`):

   ```python
   from acb.adapters import import_adapter


   class TaskScheduler:
       def __init__(self, settings: TaskSchedulerSettings | None = None):
           self._settings = settings or depends.get(TaskSchedulerSettings)
           Queue = import_adapter("queue")
           self._queue_backend = depends.get(Queue)
   ```

1. **Clean up old queue modules**:

   - Remove `acb/queues/memory.py`
   - Remove `acb/queues/redis.py`
   - Remove `acb/queues/rabbitmq.py`
   - Keep only orchestration files

1. **Update imports throughout codebase**:

   ```python
   # Old
   from acb.queues.redis import RedisTaskQueue

   # New
   from acb.adapters import import_adapter

   Queue = import_adapter("queue")
   ```

1. **Update tests**:

   - Refactor task queue tests
   - Add integration tests

**Deliverables:**

- Refactored task layer using queue adapter
- Removed duplicate queue implementations
- Updated test suite

### Phase 5: Configuration and Documentation (1-2 hours)

**Tasks:**

1. **Update settings structure**:

   ```yaml
   # settings/adapters.yml
   queue: redis  # Options: memory, redis, rabbitmq
   ```

1. **Update CLAUDE.md**:

   - Document new architecture
   - Update adapter lists
   - Add usage examples

1. **Update type error documentation**:

   - Reflect new file locations
   - Update error counts after refactor

1. **Create migration guide** (`docs/MIGRATION-0.20.0.md`):

   - Breaking changes summary
   - Import path updates
   - Configuration changes
   - Example migrations

**Deliverables:**

- Updated configuration files
- Migration guide
- Updated CLAUDE.md

### Phase 6: Testing and Validation (2-3 hours)

**Tasks:**

1. **Run comprehensive test suite**:

   ```bash
   python -m pytest tests/adapters/queue/
   python -m pytest tests/events/
   python -m pytest tests/queues/
   ```

1. **Type checking**:

   ```bash
   zuban check acb/adapters/queue/
   zuban check acb/events/
   zuban check acb/queues/
   ```

1. **Integration testing**:

   - Test events with different queue backends
   - Test tasks with different queue backends
   - Test switching backends via configuration

1. **Performance benchmarking**:

   - Compare before/after performance
   - Verify no regressions

**Deliverables:**

- All tests passing
- Type errors resolved or documented
- Performance benchmarks

## Impact Analysis

### Breaking Changes

1. **Import Paths**:

   ```python
   # Old
   from acb.queues.redis import RedisTaskQueue

   # New
   from acb.adapters import import_adapter

   Queue = import_adapter("queue")
   ```

1. **Configuration**:

   ```yaml
   # Old (implicit)
   task_queue: redis
   event_backend: redis

   # New (unified)
   queue: redis
   ```

1. **Direct Instantiation**:

   ```python
   # Old
   queue = RedisTaskQueue(settings)

   # New
   Queue = import_adapter("queue")
   queue = depends.get(Queue)
   ```

### Non-Breaking Changes

- Event and task layer APIs remain the same
- Backward compatibility via deprecation warnings for 1 version

## Migration Strategy

### For ACB Users

1. **Update imports**:

   - Replace direct queue imports with `import_adapter("queue")`
   - Update settings file to use `queue: <backend>`

1. **Test thoroughly**:

   - Events should work identically
   - Tasks should work identically
   - Only backend selection changes

### For ACB Contributors

1. **Queue adapter development**:

   - New backends go in `acb/adapters/queue/`
   - Implement `QueueBackend` interface
   - Add MODULE_METADATA

1. **Testing**:

   - Test against all backends
   - Use queue adapter fixture in tests

## Success Criteria

- ✅ Single queue adapter with memory, redis, rabbitmq backends
- ✅ Events layer uses queue adapter
- ✅ Tasks layer uses queue adapter
- ✅ All tests passing
- ✅ Type errors ≤ current count (549)
- ✅ No performance regressions
- ✅ Documentation updated
- ✅ Migration guide complete

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking existing code | HIGH | Deprecation warnings, migration guide, version bump to 0.20.0 |
| Performance regression | MEDIUM | Benchmark before/after, optimize if needed |
| Test failures | MEDIUM | Comprehensive test updates, staged rollout |
| Type errors increase | LOW | Fix types as part of refactor |

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Foundation | 2-3 hours | None |
| Phase 2: Migrate backends | 3-4 hours | Phase 1 |
| Phase 3: Refactor events | 2-3 hours | Phase 2 |
| Phase 4: Refactor tasks | 2-3 hours | Phase 2 |
| Phase 5: Documentation | 1-2 hours | Phases 3-4 |
| Phase 6: Testing | 2-3 hours | All phases |
| **Total** | **12-18 hours** | 2-3 days |

## Additional Refactoring Opportunities

### Core Module Analysis

Several root-level modules have adapter-like characteristics but exist outside `acb/adapters/`:

| Module | Current Location | Should Be Adapter? | Recommendation |
|--------|-----------------|-------------------|----------------|
| `logger.py` | acb/logger.py | ✅ Already is | Keep delegation pattern |
| `config.py` | acb/config.py | ❌ Core system | Keep as-is |
| `depends.py` | acb/depends.py | ❌ Core system | Keep as-is |
| `debug.py` | acb/debug.py | ⚠️ Maybe | Consider adapter |
| `console.py` | acb/console.py | ⚠️ Maybe | Consider adapter |
| `context.py` | acb/context.py | ❌ Core system | Keep as-is |

### Recommended Additional Refactoring

#### 1. Debug Adapter (Low Priority)

`acb/debug.py` currently wraps icecream but could be an adapter:

**Potential Structure:**

```
acb/adapters/debug/
├── _base.py       # DebugProtocol
├── icecream.py    # IcecreamDebugger (current)
└── pysnooper.py   # Alternative debugger
```

**Rationale:**

- Allows swapping debug backends (icecream, pysnooper, custom)
- Consistent with adapter pattern
- Low impact, nice-to-have

**Recommendation:** Defer to v0.21.0 or later (not critical)

#### 2. Console Adapter (Low Priority)

`acb/console.py` provides console utilities but could be more modular:

**Potential Structure:**

```
acb/adapters/console/
├── _base.py        # ConsoleProtocol
├── rich.py         # Rich console (current uses aioconsole)
└── simple.py       # Basic console
```

**Rationale:**

- Console rendering could have multiple backends
- Rich, prompt_toolkit, aioconsole are swappable
- Very low priority

**Recommendation:** Keep as-is for now (not worth complexity)

#### 3. Logger Pattern Review (Already Done ✅)

`acb/logger.py` already follows the correct pattern:

- Core module provides backward-compatible interface
- Delegates to `acb/adapters/logger/` (loguru, structlog)
- Clean separation of concerns

**Recommendation:** No changes needed, this is the reference pattern

### Broader Architectural Consistency

After queue adapter unification, ACB will have:

**Clearly Defined Adapters:**

- All in `acb/adapters/` directory
- Follow MODULE_METADATA pattern
- Configurable via `settings/adapters.yml`
- Examples: cache, storage, sql, queue, logger

**Clearly Defined Layers:**

- Orchestration logic that USES adapters
- Examples: events/, queues/, services/, workflows/
- Have `_base.py` for interfaces but not adapter modules

**Core Systems:**

- Framework infrastructure
- Not swappable
- Examples: config, depends, context

This creates a clean 3-tier architecture:

```
Core Systems (config, depends)
       ↓
Orchestration Layers (events, services, workflows)
       ↓
Adapters (queue, cache, storage, logger)
       ↓
External Systems (Redis, S3, etc.)
```

## Post-Implementation

### Future Enhancements

1. **Additional Queue Backends**:

   - Kafka adapter
   - NATS adapter
   - Amazon SQS adapter
   - Google Pub/Sub adapter

1. **Queue Advanced Features**:

   - Message priority
   - Dead letter queues
   - Message persistence
   - Queue monitoring
   - Message TTL

1. **Performance Optimization**:

   - Connection pooling
   - Message batching
   - Async streaming
   - Queue pre-warming

1. **Optional Debug/Console Adapters** (v0.21.0+):

   - Debug adapter for swappable debuggers
   - Console adapter for different rendering backends
   - Low priority, evaluate based on need

## Approval

This plan requires approval from:

- [ ] Architecture review
- [ ] Breaking change approval
- [ ] Performance team sign-off

## References

- ACB Unified Plan: `/Users/les/Projects/acb/ACB_UNIFIED_PLAN.md`
- Current adapter patterns: `/Users/les/Projects/acb/CLAUDE.md`
- Type error tracking: `/Users/les/Projects/acb/TYPE_ERROR_REMEDIATION_PLAN.md`
