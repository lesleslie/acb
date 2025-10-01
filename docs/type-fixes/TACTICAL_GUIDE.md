---
id: 01K6GMDT8KQP7XHV11038GJJ2M
---
______________________________________________________________________

## id: 01K6GKSZD8F4CN6PTSN9D3F2EH

______________________________________________________________________

## id: 01K6GKJR0800A2YAJZEAG0GTYJ

______________________________________________________________________

## id: 01K6GJYJETEG1T90MXKKSSYCKY

______________________________________________________________________

## id: 01K6GGMCMVC76MTTXGBB0ZJZ2C

______________________________________________________________________

## id: 01K6G689NA785W6425Z9DNW57R

______________________________________________________________________

## id: 01K6G5HVAQ28M61PQB27J4MN5X

______________________________________________________________________

## id: 01K6G58KSS5CNSCGPKCVGBCGQ8

______________________________________________________________________

## id: 01K6G4MKC1SWJDQDA2ZTPR7FM2

______________________________________________________________________

## id: 01K6FYT2H2M3B640960ZVAJQT8

# Type Error Tactical Guide - Agent Instructions

**For**: python-pro and refactoring-specialist agents
**Goal**: Execute remediation plan efficiently and safely
**Status**: Ready for Sprint 1 execution

## Quick Start for Agents

### Verification Commands

```bash
# Before starting work
zuban check acb/ 2>&1 | tail -1  # Get current error count

# Check specific file before/after changes
zuban check acb/testing/fixtures.py 2>&1 | tail -1

# Run tests to ensure no breakage
python -m pytest -xvs

# Final verification (MANDATORY)
python -m crackerjack -t --ai-fix
```

### Sprint 1 Tasks (Immediate Execution)

#### Task 1.1: Fix testing/fixtures.py (32 → ~5 errors)

**Agent**: refactoring-specialist
**Estimated Time**: 45 minutes
**Risk Level**: LOW - Testing code only

**Specific Fixes**:

1. **Add missing import** (line 290):

```python
# Add to top of file
from typing import Any
```

2. **Fix Generator return types** (8 locations):

```python
# Lines 155, 170, 314, 327, 345 - sync generators
from collections.abc import Generator


@pytest.fixture
def fixture_name() -> Generator[ReturnType, None, None]:
    yield value


# Lines 192, 223, 250, 285 - async generators
from collections.abc import AsyncGenerator


@pytest.fixture
async def async_fixture() -> AsyncGenerator[ReturnType, None]:
    yield value
```

3. **Fix "No return value expected" errors** (12 locations):

```python
# These are fixture functions that yield
# Change return type from -> None to -> Generator[Type, None, None]

# Example for lines 188, 281, 334, 352, 370, 372, 386, 410, 415, 422, 432
@pytest.fixture
def fixture() -> Generator[MockType, None, None]:  # NOT -> None
    mock = Mock()
    yield mock
```

4. **Fix private attribute access** (7 locations):

```python
# Lines 47, 200-202, 231-232, 317-318, 323
# Use getattr with type: ignore or cast

# Option 1: Type ignore (quick)
config._config_data  # type: ignore[attr-defined]

# Option 2: Hasattr check (safer)
if hasattr(config, "_config_data"):
    data = config._config_data
```

**Expected Result**: 32 → 5 errors

#### Task 1.2: Fix testing/performance.py (30 → ~8 errors)

**Agent**: refactoring-specialist
**Estimated Time**: 45 minutes
**Risk Level**: LOW - Testing utilities

**Specific Fixes**:

1. **Add function type annotations** (15 no-untyped-def errors):

```python
# Lines 71, 78, 96, 209 and others
from collections.abc import Callable
from typing import Any


# Before
def decorator(func): ...


# After
def decorator(func: Callable[..., Any]) -> Callable[..., Any]: ...
```

2. **Add generic type parameters** (10 type-arg errors):

```python
# Lines 98, 207, 211, 292, 325
from typing import Any

# Before
metrics: dict = {}
Callable = ...

# After
metrics: dict[str, Any] = {}
Callable[..., Any] = ...
```

3. **Fix index operation** (line 311):

