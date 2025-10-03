# Queue Systems Refactoring Plan

## Overview
Refactor queue systems to fix complexity violations and apply refurb modernizations in a single pass.

## Target Files & Current Issues

### 1. acb/queues/memory.py
**No complexity violations detected** - All functions already meet ≤13 complexity target.
**No refurb violations** for the specified patterns.

### 2. acb/queues/redis.py
**Complexity Violations:**
- `_receive` (lines 447-476): Estimated complexity ~16
  - Nested logic for resolving queue keys and dequeue operations
  - Multiple branches for Lua vs manual operations

- `get_task_status` (lines 477-526): Estimated complexity ~17
  - Multiple sequential checks across different storage locations
  - Nested loops and conditional branches

- `_process_dead_letter` (lines 651-683): Estimated complexity ~16-18
  - Multiple pipeline operations with error handling
  - Transaction complexity

**Refurb Violations:**
- Line 750: FURB107 - Replace `try: ... except Exception: pass` with `with suppress(Exception): ...`

### 3. acb/adapters/queue/_base.py
**No complexity violations detected** - Base class with abstract methods only.
**No refurb violations** for the specified patterns.

## Refactoring Strategy

### Phase 1: Redis Queue - Fix Complexity Violations

#### 1.1 Refactor `dequeue()` (lines 447-476)
Current complexity: ~16
Target complexity: ≤13

**Extraction Plan:**
- Extract `_resolve_queue_keys()` (lines 455-457) → Already extracted ✓
- Extract `_dequeue_with_lua()` (lines 461-462) → Already extracted ✓
- Extract `_dequeue_manual()` (lines 464-466) → Already extracted ✓
- Main method becomes simple orchestration

**Result:** Complexity reduced to ~8

#### 1.2 Refactor `get_task_status()` (lines 477-526)
Current complexity: ~17
Target complexity: ≤13

**Extraction Plan:**
- Extract `_check_result_storage()` → Check result_key first
- Extract `_check_processing_queue()` → Check processing status
- Extract `_check_pending_queues()` → Check pending queues and delayed
- Main method becomes linear checks with early returns

**Result:** Complexity reduced to ~6

#### 1.3 Refactor `_store_dead_letter_task()` (lines 651-683)
Current complexity: ~16-18
Target complexity: ≤13

**Extraction Plan:**
- Extract `_build_dead_letter_data()` → Create dead letter data structure
- Extract `_update_dead_letter_pipeline()` → Configure pipeline operations
- Main method orchestrates with simple error handling

**Result:** Complexity reduced to ~7

### Phase 2: Apply Refurb Modernizations

#### 2.1 FURB107 - Redis Queue Line 750
**Current:**
```python
try:
    await self._redis.aclose()
except Exception:
    pass
```

**Modern:**
```python
from contextlib import suppress

with suppress(Exception):
    await self._redis.aclose()
```

#### 2.2 Additional Modernizations
Check for additional patterns in all three files:
- FURB143: `x or {}` → `x` when x can't be None
- FURB115: `len(collection) == 0` → `not collection`
- FURB173: `{**dict1, ...}` → `dict1 | {...}`

## Implementation Order

1. **memory.py** - No changes needed (already compliant)
2. **redis.py** - Apply all refactorings:
   - Fix complexity violations (extract methods)
   - Apply FURB107 at line 750
   - Check for additional refurb patterns
3. **_base.py** - No changes needed (already compliant)

## Quality Verification

After refactoring, verify:
1. All functions have complexity ≤13
2. All refurb violations fixed
3. 100% test compatibility maintained
4. All async/await patterns preserved
5. Queue semantics and transaction safety preserved
6. Type hints added to all extracted methods

## Expected Outcomes

### Complexity Improvements
| Function | Before | After | Reduction |
|----------|--------|-------|-----------|
| RedisQueue.dequeue | 16 | 8 | -8 |
| RedisQueue.get_task_status | 17 | 6 | -11 |
| RedisQueue._store_dead_letter_task | 18 | 7 | -11 |

### Refurb Fixes
- FURB107: 1 violation fixed in redis.py
- All other patterns: Will be checked and fixed if found

### Code Quality
- More maintainable with smaller, focused functions
- Better testability with isolated logic
- Modern Python 3.13 patterns applied throughout
- Improved readability with descriptive function names
