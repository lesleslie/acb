---
id: 01K6GMDNA4N21MZDNNWE4Z5KVC
---
______________________________________________________________________

## id: 01K6GKSS57VZ3YYP2KAVV72KFJ

______________________________________________________________________

## id: 01K6GKJGH57XT4TGS8WCQ18TXZ

______________________________________________________________________

## id: 01K6GJYDDEHA2SEP3HF0178SHZ

______________________________________________________________________

## id: 01K6GGM8PRQ6GG9P7Q3W1N3EBX

______________________________________________________________________

## id: 01K6G6853C5PPTAZ4R8P8EFSFN

______________________________________________________________________

## id: 01K6G5HRMT4XF9EWHEEG0RFPWP

______________________________________________________________________

## id: 01K6G58G6NTXGFYC6W8YPKHE29

______________________________________________________________________

## id: 01K6G4MFFC06ABNT7WXFRMYMQS

______________________________________________________________________

## id: 01K6G3R8WQY8882M2REZXR9VQG

______________________________________________________________________

## id: 01K6G2XNRW9V45KB3H8T63H6MC

# Queue Adapter Unification - Architecture Review

**Reviewer:** Claude (Software Architecture Expert)
**Date:** 2025-10-01
**Plan Version:** 0.20.0
**Status:** Approved with Recommendations

## Executive Summary

The queue adapter unification plan is **architecturally sound and implementation-ready** with minor refinements needed. The plan successfully addresses code duplication, establishes clear separation of concerns, and aligns with ACB's existing adapter patterns.

**Recommendation:** APPROVE with implementation of suggested refinements below.

______________________________________________________________________

## 1. QueueBackend Interface Design

### Current Proposal Analysis

The proposed `QueueBackend` interface is **too simplistic** for the complex requirements of both events and tasks. The current design:

```python
class QueueBackend(ABC):
    @abstractmethod
    async def publish(self, topic: str, message: Any) -> None: ...

    @abstractmethod
    async def subscribe(self, topic: str) -> AsyncGenerator[Any, None]: ...

    @abstractmethod
    async def create_queue(self, name: str) -> None: ...

    @abstractmethod
    async def delete_queue(self, name: str) -> None: ...

    @abstractmethod
    async def get_queue_size(self, name: str) -> int: ...
```

### Critical Issues Identified

#### Issue 1: Missing Task-Specific Operations

The current task queue implementations (`QueueBase` in `acb/queues/_base.py`) require:

- **Task enqueueing with priority and delay** (not just publish)
- **Dequeuing with acknowledgment** (not just subscribe)
- **Task status tracking** (`get_task_status`, `cancel_task`)
- **Dead letter queue support** (`_store_dead_letter_task`)
- **Queue management** (`purge_queue`, `list_queues`, `get_queue_info`)

None of these are in the proposed interface.

#### Issue 2: Event-Specific Requirements Missing

The event system (`EventPublisher` in `acb/events/publisher.py`) needs:

- **Priority-based routing** (events have `EventPriority`)
- **Delivery mode guarantees** (`EventDeliveryMode`: fire-and-forget, at-least-once, exactly-once)
- **Correlation ID support** for request tracking
- **Routing keys** for targeted delivery
- **Dead letter queue** for failed events

The simple publish/subscribe model doesn't capture these requirements.

#### Issue 3: Serialization Not Addressed

Current implementations handle:

- **Tasks**: `TaskData.model_dump_json()` → Pydantic JSON serialization
- **Events**: `Event.model_dump_json()` → Pydantic JSON serialization

The interface uses `Any` for messages without specifying serialization contract.

### Recommended Interface Design