```python
# Before
result = timing_data[0]  # timing_data is float

# After
if isinstance(timing_data, (list, tuple)):
    result = timing_data[0]
else:
    result = timing_data
```

**Expected Result**: 30 → 8 errors

#### Task 1.3: Batch Fix no-any-return (52 → 0 errors)

**Agent**: refactoring-specialist
**Estimated Time**: 1 hour
**Risk Level**: LOW - Pure metadata

**Strategy**: Add return type hints across all files

**Pattern**:

```python
# Before
async def get_value(self):
    return await self._client.get()


# After
async def get_value(self) -> str:
    return await self._client.get()


# For unknown types, use Any temporarily
from typing import Any


async def complex_operation(self) -> Any:
    return await self._process()
```

**Target Files** (grep for specific functions):

```bash
# Get list of functions with no-any-return
zuban check acb/ 2>&1 | grep "no-any-return" | cut -d: -f1-2 | sort -u
```

**Common Return Types**:

- Cache operations: `bool`, `str | None`, `Any`
- Repository operations: `ModelType | None`, `list[ModelType]`, `int`
- Queue operations: `TaskResult`, `list[Task[Any]]`, `bool`
- Settings operations: `dict[str, Any]`, `Any`

**Expected Result**: 52 → 0 errors

#### Task 1.4: Batch Fix type-arg (42 → 0 errors)

**Agent**: refactoring-specialist
**Estimated Time**: 30 minutes
**Risk Level**: LOW - Clarifying existing intent

**Pattern**:

```python
from typing import Any

# Common fixes:
tasks: list = []  →  tasks: list[Task[Any]] = []
data: dict = {}  →  data: dict[str, Any] = {}
results: set = set()  →  results: set[str] = set()
queue: deque = deque()  →  queue: deque[Task[Any]] = deque()
client: Redis = ...  →  client: Redis[bytes] = ...
```

**Target Files**:

```bash
zuban check acb/ 2>&1 | grep "type-arg" | cut -d: -f1 | sort -u
```

**Expected Result**: 42 → 0 errors

### Sprint 2 Tasks (Settings Refactor)

#### Task 2.1: Create RabbitMQQueueSettings

**Agent**: python-pro
**File**: `acb/queues/rabbitmq.py`
**Estimated Time**: 1 hour
**Risk Level**: MEDIUM - Affects queue configuration

**Implementation**:

```python
# Add to acb/queues/rabbitmq.py
from pydantic import BaseModel, Field
from typing import Any


class RabbitMQQueueSettings(QueueSettings):
    """RabbitMQ-specific queue configuration."""

    # Connection
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672/",
        description="RabbitMQ connection URL",
    )

    # Delayed message plugin
    use_delayed_exchange_plugin: bool = Field(
        default=False, description="Enable RabbitMQ delayed message plugin"
    )
    delayed_exchange: str = Field(
        default="delayed-exchange", description="Name of delayed exchange"
    )

    # Queue configuration
    message_ttl: int | None = Field(
        default=None, description="Message TTL in milliseconds"
    )
    max_priority: int | None = Field(
        default=None, description="Maximum priority for priority queue", ge=0, le=255
    )
    queue_durable: bool = Field(default=True, description="Make queue durable")
    queue_auto_delete: bool = Field(
        default=False, description="Auto-delete queue when unused"
    )

    # Dead letter configuration
    dead_letter_routing_key: str | None = Field(
        default=None, description="Routing key for dead letter exchange"
    )

    # High availability
    enable_ha: bool = Field(default=False, description="Enable high availability")
    ha_policy: str = Field(default="all", description="HA policy (all, exactly, nodes)")
    ha_params: dict[str, Any] = Field(default_factory=dict, description="HA parameters")

    class Config:
        extra = "allow"


# Update class definition
class RabbitMQQueue(BaseQueue[RabbitMQQueueSettings]):
    """RabbitMQ queue implementation."""

    _settings: RabbitMQQueueSettings  # Explicit type annotation

    async def _ensure_settings(self) -> RabbitMQQueueSettings:
        """Ensure settings are loaded and typed correctly."""
        if self._settings is None:
            self._settings = RabbitMQQueueSettings()
        return self._settings
```

**Expected Result**: 19 → 0 errors in rabbitmq.py

