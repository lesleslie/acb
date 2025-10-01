---
id: 01K6GMDNK54X7CRFRA8GZY4CKH
---
______________________________________________________________________

## id: 01K6GKSSH66P9RN2K8TD4AN9CW

______________________________________________________________________

## id: 01K6GKJGWWQXE4J4QHRGGD5QM3

______________________________________________________________________

## id: 01K6GJYE06GCX9YFZC52ZKQMJ2

______________________________________________________________________

## id: 01K6GGM97MRF44CCHTNW4WZSQJ

______________________________________________________________________

## id: 01K6G6880YK71025H1MYGBXKVF

______________________________________________________________________

## id: 01K6G5HVCNQTGHR3612D9W97SG

______________________________________________________________________

## id: 01K6G58KFHVFEQC2JYBR5SZK4R

______________________________________________________________________

## id: 01K6G4MK99NPW33E2WJT761N72

______________________________________________________________________

## id: 01K6FYP5QK31T03HFJVY510BNX

# Type Error Remediation Plan

**Generated**: 2025-10-01
**Current Status**: 549 errors across 55 files
**Previous Status**: 686 errors (20% reduction achieved)
**Target**: \<100 errors (critical path focus)

## Executive Summary

Analysis of the 549 remaining type errors reveals clear patterns and priorities:

### Error Distribution by Type

| Error Type | Count | % Total | Complexity |
|------------|-------|---------|------------|
| `attr-defined` | 183 | 33.3% | Medium - Settings/internal attributes |
| `union-attr` | 65 | 11.8% | Low-Medium - Optional handling |
| `no-any-return` | 52 | 9.5% | Low - Add return type hints |
| `type-arg` | 42 | 7.6% | Low - Add generic type parameters |
| `assignment` | 42 | 7.6% | Medium - Type narrowing needed |
| `no-untyped-def` | 34 | 6.2% | Low - Add function signatures |
| `return-value` | 32 | 5.8% | Low-Medium - Generator/fixture types |
| `misc` | 23 | 4.2% | Medium - Generator return types |
| Others | 76 | 13.8% | Varies |

### High-Impact Files (Top 10)

| File | Errors | Primary Issues | Risk Level |
|------|--------|----------------|------------|
| `adapters/reasoning/llamaindex.py` | 44 | attr-defined (settings), union-attr | High |
| `events/publisher.py` | 41 | attr-defined (settings), abstract methods | High |
| `services/repository/service.py` | 35 | attr-defined (settings), type-arg | Medium |
| `services/state.py` | 34 | attr-defined, assignment | Medium |
| `testing/fixtures.py` | 32 | return-value (generators), attr-defined | Low |
| `services/repository/cache.py` | 32 | attr-defined, no-any-return | Medium |
| `adapters/reasoning/langchain.py` | 31 | attr-defined (settings), union-attr | High |
| `testing/performance.py` | 30 | no-untyped-def, type-arg, index | Low |
| `adapters/reasoning/custom.py` | 26 | attr-defined (settings) | Medium |
| `services/error_handling.py` | 25 | attr-defined, union-attr | Medium |

## Critical Findings

### 1. Settings Attribute Pattern (183 errors - 33%)

**Root Cause**: Dynamic settings access pattern `settings.attribute_name` where attributes aren't defined in base settings classes.

**Examples**:

```python
# From queues/rabbitmq.py
settings.rabbitmq_url  # attr-defined error
settings.use_delayed_exchange_plugin  # attr-defined error
settings.message_ttl  # attr-defined error

# From services/state.py
settings.distributed_state_enabled  # attr-defined error
settings.state_backend  # attr-defined error
```

**Solution**: Three approaches:

1. **Quick Fix**: Use `getattr(settings, 'attribute', default)` with type: ignore
1. **Proper Fix**: Define typed settings subclasses per module
1. **Best Fix**: Use Pydantic model_extra='allow' with __getattr__ typing

### 2. Testing Infrastructure (94 errors - 17%)

**Files**: `testing/fixtures.py` (32), `testing/performance.py` (30), `testing/utils.py` (12), others (20)

**Issues**:

- Generator return types (`return-value`, `misc`) - 23 errors
- Missing function signatures (`no-untyped-def`) - 15 errors
- Private attribute access (`attr-defined`) - 10 errors