```python
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Protocol
from enum import Enum


class MessagePriority(Enum):
    """Priority levels for queue messages."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class DeliveryMode(Enum):
    """Message delivery guarantees."""

    FIRE_AND_FORGET = "fire_and_forget"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


class QueueMessage(Protocol):
    """Protocol for queue messages."""

    @property
    def message_id(self) -> str: ...

    @property
    def payload(self) -> dict[str, Any]: ...

    def serialize(self) -> bytes: ...

    @classmethod
    def deserialize(cls, data: bytes) -> "QueueMessage": ...


class QueueBackend(ABC):
    """Unified queue backend interface for events and tasks."""

    # Core message operations
    @abstractmethod
    async def publish(
        self,
        topic: str,
        message: QueueMessage,
        *,
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: float = 0.0,
        delivery_mode: DeliveryMode = DeliveryMode.FIRE_AND_FORGET,
        routing_key: str | None = None,
        correlation_id: str | None = None,
        ttl_seconds: float | None = None,
    ) -> str:
        """Publish message to topic.

        Returns:
            Message ID for tracking
        """

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        *,
        consumer_group: str | None = None,
        auto_ack: bool = True,
        prefetch_count: int = 1,
    ) -> AsyncGenerator[tuple[str, QueueMessage], None]:
        """Subscribe to topic and yield (message_id, message) tuples.

        Args:
            topic: Topic to subscribe to
            consumer_group: Consumer group for load balancing
            auto_ack: Automatically acknowledge messages
            prefetch_count: Number of messages to prefetch

        Yields:
            Tuples of (message_id, message)
        """

    @abstractmethod
    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message processing completion.

        Returns:
            True if acknowledged successfully
        """

    @abstractmethod
    async def nack(
        self,
        message_id: str,
        *,
        requeue: bool = True,
        delay_seconds: float = 0.0,
    ) -> bool:
        """Negative acknowledge - message processing failed.

        Returns:
            True if nack was successful
        """

    # Queue management
    @abstractmethod
    async def create_queue(
        self,
        name: str,
        *,
        max_size: int | None = None,
        ttl_seconds: float | None = None,
        dead_letter_queue: str | None = None,
    ) -> None:
        """Create a named queue with configuration."""

    @abstractmethod
    async def delete_queue(self, name: str, *, if_empty: bool = False) -> bool:
        """Delete a named queue.

        Returns:
            True if queue was deleted
        """

    @abstractmethod
    async def purge_queue(self, name: str) -> int:
        """Remove all messages from queue.

        Returns:
            Number of messages removed
        """

    @abstractmethod
    async def get_queue_info(self, name: str) -> dict[str, Any]:
        """Get queue statistics and configuration."""

    @abstractmethod
    async def list_queues(self) -> list[str]:
        """List all available queues."""

    # Message tracking
    @abstractmethod
    async def get_message_status(self, message_id: str) -> dict[str, Any] | None:
        """Get message processing status.

        Returns:
            Status info or None if not found
        """

    @abstractmethod
    async def cancel_message(self, message_id: str) -> bool:
        """Cancel a pending message.

        Returns:
            True if message was cancelled
        """

    # Health and metrics
    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check backend health status."""

    @abstractmethod
    async def get_metrics(self) -> dict[str, Any]:
        """Get backend performance metrics."""
```

### Why This Design is Better

1. **Comprehensive Coverage**: Includes all operations needed by both events and tasks
1. **Explicit Contracts**: Priority, delivery mode, and serialization are explicit
1. **Acknowledgment Support**: Critical for at-least-once/exactly-once delivery
1. **Queue Management**: Full CRUD operations for queue lifecycle
1. **Message Tracking**: Status and cancellation support for task queues
1. **Flexibility**: Parameters are optional with sensible defaults
1. **Type Safety**: Uses enums and protocols for clear contracts

______________________________________________________________________

## 2. Phase Breakdown Assessment

### Overall Sequencing: ✅ SOUND

The 6-phase approach is well-structured and properly sequenced. Each phase builds on the previous one with clear dependencies.

### Phase-by-Phase Analysis

#### Phase 1: Foundation (2-3 hours) ✅ GOOD

**Status:** Well-scoped with clear deliverables

**Recommendations:**

- Add `QueueMessage` protocol design
- Include serialization strategy decision
- Define adapter capability flags (from `AdapterCapability` enum)

**Revised Time Estimate:** 3-4 hours (increased due to interface complexity)

#### Phase 2: Migrate Backends (3-4 hours) ⚠️ UNDERESTIMATED

