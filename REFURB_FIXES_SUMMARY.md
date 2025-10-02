# Refurb Fixes Summary and Implementation Plan

## Summary

This document tracks the progress of fixing all refurb violations in the ACB codebase.

## Total Violations Found

- **Total**: 68 violations across all FURB categories
- **FURB107 (try/except → suppress)**: 41 violations in 23 files
- **FURB173 (dict unpacking → merge operator)**: 4 violations
- **FURB138 (loops → comprehensions)**: 7 violations
- **FURB110 (if/else → or operator)**: 4 violations
- **FURB113 (multiple append → extend)**: 3 violations
- **Other FURB issues**: 9 violations

## Completed Fixes

### FURB107 - try/except → suppress() (9 of 41 completed)

**Files Fixed:**

1. ✅ `acb/adapters/embedding/onnx.py` - 1 violation (added suppress import, fixed line 303)
1. ✅ `acb/services/performance/serverless.py` - 6 violations (already had suppress import, fixed lines 652, 711, 722, 741, 748, 996)
1. ✅ `acb/logger.py` - 2 violations (added suppress import, fixed lines 55, 62)

**Total FURB107 Fixed**: 9 violations
**Remaining FURB107**: 32 violations in 20 files

### FURB173 - Dict Merging (2 of 4 completed)

**Files Fixed:**

1. ✅ `acb/adapters/embedding/huggingface.py` - 2 violations (lines 149, 174)

**Remaining FURB173**:

- `acb/services/repository/cache.py:153`
- `acb/services/repository/coordinator.py:307`

## Remaining Work

### Priority 1: Complete FURB107 Fixes (32 remaining)

**Files Needing Fixes:**

1. `acb/adapters/queue/rabbitmq.py` - 4 violations at lines [315, 323, 331, 339]
1. `acb/adapters/queue/redis.py` - 3 violations at lines [310, 317, 325]
1. `acb/services/repository/unit_of_work.py` - 5 violations at lines [219, 273, 284, 357, 524]
1. `acb/services/repository/service.py` - 3 violations at lines [467, 480, 493]
1. `acb/events/discovery.py` - 2 violations at lines [441, 550]
1. `acb/migration/assessment.py` - 2 violations at lines [64, 73]
1. `acb/queues/__init__.py` - 2 violations at lines [301, 510]
1. `acb/services/discovery.py` - 2 violations at lines [428, 533]
1. `acb/testing/discovery.py` - 2 violations at lines [413, 518]
1. `acb/testing/utils.py` - 2 violations at lines [251, 275]
1. `acb/events/__init__.py` - 1 violation at line [368]
1. `acb/events/_base.py` - 1 violation at line [424]
1. `acb/events/publisher.py` - 1 violation at line [199]
1. `acb/queues/discovery.py` - 1 violation at line [534]
1. `acb/queues/rabbitmq.py` - 1 violation at line [213]
1. `acb/queues/redis.py` - 1 violation at line [718]
1. `acb/services/__init__.py` - 1 violation at line [258]
1. `acb/services/repository/coordinator.py` - 1 violation at line [551]
1. `acb/services/repository/registry.py` - 1 violation at line [259]
1. `acb/services/validation/coercion.py` - 1 violation at line [327]
1. `acb/testing/fixtures.py` - 1 violation at line [299]
1. `acb/workflows/_base.py` - 1 violation at line [391]

**Implementation Steps for Each File:**

1. Add `from contextlib import suppress` import at the top (after other imports)
1. For each violation, convert:
   ```python
   try:
       # code
   except Exception:
       pass
   ```
   to:
   ```python
   with suppress(Exception):
       # code
   ```

### Priority 2: FURB173 - Dict Merging (2 remaining)

Replace `{..., **dict}` with `{...} | dict`:

1. `acb/services/repository/cache.py:153` - Replace `{..., ..., **kwargs}` with `{...} | {...} | kwargs`
1. `acb/services/repository/coordinator.py:307` - Replace `{..., **entity_data}` with `{...} | entity_data`

### Priority 3: FURB138 - List Comprehensions (7 instances)

Convert loops to list comprehensions:

