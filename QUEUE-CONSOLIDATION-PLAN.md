# Queue System Consolidation Plan

## Problem Analysis

ACB currently has **two separate queue implementations** in different locations:

### 1. `acb/adapters/queue/` - Low-level Messaging Adapter (983 lines)
**Purpose**: Pub/sub messaging adapter for events system
**Interface**: `QueueBackend` (publish/subscribe, enqueue/dequeue messages)
**Files**:
- `_base.py` - QueueBackend interface
- `memory.py` - In-memory implementation
- `redis.py` - Redis implementation
- `rabbitmq.py` - RabbitMQ implementation

**Used By**:
- `acb/events/publisher.py` - Event publishing
- `acb/events/subscriber.py` - Event subscription

**Testing**: ❌ No tests in `tests/adapters/queue/`

### 2. `acb/queues/` - High-level Task Queue System (945 lines base + extras)
**Purpose**: Background job processing with scheduling and workers
**Interface**: `QueueBase` (task execution, handlers, scheduling)
**Files**:
- `_base.py` - QueueBase interface for tasks
- `memory.py` - In-memory task queue
- `redis.py` - Redis task queue
- `rabbitmq.py` - RabbitMQ task queue
- `apscheduler.py` - APScheduler integration ⭐ NEW
- `scheduler.py` - Task scheduling system
- `discovery.py` - Queue provider discovery
- `README.md` - Comprehensive documentation

**Features**:
- Task handlers and workers
- Priority-based execution
- Retry mechanisms
- Dead letter queues
- Cron scheduling
- Service discovery
- ACB Services integration

**Used By**:
- Direct imports for task processing
- APScheduler for advanced scheduling

**Testing**: ✅ Comprehensive tests in `tests/queues/`

### 3. Current Static Mappings (Confusing!)

```python
# acb/adapters/__init__.py lines 533-536
"queue.memory": ("acb.adapters.queue.memory", "Queue"),      # Old location
"queue.redis": ("acb.adapters.queue.redis", "Queue"),        # Old location
"queue.rabbitmq": ("acb.adapters.queue.rabbitmq", "Queue"),  # Old location
"queue.apscheduler": ("acb.queues.apscheduler", "Queue"),   # New location ⚠️
```

This inconsistency causes confusion about which system to use!

## Recommended Solution

**Consolidate into `acb/queues/` as the unified queue system.**

### Why `acb/queues/` Should Be Primary:

1. ✅ **More Complete**: Discovery, scheduling, APScheduler, workers
2. ✅ **Better Architecture**: Service integration, comprehensive metadata
3. ✅ **Has Tests**: Full test coverage with 3 test files
4. ✅ **Has Documentation**: README with examples and configuration
5. ✅ **Modern Patterns**: Follows ACB 0.19.1+ architecture
6. ✅ **Actively Developed**: Includes new APScheduler adapter

### Migration Strategy

The `adapters/queue` implementations can be merged into `queues/` since they're different backends for the same purpose. The Events system can use the queues system for pub/sub.

## Migration Plan

### Phase 1: Analysis & Verification (Current)

- [x] Identify all queue implementations
- [x] Map current usage patterns
- [x] Identify imports and dependencies
- [ ] Verify interface compatibility
- [ ] Check if events system can use QueueBase

### Phase 2: Merge Implementations

**Option A: Keep Separate Interfaces** (Recommended)
- Keep both `QueueBackend` (pub/sub) and `QueueBase` (tasks) interfaces
- Move `adapters/queue/` contents to `queues/backends/`
- Events system continues using pub/sub interface
- Task system uses task interface
- Both share the same backend implementations

**Option B: Unified Interface**
- Create single unified queue interface
- Merge QueueBackend and QueueBase capabilities
- Update events system to use unified interface
- More disruptive but cleaner long-term

### Phase 3: Update Adapter Registry

```python
# acb/adapters/__init__.py - After migration
"queue.memory": ("acb.queues.memory", "Queue"),
"queue.redis": ("acb.queues.redis", "Queue"),
"queue.rabbitmq": ("acb.queues.rabbitmq", "Queue"),
"queue.apscheduler": ("acb.queues.apscheduler", "Queue"),
```

### Phase 4: Update Imports