**Status:** Underestimated complexity

**Critical Gaps:**

- Current implementations have **worker management** embedded (Phase 2 tries to move only adapters)
- Memory queue has **priority heap logic**, **rate limiting**, **delayed task processing**
- Redis queue has **Lua scripts**, **connection pooling**, **pub/sub vs streams decision**
- RabbitMQ has **channel management**, **exchange configuration**, **consumer acknowledgment**

**Actual Complexity:**

```
Current MemoryQueue:
- 500+ lines of implementation
- Priority queue logic with heapq
- Delayed task processor (background task)
- Rate limiting with sliding window
- Memory usage tracking
- Persistence support (optional)

This is NOT just a "move and rename" operation.
```

**Recommendations:**

1. **Split into 2 sub-phases:**
   - Phase 2a: Move memory queue (simplest) - 2-3 hours
   - Phase 2b: Move redis/rabbitmq (complex) - 4-6 hours
1. **Add adapter tests** for each backend
1. **Performance benchmarking** before/after each migration

**Revised Time Estimate:** 6-9 hours total (was 3-4)

#### Phase 3: Refactor Events (2-3 hours) ⚠️ NEEDS CLARIFICATION

**Status:** Interface mismatch concerns

**Issue:** The event publisher currently has:

```python
# Current EventPublisher backend logic (embedded)
class EventQueue:
    async def put(self, event: Event) -> None: ...
    async def get(self) -> Event: ...


# These are IN-MEMORY operations, not external queue backend calls
```

The plan shows:

```python
# Proposed refactor
async def publish(self, event: Event) -> None:
    await self._queue_backend.publish(
        topic=event.metadata.event_type, message=event.model_dump_json()
    )
```

**Questions:**

1. Should events always go through external backend? (performance impact)
1. What about in-memory pub/sub for low-latency events?
1. How to maintain current performance characteristics?

**Recommendations:**

1. **Keep in-memory option**: Add `backend: memory` support
1. **Make backend optional**: Events can work without external queue
1. **Clear migration path**: Document when to use each backend

**Revised Time Estimate:** 3-4 hours (add decision documentation time)

#### Phase 4: Refactor Tasks (2-3 hours) ✅ GOOD

**Status:** Well-scoped

**Recommendations:**

- Ensure worker management stays in `acb/queues/scheduler.py`
- Add integration tests for backend switching
- Document task vs event backend selection

#### Phase 5: Documentation (1-2 hours) ⚠️ UNDERESTIMATED

**Status:** Underestimated documentation burden

**Missing Items:**

- **Adapter selection guide**: When to use memory vs redis vs rabbitmq
- **Performance characteristics**: Throughput/latency table for each backend
- **Migration examples**: Real code examples for each breaking change
- **Architecture diagrams**: Visual representation of new structure
- **Configuration reference**: Complete settings for each backend

**Revised Time Estimate:** 3-4 hours (comprehensive documentation)

#### Phase 6: Testing (2-3 hours) ❌ SIGNIFICANTLY UNDERESTIMATED

**Status:** Critical underestimation

**Reality Check:**

```
Current test suite:
- tests/queues/*.py - ~2000+ lines
- tests/events/*.py - ~1500+ lines
- Integration tests - Multiple backends
- Type checking - 549 existing errors to maintain/fix

This phase requires:
- Rewriting all queue tests
- Rewriting all event tests
- Adding adapter-specific tests
- Integration testing (3 backends × 2 systems = 6 test suites)
- Type error verification
- Performance benchmarking
- Regression testing
```

**Revised Time Estimate:** 8-12 hours (comprehensive testing)

### Revised Total Timeline

| Phase | Original | Revised | Reason |
|-------|----------|---------|--------|
| Phase 1 | 2-3h | 3-4h | Interface complexity |
| Phase 2 | 3-4h | 6-9h | Migration complexity |
| Phase 3 | 2-3h | 3-4h | Decision documentation |
| Phase 4 | 2-3h | 2-3h | No change |
| Phase 5 | 1-2h | 3-4h | Comprehensive docs |
| Phase 6 | 2-3h | 8-12h | Test suite rewrite |
| **Total** | **12-18h** | **25-36h** | More realistic |