**Priority**: Low risk - testing code doesn't affect runtime
**Strategy**: Batch fix with proper Generator/AsyncGenerator types

### 3. Reasoning Adapters (132 errors - 24%)

**Files**: `llamaindex.py` (44), `langchain.py` (31), `custom.py` (26), `openai_functions.py` (10)

**Common Pattern**:

```python
# 65 union-attr errors
result.something  # when result could be None
task.get_name()  # when task is Task[Any] | None
```

**Strategy**: Add proper None checks before attribute access

### 4. Services Layer (147 errors - 27%)

**Primary Issues**:

- Settings attributes (attr-defined) - 85 errors
- Missing type parameters (type-arg) - 25 errors
- Assignment type mismatches - 20 errors

## Remediation Strategy

### Phase 1: Quick Wins (Target: -150 errors, 2-3 hours)

#### 1.1 Testing Infrastructure (94 errors → ~20 errors)

**Priority**: High - Easy, low risk, big impact

**Actions**:

```python
# Fix generator return types in testing/fixtures.py
from collections.abc import Generator, AsyncGenerator
from typing import Any


# Before
@pytest.fixture
def some_fixture():
    yield value


# After
@pytest.fixture
def some_fixture() -> Generator[SomeType, None, None]:
    yield value


# For async generators
@pytest.fixture
async def async_fixture() -> AsyncGenerator[SomeType, None]:
    yield value
```

**Files to fix**:

- `testing/fixtures.py`: 32 errors → ~5 errors (add Generator types)
- `testing/performance.py`: 30 errors → ~8 errors (add function signatures)
- `testing/utils.py`: 12 errors → ~3 errors (type annotations)
- `testing/discovery.py`: 1 error (return type fix)
- `testing/providers/services.py`: 5 errors (type annotations)

**Estimated Impact**: -74 errors

#### 1.2 Simple Type Annotations (52 errors → 0 errors)

**Priority**: High - Trivial fixes

**Actions**:

```python
# Fix no-any-return (52 errors)
# Before
async def get_value(self):
    return await self.client.get()


# After
async def get_value(self) -> str:
    return await self.client.get()


# Fix no-untyped-def (34 errors)
# Before
def process(data):
    return transform(data)


# After
def process(data: dict[str, Any]) -> dict[str, Any]:
    return transform(data)
```

**Estimated Impact**: -52 errors (no-any-return) + -20 errors (no-untyped-def) = -72 errors

#### 1.3 Generic Type Parameters (42 errors → 0 errors)

**Priority**: High - Simple additions

**Actions**:

```python
# Fix type-arg errors
# Before
tasks: list = []
data: dict = {}
client: Redis = ...

# After
tasks: list[Task[Any]] = []
data: dict[str, Any] = {}
client: Redis[bytes] = ...
```

**Estimated Impact**: -42 errors

**Phase 1 Total**: -188 errors (549 → 361)

### Phase 2: Settings Pattern Fix (Target: -120 errors, 3-4 hours)

**Priority**: Medium - Moderate complexity, high impact

#### 2.1 Create Typed Settings Subclasses

**Strategy**: Define proper settings classes with all required attributes

```python
# Example for queues/rabbitmq.py (19 errors)
from pydantic import BaseModel, Field


class RabbitMQQueueSettings(QueueSettings):
    """RabbitMQ-specific queue settings."""

    rabbitmq_url: str = Field(default="amqp://localhost")
    use_delayed_exchange_plugin: bool = False
    delayed_exchange: str = "delayed-exchange"
    message_ttl: int | None = None
    max_priority: int | None = None
    dead_letter_routing_key: str | None = None
    enable_ha: bool = False
    ha_policy: str = "all"
    ha_params: dict[str, Any] = Field(default_factory=dict)
    queue_durable: bool = True
    queue_auto_delete: bool = False


class RabbitMQQueue(BaseQueue[RabbitMQQueueSettings]):
    """RabbitMQ queue implementation."""

    _settings: RabbitMQQueueSettings
```

#### 2.2 Priority Files for Settings Fixes

**High Priority** (settings-heavy, 85 errors):