#### Task 2.2: Create StateServiceSettings

**Agent**: python-pro
**File**: `acb/services/state.py`
**Estimated Time**: 1.5 hours
**Risk Level**: MEDIUM - Core state management

**Implementation**:

```python
# Add to acb/services/state.py
from pydantic import BaseModel, Field


class StateServiceMetrics(BaseModel):
    """Extended metrics for state service."""

    # Operation counters
    gets_total: int = 0
    sets_total: int = 0
    deletes_total: int = 0
    expires_total: int = 0

    # Persistence metrics
    persistent_reads_total: int = 0
    persistent_writes_total: int = 0

    # Synchronization metrics
    sync_operations_total: int = 0
    sync_conflicts_total: int = 0

    # Lock metrics
    lock_acquisitions_total: int = 0
    lock_timeouts_total: int = 0

    # Memory metrics
    memory_entries_count: int = 0
    memory_size_bytes: int = 0

    class Config:
        extra = "allow"


class StateServiceSettings(ServiceSettings):
    """State management service configuration."""

    # Timeouts
    cleanup_interval_seconds: int = Field(
        default=300, description="Cleanup interval in seconds", ge=1
    )
    lock_timeout_seconds: int = Field(
        default=30, description="Lock acquisition timeout", ge=1
    )

    # State backend configuration
    distributed_state_enabled: bool = Field(
        default=False, description="Enable distributed state"
    )
    state_backend: str = Field(
        default="memory", description="State backend type (memory, redis, etc.)"
    )

    class Config:
        extra = "allow"


# Update class to use new settings
class StateService:
    _settings: StateServiceSettings
    _metrics: StateServiceMetrics

    def __init__(self):
        self._settings = StateServiceSettings()
        self._metrics = StateServiceMetrics()
```

**Expected Result**: 34 → 0 errors in state.py

#### Task 2.3: Create EventPublisherSettings

**Agent**: python-pro
**File**: `acb/events/publisher.py`
**Estimated Time**: 2 hours
**Risk Level**: HIGH - Event system architecture

**Note**: This file also has abstract method issues. Handle carefully.

**Implementation**:

```python
# Add to acb/events/publisher.py
from pydantic import BaseModel, Field
from typing import Any


class EventPublisherSettings(BaseModel):
    """Event publisher configuration."""

    # Basic settings
    event_buffer_size: int = Field(default=1000, ge=1)
    batch_size: int = Field(default=100, ge=1)
    flush_interval_seconds: float = Field(default=1.0, ge=0.1)

    # Retry configuration
    max_retries: int = Field(default=3, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0)

    # Queue settings
    queue_type: str = Field(default="memory")
    queue_config: dict[str, Any] = Field(default_factory=dict)

    # Delivery settings
    enable_persistence: bool = False
    persistence_backend: str | None = None

    class Config:
        extra = "allow"


class EventPublisher:
    _settings: EventPublisherSettings

    def __init__(self, settings: EventPublisherSettings | None = None):
        self._settings = settings or EventPublisherSettings()
```

**Also handle abstract methods** - Check what abstract methods need implementation and add them.

**Expected Result**: 41 → ~5 errors (some abstract method issues may remain)

### Sprint 3 Tasks (Union Handling)

#### Task 3.1: Fix union-attr in Reasoning Adapters

**Agent**: refactoring-specialist
**Files**:

- `acb/adapters/reasoning/llamaindex.py` (15 errors)
- `acb/adapters/reasoning/langchain.py` (12 errors)
- `acb/adapters/reasoning/custom.py` (8 errors)

**Estimated Time**: 2 hours total
**Risk Level**: MEDIUM - Affects reasoning logic

**Pattern**:

```python
# Before (causes union-attr error)
result = await self._operation()
value = result.attribute  # Error if result could be None

# Fix 1: Early return with type narrowing
result = await self._operation()
if result is None:
    return default_value  # or raise exception
value = result.attribute  # Now safe

# Fix 2: Walrus operator with type narrowing
if (result := await self._operation()) is not None:
    value = result.attribute
else:
    value = default_value

# Fix 3: Assert for impossible None cases
result = await self._operation()
assert result is not None, "Operation should never return None"
value = result.attribute

# Fix 4: Optional chaining (when default is acceptable)
value = getattr(result, "attribute", default_value) if result else default_value
```