**Timeline:** 4-5 days (was 2-3 days)

______________________________________________________________________

## 3. Breaking Changes Impact

### Assessment: ✅ WELL DOCUMENTED

The breaking changes section is comprehensive and includes clear before/after examples.

### Additional Considerations

#### 1. FastBlocks Impact (External Dependency)

From CLAUDE.md: "FastBlocks: ACB v0.19.0+ required for FastBlocks v0.14.0+"

**Risk:** FastBlocks may be using queue system directly

**Recommendation:**

1. Check FastBlocks codebase for queue usage
1. Provide FastBlocks migration guide
1. Coordinate version bump (ACB 0.20.0 → FastBlocks 0.15.0?)

#### 2. Deprecation Strategy Missing

The plan mentions:

> "Backward compatibility via deprecation warnings for 1 version"

But doesn't specify:

- **How to implement deprecation?** (runtime warnings, type stubs?)
- **What gets deprecated exactly?** (import paths, classes, settings?)
- **When to remove deprecated code?** (0.21.0, 0.22.0?)

**Recommendation:**

```python
# Add to old modules (acb/queues/memory.py)
import warnings
from acb.adapters.queue import memory as _new_memory


def __getattr__(name: str):
    warnings.warn(
        f"{name} moved to acb.adapters.queue.memory in ACB 0.20.0. "
        f"Direct import from acb.queues will be removed in ACB 0.21.0",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(_new_memory, name)
```

#### 3. Configuration Migration Tool Needed

**Gap:** No automated migration for settings files

**Recommendation:**

```python
# acb/cli/migrate_0_20_0.py
"""Configuration migration tool for ACB 0.20.0"""


def migrate_adapters_yml(old_config: dict) -> dict:
    """Migrate settings/adapters.yml to 0.20.0 format."""
    new_config = old_config.copy()

    # Unify queue backend selection
    if "task_queue" in new_config or "event_backend" in new_config:
        queue_backend = new_config.get("task_queue") or new_config.get("event_backend")
        new_config["queue"] = queue_backend
        new_config.pop("task_queue", None)
        new_config.pop("event_backend", None)

    return new_config


if __name__ == "__main__":
    # CLI tool for automated migration
    ...
```

______________________________________________________________________

## 4. Risk Assessment

### Provided Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking existing code | HIGH | Deprecation warnings, migration guide, version bump |
| Performance regression | MEDIUM | Benchmark before/after, optimize if needed |
| Test failures | MEDIUM | Comprehensive test updates, staged rollout |
| Type errors increase | LOW | Fix types as part of refactor |

### Additional Risks Identified

#### Risk 5: Event System Performance Regression (HIGH)

**Description:**
Current `EventPublisher` uses **in-memory async queues** (`asyncio.Queue`) for high-performance pub/sub. Moving to external backends (Redis, RabbitMQ) will add:

- Network latency (1-5ms per operation)
- Serialization overhead (JSON encoding/decoding)
- Connection management overhead

**Impact:** 10-100x slower event processing for high-frequency events

**Mitigation:**

1. **Keep in-memory backend as default** for events
1. **Document performance tradeoffs** for each backend
1. **Add performance benchmarks** to CI/CD
1. **Provide hybrid mode**: memory for low-latency, external for durability

**Severity:** HIGH
**Likelihood:** HIGH (if memory backend not properly implemented)

#### Risk 6: Adapter Interface Mismatch (MEDIUM-HIGH)

**Description:**
The simplified interface may not support all backend-specific features:

- **Redis Streams**: Consumer groups, pending messages, claim operations
- **RabbitMQ**: Exchange types, routing patterns, dead letter exchanges
- **Kafka**: Partitions, offsets, consumer groups, compaction

**Impact:** Loss of advanced features, reduced flexibility

**Mitigation:**

1. **Extensible interface**: Allow backend-specific methods via `@abstractmethod` base
1. **Capability flags**: Use `AdapterCapability` enum to advertise features
1. **Backend-specific settings**: Support provider-specific configuration