**Files to Update**:
1. `acb/events/publisher.py` - Change queue adapter import
2. `acb/events/subscriber.py` - Change queue adapter import
3. `acb/adapters/queue/__init__.py` - Deprecate or remove
4. Any tests that reference `acb.adapters.queue`

### Phase 5: Cleanup

- Remove `acb/adapters/queue/` directory
- Update all documentation
- Update CHANGELOG with migration notes
- Create MIGRATION guide if needed

## Files Requiring Changes

### To Move/Merge:
```
acb/adapters/queue/_base.py      → acb/queues/backends/_base.py (or merge)
acb/adapters/queue/memory.py     → Update existing acb/queues/memory.py
acb/adapters/queue/redis.py      → Update existing acb/queues/redis.py
acb/adapters/queue/rabbitmq.py   → Update existing acb/queues/rabbitmq.py
acb/adapters/queue/__init__.py   → Remove
```

### To Update:
```
acb/events/publisher.py          → Update queue adapter import
acb/events/subscriber.py         → Update queue adapter import
acb/adapters/__init__.py         → Update static mappings (lines 533-536)
tests/events/conftest.py         → Update queue imports if needed
```

### Documentation Updates:
```
README.md                        → Update queue adapter examples
CHANGELOG.md                     → Document consolidation
acb/queues/README.md             → Verify examples are correct
CLAUDE.md                        → Update queue adapter documentation
```

## Risks & Considerations

### Low Risk:
- ✅ Few external dependencies on `adapters/queue`
- ✅ Only events system uses it
- ✅ `queues/` already has better implementation
- ✅ No published API to break (internal refactor)

### Moderate Risk:
- ⚠️ Events system compatibility needs verification
- ⚠️ Ensure pub/sub patterns still work
- ⚠️ Static mapping changes affect adapter loading

### Mitigation:
1. Keep comprehensive test coverage
2. Run full test suite after each change
3. Create feature branch for migration
4. Test events pub/sub separately

## Testing Strategy

### Unit Tests:
- ✅ `tests/queues/` already exists (keep)
- ❌ `tests/adapters/queue/` doesn't exist (no regression risk)

### Integration Tests:
- Test events publisher/subscriber with new queue backend
- Verify pub/sub patterns work
- Test task execution and scheduling
- Verify APScheduler integration

### Performance Tests:
- Benchmark message throughput
- Test under load
- Compare before/after performance

## Timeline Estimate

- **Phase 1 (Analysis)**: 30 minutes ⏱️ (Current)
- **Phase 2 (Merge)**: 1-2 hours
- **Phase 3 (Registry)**: 15 minutes
- **Phase 4 (Imports)**: 30 minutes
- **Phase 5 (Cleanup)**: 30 minutes
- **Testing**: 1 hour

**Total**: ~3-4 hours

## Decision Required

**Question for User**: Which approach do you prefer?

### Option A: Separate Interfaces (Recommended)
- Keep `QueueBackend` for pub/sub (events)
- Keep `QueueBase` for tasks (background jobs)
- Move `adapters/queue` → `queues/backends/`
- Less disruptive, clearer separation of concerns

### Option B: Unified Interface
- Single queue interface for everything
- More refactoring required
- Simpler conceptually
- Cleaner long-term

### Option C: Keep Separate (Not Recommended)
- Leave as-is but document the difference
- Rename `adapters/queue` → `adapters/messaging`
- Keeps duplication but clarifies purpose

## Recommendation

**Proceed with Option A** (Separate Interfaces):

1. Rename `acb/adapters/queue/` → `acb/queues/backends/` (or similar)
2. Keep both `QueueBackend` and `QueueBase` interfaces
3. Update adapter registry to point to `acb.queues.*`
4. Events system continues using pub/sub interface
5. Task system uses task interface
6. Share backend implementations

This provides the best balance of:
- ✅ Consolidation (single location)
- ✅ Clear separation (different interfaces)
- ✅ Minimal disruption (events system unchanged)
- ✅ Better architecture (everything in queues/)

## Next Steps

1. Get user confirmation on approach
2. Create feature branch `consolidate-queue-systems`
3. Begin Phase 2 implementation
4. Test thoroughly
5. Document changes
6. Merge to main