1. `acb/events/discovery.py:364`
1. `acb/services/repository/_base.py:421`
1. `acb/services/repository/_base.py:438`
1. `acb/services/repository/unit_of_work.py:442`
1. `acb/testing/providers/actions.py:216`
1. `acb/testing/providers/adapters.py:226`
1. `acb/testing/providers/adapters.py:276`

### Priority 4: FURB110 - Replace if/else with or (4 instances)

Replace `x if x else None` with `x or None`:

1. `acb/adapters/reasoning/openai_functions.py:308`
1. `acb/services/repository/query_builder.py:525`
1. `acb/services/repository/query_builder.py:578`
1. `acb/services/validation/decorators.py:266`

### Priority 5: FURB113 - Replace append with extend (3 instances)

Replace multiple `append()` calls with single `extend()`:

1. `acb/adapters/reasoning/openai_functions.py:768`
1. `acb/migration/assessment.py:175`
1. `acb/services/validation/results.py:169`

### Priority 6: Other FURB Issues (9 instances)

1. **FURB108** (1 instance): `acb/adapters/embedding/_base.py:358` - Replace `x == y or z == y` with `y in (x, z)`
1. **FURB109** (2 instances): Replace `in [x, y, z]` with `in (x, y, z)`
   - `acb/adapters/reasoning/custom.py:694`
   - `acb/testing/providers/security.py:250`
1. **FURB115** (1 instance): `acb/services/performance/serverless.py:632` - Replace `len(x) == 0` with `not x`
1. **FURB117** (2 instances): Replace `open(path)` with `path.open()`
   - `acb/migration/assessment.py:78`
   - `acb/testing/utils.py:445`
1. **FURB118** (1 instance): `acb/adapters/embedding/sentence_transformers.py:340` - Replace lambda with `operator.itemgetter`
1. **FURB143** (1 instance): `acb/adapters/queue/rabbitmq.py:550` - Replace `x or {}` with `x`
1. **FURB168** (1 instance): `acb/services/validation/output.py:188` - Replace `isinstance(x, ... | type(None))` with `x is None or isinstance(x, ...)`
1. **FURB183** (1 instance): `acb/queues/rabbitmq.py:762` - Replace f-string with str()
1. **FURB102** (1 instance): `acb/testing/providers/adapters.py:198` - Replace `x.startswith(y) or x.startswith(z)` with `x.startswith((y, z))`

## Verification Steps

After all fixes are complete:

1. Run `refurb acb/` to verify all violations are resolved
1. Run `python -m crackerjack -t` to ensure:
   - All pre-commit hooks pass
   - All tests pass
   - Code quality meets project standards
1. Format code with `ruff format`
1. Final verification with `ruff check --select FURB`

## Progress Tracking

- **Total Violations**: 68
- **Fixed**: 11 (16%)
- **Remaining**: 57 (84%)

### By Category Progress

| Category | Total | Fixed | Remaining | % Complete |
|----------|-------|-------|-----------|------------|
| FURB107 | 41 | 9 | 32 | 22% |
| FURB173 | 4 | 2 | 2 | 50% |
| FURB138 | 7 | 0 | 7 | 0% |
| FURB110 | 4 | 0 | 4 | 0% |
| FURB113 | 3 | 0 | 3 | 0% |
| Others | 9 | 0 | 9 | 0% |

## Estimated Time to Complete

Based on the fixes completed so far:

- **FURB107**: ~3-4 hours (32 violations across 20 files)
- **FURB173**: ~10 minutes (2 violations)
- **FURB138**: ~30-45 minutes (7 violations)
- **FURB110**: ~15 minutes (4 violations)
- **FURB113**: ~15 minutes (3 violations)
- **Others**: ~30 minutes (9 violations)

**Total Estimated Time**: 5-6 hours

## Next Steps

1. Continue with FURB107 fixes systematically file by file
1. Apply quick wins (FURB173, FURB110, FURB113)
1. Convert loops to comprehensions (FURB138)
1. Fix remaining misc violations
1. Run full verification suite
1. Commit changes with descriptive message

## Notes

- All files requiring suppress() import need `from contextlib import suppress` added
- Priority is on FURB107 as it has the most instances (41) and represents a code quality improvement
- The refurb command has timeout issues when run on the entire codebase - run on individual files or directories
- Some violations may auto-fix when others are resolved due to code structure changes