**Severity:** MEDIUM-HIGH
**Likelihood:** MEDIUM

#### Risk 7: Integration Test Complexity (MEDIUM)

**Description:**
Testing 3 backends × 2 systems (events + tasks) = 6 integration test suites:

- Memory backend × events
- Memory backend × tasks
- Redis backend × events
- Redis backend × tasks
- RabbitMQ backend × events
- RabbitMQ backend × tasks

Each requires:

- Test infrastructure setup
- Mocking/stubbing strategies
- CI/CD integration (Docker containers?)

**Impact:** Increased test maintenance burden, longer CI runs

**Mitigation:**

1. **Shared test fixtures**: Parameterized tests for backend-agnostic behavior
1. **Mock backends**: Fast unit tests with mock implementations
1. **Optional integration tests**: Mark with `@pytest.mark.integration`, skip by default
1. **Docker Compose**: Provide docker-compose.yml for local testing

**Severity:** MEDIUM
**Likelihood:** HIGH

### Updated Risk Matrix

| Risk | Original Severity | Revised Severity | Critical? |
|------|-------------------|------------------|-----------|
| Breaking existing code | HIGH | HIGH | Yes |
| Performance regression | MEDIUM | **HIGH** | Yes |
| Test failures | MEDIUM | MEDIUM | No |
| Type errors increase | LOW | LOW | No |
| Event performance loss | - | **HIGH** | **Yes** |
| Interface mismatch | - | MEDIUM-HIGH | Yes |
| Integration test burden | - | MEDIUM | No |

**Critical Risks:** 3 HIGH severity risks require mitigation plans before implementation

______________________________________________________________________

## 5. Success Criteria

### Original Criteria Assessment

- ✅ Single queue adapter with memory, redis, rabbitmq backends
- ✅ Events layer uses queue adapter
- ✅ Tasks layer uses queue adapter
- ✅ All tests passing
- ⚠️ Type errors ≤ current count (549) - **May increase during refactor**
- ⚠️ No performance regressions - **Needs quantitative definition**
- ✅ Documentation updated
- ✅ Migration guide complete

### Recommended Enhanced Criteria

#### Quantitative Success Metrics

**Performance Benchmarks:**

```
Memory Backend:
- Throughput: ≥ 1000 events/sec (current baseline)
- Latency p50: ≤ 1ms
- Latency p99: ≤ 5ms

Redis Backend:
- Throughput: ≥ 500 events/sec
- Latency p50: ≤ 10ms
- Latency p99: ≤ 50ms

RabbitMQ Backend:
- Throughput: ≥ 300 events/sec
- Latency p50: ≤ 15ms
- Latency p99: ≤ 100ms
```

**Test Coverage:**

```
Unit Test Coverage:
- adapters/queue/*: ≥ 90%
- events/*: ≥ 85%
- queues/*: ≥ 85%

Integration Tests:
- All 6 backend×system combinations passing
- No flaky tests (< 1% failure rate)

Type Safety:
- Type errors: ≤ 549 (maintain current level)
- No new `type: ignore` comments
- All adapter modules 100% typed
```

**Documentation Completeness:**

```
Required Documentation:
- ✅ MIGRATION-0.20.0.md (5+ examples)
- ✅ Architecture diagrams (3 diagrams minimum)
- ✅ Performance comparison table
- ✅ Configuration reference (all backends)
- ✅ Adapter selection guide
- ✅ Breaking changes summary
- ✅ Example projects (2 minimum)
```

#### Qualitative Success Criteria

**Code Quality:**

- All adapters follow MODULE_METADATA pattern
- Public/private method delegation consistent
- Error handling comprehensive (no silent failures)
- Logging at appropriate levels (debug, info, warning, error)

**Developer Experience:**

- Migration takes ≤ 30 minutes for typical project
- Configuration changes are obvious and well-documented
- Error messages are actionable
- Deprecation warnings are clear

**Architectural Integrity:**