1. `queues/rabbitmq.py` - 19 errors → Create RabbitMQQueueSettings
1. `services/state.py` - 20 errors → Create StateServiceSettings
1. `queues/__init__.py` - 10 errors → Update ServiceSettings
1. `services/repository/cache.py` - 15 errors → Create RepositoryCacheSettings
1. `events/publisher.py` - 21 errors → Create EventPublisherSettings

**Medium Priority** (40 errors):

- `services/error_handling.py` - 15 errors
- `services/health.py` - 8 errors
- `services/repository/service.py` - 17 errors

**Estimated Impact**: -120 errors (183 → 63 remaining attr-defined)

### Phase 3: Union/Optional Handling (Target: -50 errors, 2-3 hours)

**Priority**: Medium - Straightforward but requires careful review

#### 3.1 Add None Checks (65 union-attr errors)

**Pattern**:

```python
# Before
result = await some_operation()
value = result.attribute  # Error: union-attr

# After
result = await some_operation()
if result is not None:
    value = result.attribute
else:
    # Handle None case
    value = default_value
```

**Files to fix**:

- `adapters/reasoning/llamaindex.py` - 15 errors
- `adapters/reasoning/langchain.py` - 12 errors
- `events/publisher.py` - 10 errors
- `services/error_handling.py` - 8 errors
- Other files - 20 errors

**Estimated Impact**: -50 errors (65 → 15 difficult cases)

### Phase 4: Complex Fixes (Target: -50 errors, 4-5 hours)

**Priority**: Low-Medium - Complex or architectural changes

#### 4.1 Assignment Type Mismatches (42 errors)

**Examples**:

```python
# queues/redis.py:518
# Before
attempts: int = task_result  # TaskResult type mismatch

# After
attempts: int = task_result.attempts if isinstance(task_result, TaskResult) else 0
```

#### 4.2 Abstract Method Implementation (8 errors)

**Files**: `events/publisher.py`, `services/repository/_base.py`

**Action**: Implement required abstract methods or adjust inheritance

#### 4.3 Valid-Type Errors (5 errors)

**Example**:

```python
# Before
logger: Logger = ...  # Variable used as type

# After
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from acb.logger import LoggerType
logger: LoggerType = ...
```

**Estimated Impact**: -50 errors

## File-by-File Priority Recommendations

### Tier 1: Critical Path (Core Framework)

**Must fix before release**

1. **adapters/reasoning/llamaindex.py** (44 errors)

   - **Complexity**: Medium
   - **Effort**: 2-3 hours
   - **Issues**: Settings attributes (20), union-attr (15), no-any-return (9)
   - **Strategy**: Create LlamaIndexReasoningSettings, add None checks
   - **Agent**: python-pro (settings), refactoring-specialist (union handling)

1. **events/publisher.py** (41 errors)

   - **Complexity**: High
   - **Effort**: 3-4 hours
   - **Issues**: Settings attributes (21), abstract methods (8), union-attr (10)
   - **Strategy**: Create EventPublisherSettings, implement abstract methods
   - **Agent**: python-pro (comprehensive refactor)

1. **services/repository/service.py** (35 errors)

   - **Complexity**: Medium
   - **Effort**: 2 hours
   - **Issues**: Settings attributes (17), type-arg (10), no-any-return (8)
   - **Strategy**: Add generic types, create RepositoryServiceSettings
   - **Agent**: python-pro

### Tier 2: High-Impact Quick Wins

**Easy fixes, big impact**

4. **testing/fixtures.py** (32 errors)

   - **Complexity**: Low
   - **Effort**: 1 hour
   - **Issues**: return-value (15), misc (10), attr-defined (7)
   - **Strategy**: Add Generator/AsyncGenerator types, fix private access
   - **Agent**: refactoring-specialist

1. **testing/performance.py** (30 errors)

   - **Complexity**: Low
   - **Effort**: 1 hour
   - **Issues**: no-untyped-def (15), type-arg (10), misc (5)
   - **Strategy**: Add function signatures, generic types
   - **Agent**: refactoring-specialist

### Tier 3: Moderate Complexity

**Important but can be staged**

6. **services/state.py** (34 errors)

   - **Complexity**: Medium
   - **Effort**: 2 hours
   - **Issues**: Settings attributes (20), assignment (8), union-attr (6)
   - **Strategy**: Create StateServiceSettings, fix type narrowing

