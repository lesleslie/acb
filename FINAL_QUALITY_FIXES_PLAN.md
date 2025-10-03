# Final Quality Fixes Implementation Plan

## Current State

- **Complexipy**: 19 violations (16-19 range)
- **Refurb**: 78 violations (45× FURB107, 3× FURB173, 30× others)
- **Zuban**: 168 type errors

## Implementation Strategy

### Phase 1: Refurb FURB107 (contextlib.suppress) - 45 instances

**Pattern**: Replace `try: ... except Exception: pass` with `with suppress(Exception): ...`

**Files to modify** (in order of concentration):

1. `acb/mcp/registry.py` - 6 instances (lines 43, 58, 65, 87, 92, 146)
1. `acb/mcp/server.py` - 5 instances (lines 334, 340, 352, 361, 366)
1. `acb/adapters/queue/rabbitmq.py` - 5 instances (lines 215, 315, 323, 331, 339)
1. `acb/services/repository/unit_of_work.py` - 5 instances (lines 219, 273, 284, 357, 524)
1. `acb/services/repository/service.py` - 3 instances (lines 467, 480, 493)
1. `acb/adapters/queue/redis.py` - 3 instances (lines 310, 317, 325)
1. `acb/migration/assessment.py` - 2 instances (lines 64, 73)
1. `acb/queues/__init__.py` - 2 instances (lines 301, 513)
1. Single instance files - 14 files with 1 each

**Implementation**: Add `from contextlib import suppress` at top, replace patterns

### Phase 2: Other Refurb Violations - 33 instances

**FURB173 (dict merge)** - 4 instances:

- `acb/services/performance/serverless.py:796, 1003`
- `acb/services/repository/cache.py:153`
- `acb/services/repository/coordinator.py:307`

**FURB138 (list comprehension)** - 6 instances:

- `acb/events/discovery.py:364`
- `acb/services/repository/_base.py:421, 438`
- `acb/services/repository/unit_of_work.py:442`
- `acb/testing/providers/actions.py:216`
- `acb/testing/providers/adapters.py:226, 276`

**FURB110, FURB111, FURB113, etc.** - 23 remaining instances

### Phase 3: Zuban Type Errors - 168 errors in 34 files

**Priority files** (most errors):

1. `acb/services/error_handling.py` - 13 errors (missing annotations)
1. `acb/adapters/graph/arangodb.py` - 8 errors (SecretStr, dict indexing)
1. `acb/adapters/reasoning/openai_functions.py` - 4 errors (Logger type, dict types)
1. `acb/services/health.py` - 4 errors (type mismatches)
1. `acb/services/repository/_base.py` - 4 errors (annotations, generics)
1. `acb/adapters/graph/neo4j.py` - 4 errors (SecretStr, dict indexing)
1. `acb/adapters/vector/pinecone.py` - 3 errors (type mismatches)
1. `acb/adapters/reasoning/custom.py` - 4 errors (Logger, division by zero)

**Common patterns**:

- Logger type issues: Use TYPE_CHECKING guard
- Missing function annotations: Add complete type hints
- Dict index with nullable keys: Add null checks
- SecretStr compatibility: Handle nullable SecretStr
- Missing generic parameters: Add [Any, Any] to generics

### Phase 4: Complexity Violations - 19 functions (16-19 range)

Extract helper methods to reduce complexity below 15:

- Complexity 16-17: 12 functions (need 1-2 helper methods each)
- Complexity 18-19: 7 functions (need 3-4 helper methods each)

## Execution Order

1. **Refurb fixes** (quick wins, purely mechanical)
1. **Zuban type errors** (systematic, grouped by pattern)
1. **Complexity violations** (requires thoughtful refactoring)
1. **Final verification** (crackerjack -t)

## Success Criteria

- ✅ 0 refurb violations
- ✅ 0 zuban type errors
- ✅ 0 complexity violations (all ≤15)
- ✅ All tests pass
- ✅ No logic regressions