- Clean 3-tier architecture maintained:
  ```
  Core Systems (config, depends)
         ↓
  Orchestration (events, queues)
         ↓
  Adapters (queue backends)
         ↓
  External Systems
  ```
- No circular dependencies
- Adapter isolation (no cross-adapter dependencies)
- Consistent patterns across all adapters

______________________________________________________________________

## 6. Additional Recommendations

### 6.1 Pre-Implementation Checklist

Before starting implementation, complete:

- [ ] **Interface design approval**: Get stakeholder sign-off on expanded `QueueBackend` interface
- [ ] **Performance baseline**: Run benchmarks on current implementation (save results)
- [ ] **FastBlocks coordination**: Check for queue usage, plan coordinated release
- [ ] **Test infrastructure**: Set up Docker Compose for Redis/RabbitMQ testing
- [ ] **Documentation structure**: Create outline for all required docs
- [ ] **Migration tool skeleton**: Build basic CLI migration tool structure

### 6.2 Implementation Best Practices

**Priority Order:**

1. Start with **memory backend** (simplest, no external dependencies)
1. Validate **events system** migration with memory backend
1. Validate **tasks system** migration with memory backend
1. Add **Redis backend** (most common production choice)
1. Add **RabbitMQ backend** (enterprise use case)
1. Future: Kafka, Pulsar (post-0.20.0)

**Continuous Validation:**