1. **services/repository/cache.py** (32 errors)

   - **Complexity**: Medium
   - **Effort**: 2 hours
   - **Issues**: Settings attributes (15), no-any-return (12), type-arg (5)
   - **Strategy**: Create RepositoryCacheSettings, add return types

1. **adapters/reasoning/langchain.py** (31 errors)

   - **Complexity**: Medium
   - **Effort**: 2 hours
   - **Issues**: Settings attributes (15), union-attr (12), no-any-return (4)
   - **Strategy**: Similar to llamaindex.py

### Tier 4: Low Priority / Defer

**Non-critical or low-value files**

9. **adapters/reasoning/custom.py** (26 errors)

   - Can defer - less commonly used

1. **services/error_handling.py** (25 errors)

   - Can stage after core fixes

1. **queues/rabbitmq.py** (19 errors)

   - Queue system is optional, can defer

## Execution Plan

### Sprint 1: Foundation (Day 1-2, Target: 549 → 361)

**Goal**: Quick wins, maximum error reduction

**Tasks**:

1. **Testing Infrastructure** (python-pro agent)

   - Fix `testing/fixtures.py` - Add Generator types
   - Fix `testing/performance.py` - Add function signatures
   - Fix `testing/utils.py` - Add type annotations
   - **Expected**: -74 errors

1. **Simple Type Annotations** (refactoring-specialist agent)

   - Batch fix `no-any-return` errors across all files
   - Batch fix `no-untyped-def` errors
   - Add generic type parameters (`type-arg`)
   - **Expected**: -114 errors

**Sprint 1 Target**: 549 → 361 errors (-188)

### Sprint 2: Settings Pattern (Day 3-4, Target: 361 → 241)

**Goal**: Systematic settings refactor

**Tasks**:

1. **High-Priority Settings** (python-pro agent)

   - `queues/rabbitmq.py` - RabbitMQQueueSettings
   - `services/state.py` - StateServiceSettings
   - `events/publisher.py` - EventPublisherSettings
   - `services/repository/cache.py` - RepositoryCacheSettings
   - **Expected**: -70 errors

1. **Medium-Priority Settings** (python-pro agent)

   - `services/repository/service.py` - RepositoryServiceSettings
   - `services/error_handling.py` - ErrorHandlingSettings
   - `services/health.py` - HealthServiceSettings
   - **Expected**: -50 errors

**Sprint 2 Target**: 361 → 241 errors (-120)

### Sprint 3: Union Handling (Day 5, Target: 241 → 191)

**Goal**: Fix None handling

**Tasks**:

1. **Reasoning Adapters** (refactoring-specialist agent)

   - `adapters/reasoning/llamaindex.py` - Add None checks
   - `adapters/reasoning/langchain.py` - Add None checks
   - `adapters/reasoning/custom.py` - Add None checks
   - **Expected**: -35 errors

1. **Services Layer** (refactoring-specialist agent)

   - `events/publisher.py` - Add None checks
   - `services/error_handling.py` - Add None checks
   - Other services files
   - **Expected**: -15 errors

**Sprint 3 Target**: 241 → 191 errors (-50)

### Sprint 4: Complex Fixes (Day 6-7, Target: 191 → ~140)

**Goal**: Address remaining complex issues

**Tasks**:

1. **Assignment Fixes** (python-pro agent)

   - Fix type mismatches in queues, services
   - **Expected**: -25 errors

1. **Abstract Methods** (python-pro agent)

   - Implement missing abstract methods
   - **Expected**: -8 errors

1. **Misc Complex Issues** (python-pro agent)

   - Valid-type errors, index errors, etc.
   - **Expected**: -17 errors

**Sprint 4 Target**: 191 → 141 errors (-50)

## Risk Assessment

### Low Risk (Safe to automate)

- **Testing infrastructure** - Won't affect production
- **Type annotations** - Pure metadata additions
- **Generic type parameters** - Clarifying existing intent

### Medium Risk (Review carefully)

- **Settings classes** - Could affect runtime configuration
- **Union handling** - Could introduce logic changes
- **Assignment fixes** - Verify type conversions are correct

### High Risk (Manual review required)