**Example from llamaindex.py**:

```python
# Line with union-attr error
task = self._get_task()
name = task.get_name()  # Error: task could be None

# Fixed version
task = self._get_task()
if task is None:
    raise ValueError("Task not found")
name = task.get_name()  # Safe now
```

**Expected Result**: 35 → 5 errors (handle obvious cases, defer complex logic)

## Common Pitfalls and Solutions

### Pitfall 1: Generator vs Iterator

```python
# WRONG - mypy expects Generator specifically
@pytest.fixture
def fixture() -> Iterator[Type]:
    yield value


# CORRECT
from collections.abc import Generator


@pytest.fixture
def fixture() -> Generator[Type, None, None]:
    yield value
```

### Pitfall 2: Private Attribute Access in Tests

```python
# WRONG - Will cause attr-defined error
config._internal_data

# CORRECT - Multiple options
# Option 1: Type ignore
config._internal_data  # type: ignore[attr-defined]

# Option 2: Hasattr check
if hasattr(config, "_internal_data"):
    data = config._internal_data

# Option 3: Getattr with default
data = getattr(config, "_internal_data", {})
```

### Pitfall 3: Settings Class Inheritance

```python
# WRONG - Missing proper typing
class MySettings(BaseSettings):
    pass


class MyClass:
    _settings: BaseSettings  # Too generic


# CORRECT
class MySettings(BaseSettings):
    my_field: str = "default"


class MyClass:
    _settings: MySettings  # Specific type
```

### Pitfall 4: Union Type Narrowing

```python
# WRONG - Direct access without check
value = optional_value.attribute

# CORRECT - Proper narrowing
if optional_value is not None:
    value = optional_value.attribute
```

## Test Validation Protocol

After each fix:

1. **Type check**: `zuban check <file>`
1. **Run tests**: `python -m pytest tests/<corresponding_test>.py -v`
1. **Verify no regressions**: Check error count decreased
1. **Document**: Update progress in this file

## Progress Tracking

### Sprint 1 Progress

- [ ] Task 1.1: testing/fixtures.py (32 → 5)
- [ ] Task 1.2: testing/performance.py (30 → 8)
- [ ] Task 1.3: Batch no-any-return (52 → 0)
- [ ] Task 1.4: Batch type-arg (42 → 0)
- **Target**: 549 → 361 errors (-188)

### Sprint 2 Progress

- [ ] Task 2.1: RabbitMQQueueSettings (19 → 0)
- [ ] Task 2.2: StateServiceSettings (34 → 0)
- [ ] Task 2.3: EventPublisherSettings (41 → 5)
- [ ] Additional settings classes (35 → 5)
- **Target**: 361 → 241 errors (-120)

### Sprint 3 Progress

- [ ] Task 3.1: Union handling - reasoning adapters (35 → 5)
- [ ] Task 3.2: Union handling - services (15 → 3)
- **Target**: 241 → 191 errors (-50)

## Emergency Procedures

### If Tests Break

1. **Stop immediately**
1. Review the change that broke tests
1. Check if it's a test issue or logic issue
1. Revert if uncertain
1. Document the issue and ask for guidance

### If Error Count Increases

1. **Verify your change** with `git diff`
1. Run `zuban check` on just the changed file
1. Check if new errors are related to your changes
1. If unrelated, continue; if related, review fix

### If Stuck

1. **Document** what you tried
1. **Note** the specific error and context
1. **Skip** to next task
1. Flag for manual review

## Success Criteria

Each sprint must meet:

- ✅ Target error reduction achieved
- ✅ All tests pass
- ✅ No new errors introduced
- ✅ Changes committed with clear messages
- ✅ Crackerjack verification passes

## Final Notes

- **Be conservative**: When uncertain, add `type: ignore` with comment
- **Test frequently**: After every 5-10 fixes
- **Commit often**: After each completed task
- **Document issues**: Any unexpected problems or blockers
- **Ask for help**: If something seems architecturally wrong

This guide is your tactical playbook. Follow it systematically, and we'll achieve our remediation goals efficiently and safely.