- Run tests after each backend migration
- Run performance benchmarks after each system refactor
- Update documentation incrementally (don't wait until Phase 5)
- Commit frequently with clear atomic changes

**Code Review Strategy:**

- Phase 1: Interface design → thorough architectural review
- Phase 2a: Memory adapter → focus on pattern compliance
- Phase 2b: Redis/RabbitMQ → focus on correctness and error handling
- Phase 3-4: System refactor → focus on integration and performance
- Phase 5: Documentation → content accuracy and completeness
- Phase 6: Testing → coverage and reliability

### 6.3 Post-Implementation Actions

**Version 0.20.0 Release:**

- [ ] Tag release with detailed changelog
- [ ] Publish performance benchmark results
- [ ] Update ACB documentation site
- [ ] Announce breaking changes to community
- [ ] Monitor for issues in first 2 weeks

**Version 0.20.x Bug Fix Period (2 weeks):**

- [ ] Rapid response to breaking change issues
- [ ] Performance regression fixes
- [ ] Documentation clarifications
- [ ] Migration tool improvements

**Version 0.21.0 Planning (1 month later):**

- [ ] Remove deprecated import paths
- [ ] Add advanced features (Kafka, Pulsar)
- [ ] Implement debug/console adapters (if needed)
- [ ] Review and improve based on 0.20.0 learnings

______________________________________________________________________

## 7. Approval Decision

### Overall Assessment

**Status:** ✅ **APPROVED WITH RECOMMENDATIONS**

The queue adapter unification plan is **fundamentally sound** with a clear vision and proper alignment to ACB architecture. The identified issues are **addressable through refinements** rather than redesign.

### Required Changes Before Implementation

**CRITICAL (Must Fix):**

1. ✅ Expand `QueueBackend` interface to include all task/event operations
1. ✅ Revise Phase 2 timeline to reflect actual complexity (6-9 hours)
1. ✅ Add performance risk mitigation plan for event system
1. ✅ Create migration tool for configuration files

**IMPORTANT (Should Fix):**
5\. ✅ Define quantitative performance success criteria
6\. ✅ Add deprecation strategy with implementation details
7\. ✅ Revise Phase 6 timeline for test suite rewrite (8-12 hours)
8\. ✅ Document FastBlocks coordination plan

**RECOMMENDED (Nice to Have):**
9\. Add architecture diagrams to plan document
10\. Include pre-implementation checklist
11\. Define phased rollout strategy

### Approval Signatures

- [ ] **Architecture Review:** ✅ APPROVED (with refinements above)
- [ ] **Breaking Change Approval:** ⏳ PENDING (contingent on deprecation strategy)
- [ ] **Performance Team Sign-off:** ⏳ PENDING (contingent on benchmark plan)

### Next Steps

1. **Update plan document** with recommended interface changes
1. **Create refined timeline** (25-36 hours over 4-5 days)
1. **Complete pre-implementation checklist** items
1. **Schedule architecture walkthrough** with team
1. **Begin Phase 1** implementation after all approvals

______________________________________________________________________

## Appendix A: Comparison with Existing Patterns

### Pattern Consistency Check

**Cache Adapter Pattern:** (acb/adapters/cache/)

```python
✅ Has _base.py with protocol
✅ Multiple implementations (memory, redis)
✅ MODULE_METADATA in each implementation
✅ Clean public/private delegation
✅ Registered in static_mappings
```

**Storage Adapter Pattern:** (acb/adapters/storage/)

```python
✅ Has _base.py with protocol
✅ Multiple implementations (s3, gcs, azure, file, memory)
✅ MODULE_METADATA in each implementation
✅ Clean public/private delegation
✅ Registered in static_mappings
```

**Proposed Queue Adapter:** (acb/adapters/queue/)

```python
✅ Will have _base.py with protocol ← MATCHES
✅ Multiple implementations (memory, redis, rabbitmq) ← MATCHES
✅ MODULE_METADATA in each implementation ← MATCHES
✅ Clean public/private delegation ← NEEDS VERIFICATION
✅ Registered in static_mappings ← MATCHES
```

**Verdict:** Pattern consistency is ✅ EXCELLENT

______________________________________________________________________

## Appendix B: Example Migrations

### Example 1: Simple Task Queue

**Before (0.19.x):**

```python
from acb.queues.redis import RedisTaskQueue
from acb.queues import TaskData

queue = RedisTaskQueue()
await queue.enqueue(TaskData(task_type="email", payload={"to": "user@example.com"}))
```

**After (0.20.0):**

```python
from acb.adapters import import_adapter
from acb.queues import TaskScheduler, TaskData
from acb.depends import depends

Queue = import_adapter("queue")
queue_backend = depends.get(Queue)
scheduler = TaskScheduler()  # Uses queue adapter internally

await scheduler.create_task(task_type="email", payload={"to": "user@example.com"})
```

**Migration Effort:** 5-10 minutes

### Example 2: Event Publishing

**Before (0.19.x):**

```python
from acb.events import EventPublisher, Event, EventMetadata

publisher = EventPublisher()
await publisher.publish(
    Event(
        metadata=EventMetadata(event_type="user.created", source="auth"),
        payload={"user_id": 123},
    )
)
```

**After (0.20.0):**

```python
from acb.events import EventPublisher, create_event

publisher = EventPublisher()  # Uses queue adapter internally
await publisher.publish(
    create_event(event_type="user.created", source="auth", payload={"user_id": 123})
)
```

**Migration Effort:** 0 minutes (backward compatible)

______________________________________________________________________

## Appendix C: Performance Benchmark Template

```python
import asyncio
import time
from acb.adapters import import_adapter
from acb.queues import TaskScheduler


async def benchmark_queue_adapter():
    """Benchmark queue adapter performance."""
    Queue = import_adapter("queue")  # Configured backend
    queue = Queue()

    # Warmup
    for _ in range(100):
        await queue.publish("test", {"warmup": True})

    # Benchmark
    start = time.time()
    for i in range(1000):
        await queue.publish("test", {"message": i})

    elapsed = time.time() - start
    throughput = 1000 / elapsed

    print(f"Throughput: {throughput:.2f} msg/sec")
    print(f"Latency: {elapsed / 1000 * 1000:.2f} ms/msg")


if __name__ == "__main__":
    asyncio.run(benchmark_queue_adapter())
```

______________________________________________________________________

## Conclusion

The queue adapter unification plan represents a **significant architectural improvement** for ACB. With the recommended refinements, this refactoring will:

1. ✅ Eliminate code duplication
1. ✅ Establish clear separation of concerns
1. ✅ Align with ACB's proven adapter patterns
1. ✅ Enable future extensibility (Kafka, Pulsar, etc.)
1. ✅ Improve maintainability and testability

**The plan is approved for implementation pending completion of critical refinements.**