- **Abstract methods** - Could affect inheritance contracts
- **Complex refactors** - `events/publisher.py`, `services/repository/service.py`
- **Valid-type changes** - Type system structural changes

## Success Metrics

### Targets

- **Phase 1**: 549 → 361 (-34%, 2-3 hours)
- **Phase 2**: 361 → 241 (-33%, 3-4 hours)
- **Phase 3**: 241 → 191 (-21%, 2-3 hours)
- **Phase 4**: 191 → 141 (-26%, 4-5 hours)
- **Final Goal**: \<150 errors (73% reduction from 549)

### Quality Gates

- All tests must pass after each phase
- No new runtime errors introduced
- Type coverage improvement verified with zuban
- Code review for medium/high risk changes

## Agent Delegation Strategy

### python-pro Agent Tasks

**Focus**: Complex fixes, settings refactors, abstract methods

- Create typed settings subclasses (Phase 2)
- Fix abstract method implementations
- Complex type narrowing and assignment fixes
- Review and validate high-risk changes

### refactoring-specialist Agent Tasks

**Focus**: Bulk fixes, pattern-based changes, testing infrastructure

- Testing infrastructure fixes (Phase 1)
- Batch type annotation additions
- Union/Optional None checks (Phase 3)
- Repetitive pattern fixes across multiple files

### Coordination Protocol

1. **Sprint planning**: Define file targets and expected impact
1. **Batch operations**: Group similar fixes for efficiency
1. **Incremental verification**: Run `zuban check` after each major change
1. **Test validation**: Run full test suite after each phase
1. **Documentation**: Update this plan with actual results

## Implementation Notes

### Pattern Templates

#### Settings Class Template

```python
from pydantic import BaseModel, Field
from typing import Any


class ComponentSettings(BaseSettings):
    """Settings for ComponentName."""

    # Required fields
    required_field: str

    # Optional fields with defaults
    optional_field: bool = False
    timeout: int = Field(default=30, ge=1)

    # Collections
    options: dict[str, Any] = Field(default_factory=dict)
    items: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"  # Allow dynamic attributes
```

#### Union Handling Template

```python
# Pattern 1: Early return
result = await operation()
if result is None:
    return default_value
value = result.attribute

# Pattern 2: Walrus operator
if (result := await operation()) is not None:
    value = result.attribute

# Pattern 3: Type narrowing with assert
result = await operation()
assert result is not None, "Result should not be None"
value = result.attribute
```

#### Generator Type Template

```python
from collections.abc import Generator, AsyncGenerator
from typing import Any


@pytest.fixture
def sync_fixture() -> Generator[FixtureType, None, None]:
    """Fixture docstring."""
    resource = create_resource()
    yield resource
    cleanup(resource)


@pytest.fixture
async def async_fixture() -> AsyncGenerator[FixtureType, None]:
    """Async fixture docstring."""
    resource = await create_resource()
    yield resource
    await cleanup(resource)
```

### Verification Commands

```bash
# Check specific file
zuban check acb/testing/fixtures.py

# Check specific directory
zuban check acb/testing/

# Count errors by type
zuban check acb/ 2>&1 | grep "^acb/" | awk -F'\\[' '{print $2}' | sort | uniq -c | sort -rn

# Track progress
echo "Errors: $(zuban check acb/ 2>&1 | tail -1 | awk '{print $2}')"
```

### Git Strategy

- Create feature branch: `feature/type-error-remediation`
- Commit after each phase with clear messages
- Tag successful milestones: `phase-1-complete`, `phase-2-complete`, etc.
- Keep PRs focused on single phases for easier review

## Conclusion

This plan provides a clear path to reduce type errors from 549 to \<150 (73% reduction) over 4 sprints (~15 hours total effort). The phased approach prioritizes:

1. **Quick wins** for immediate impact
1. **Systematic patterns** for sustainable fixes
1. **Risk management** through careful staging
1. **Agent specialization** for optimal efficiency

The remediation is achievable with focused effort and will significantly improve the codebase's type safety and maintainability.

**Next Steps**:

1. Review and approve this plan
1. Assign Sprint 1 tasks to refactoring-specialist agent
1. Begin testing infrastructure fixes
1. Track progress against targets after each phase
