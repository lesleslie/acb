# ACB Quality Remediation Plan

**Date**: October 3, 2025
**Current Quality Score**: 69/100 (per recent commit)
**Coverage**: 45.91% (down from 77.89% baseline)

## Executive Summary

Three critical issues have been identified and investigated:

1. ✅ **MCP Integration Bug**: FIXED - session-mgmt:crackerjack-run now works
2. ⚠️  **AI Auto-Fix Not Engaging**: DIAGNOSED - needs workflow configuration fix
3. ❌ **Quality Hooks Failing**: 33 refurb issues + 6 complexity violations
4. ⚠️  **Coverage Drop**: 32 percentage point decrease (77.89% → 45.91%)

---

## Issue #1: AI Auto-Fix Not Engaging ⚠️

### Root Cause Analysis

**Discovery**: The `--ai-fix` flag is recognized and environment setup occurs, but the AI fixing workflow doesn't engage even when hooks fail.

**Evidence**:
- `_determine_ai_fixing_needed()` returns `True` when hooks fail ✓
- Environment variables set via `setup_ai_agent_env()` ✓
- MCP/WebSocket servers running ✓
- **BUT**: No AI agent iterations occur
- **BUT**: No code modifications made
- **BUT**: No execution logs written to `~/.crackerjack/intelligence/`

**Key Code Locations**:
```
.venv/lib/python3.13/site-packages/crackerjack/core/workflow_orchestrator.py:
  - _determine_ai_fixing_needed() - Logic that decides if AI fixing needed
  - _execute_ai_fixing_workflow() - Should run AI iterations

.venv/lib/python3.13/site-packages/crackerjack/__main__.py:
  - setup_ai_agent_env() - Sets up AI agent environment variables
  - Line 1466: Calls setup_ai_agent_env(ai_fix, ai_debug or debug)
```

**Hypothesis**: The `options.ai_fix` flag may not be properly passed to the workflow orchestrator, OR the `_execute_ai_fixing_workflow()` function has a gate condition that's preventing execution.

### Immediate Action

**Need to investigate**:
1. Whether `options.ai_fix` is checked before calling `_execute_ai_fixing_workflow()`
2. What conditions must be met inside `_execute_ai_fixing_workflow()` for agent execution
3. Check if there's a missing MCP client connection requirement
4. Verify agent coordinator initialization

### Recommended Fix Strategy

```python
# In workflow_orchestrator.py, needs modification like:

def _determine_ai_fixing_needed(...) -> bool:
    # CURRENT: Only checks if hooks failed
    if publishing_requested:
        return not testing_passed or not comprehensive_passed
    return not testing_passed or not comprehensive_passed

    # SHOULD BE: Also check if ai_fix flag is enabled
    if not self.options.ai_fix:  # <-- Missing check?
        return False
    if publishing_requested:
        return not testing_passed or not comprehensive_passed
    return not testing_passed or not comprehensive_passed
```

---

## Issue #2: Quality Hook Failures ❌

### Refurb - 33 Code Quality Issues

**Category Breakdown**:

| Issue Type | Count | FURB Code | Fix Complexity |
|------------|-------|-----------|----------------|
| Use `contextlib.suppress()` | 13 | FURB107 | Low |
| Use list comprehensions | 7 | FURB138 | Low |
| Use dict merge `|` operator | 4 | FURB173 | Low |
| Use `.extend()` not `.append()` | 3 | FURB113 | Low |
| Use `in` operator | 1 | FURB108 | Low |
| Use `operator.itemgetter()` | 1 | FURB118 | Low |
| Use `chain.from_iterable()` | 1 | FURB179 | Low |
| Use `.startswith()` tuple | 1 | FURB102 | Low |
| Direct string conversion | 1 | FURB123 | Low |
| Simplify isinstance check | 1 | FURB168 | Low |

**All issues are LOW complexity** - simple refactoring patterns.

#### Detailed Fixes Required

**1. FURB107 - Use `contextlib.suppress()` (13 locations)**

Files affected:
- `acb/events/discovery.py:506`
- `acb/migration/assessment.py:64`, `73`
- `acb/queues/__init__.py:303`
- `acb/queues/discovery.py:534`
- `acb/services/discovery.py:493`
- `acb/services/repository/coordinator.py:593`
- `acb/services/repository/registry.py:268`
- `acb/services/repository/unit_of_work.py:219`
- `acb/testing/discovery.py:478`
- `acb/testing/fixtures.py:299`
- `acb/testing/utils.py:251`, `275`

Pattern:
```python
# BEFORE:
try:
    some_operation()
except Exception:
    pass

# AFTER:
from contextlib import suppress

with suppress(Exception):
    some_operation()
```

**2. FURB138 - Use list comprehensions (7 locations)**

Files affected:
- `acb/events/discovery.py:364`
- `acb/services/repository/_base.py:421`, `438`
- `acb/services/repository/unit_of_work.py:438`
- `acb/testing/providers/actions.py:216`
- `acb/testing/providers/adapters.py:226`, `276`

Pattern:
```python
# BEFORE:
result = []
for item in items:
    result.append(transform(item))

# AFTER:
result = [transform(item) for item in items]
```

**3. FURB173 - Use dict merge `|` operator (4 locations)**

Files affected:
- `acb/services/performance/serverless.py:793`, `1000`
- `acb/services/repository/cache.py:153`
- `acb/services/repository/coordinator.py:307`

Pattern:
```python
# BEFORE:
result = {**dict1, "key": "value", **dict2}

# AFTER:
result = dict1 | {"key": "value"} | dict2
```

**4. FURB113 - Use `.extend()` (3 locations)**

Files affected:
- `acb/adapters/reasoning/openai_functions.py:781`
- `acb/migration/assessment.py:175`
- `acb/services/validation/results.py:169`

Pattern:
```python
# BEFORE:
list.append(item1)
list.append(item2)

# AFTER:
list.extend((item1, item2))
```

**5. Other Single-Instance Issues (5 locations)**

- **FURB108** (`acb/adapters/embedding/_base.py:358`): `x == y or z == y` → `y in (x, z)`
- **FURB118** (`acb/adapters/embedding/sentence_transformers.py:340`): `lambda x: x[1]` → `operator.itemgetter(1)`
- **FURB179** (`acb/events/publisher.py:205`): Nested list comp → `chain.from_iterable()`
- **FURB102** (`acb/testing/providers/adapters.py:198`): `x.startswith(y) or x.startswith(z)` → `x.startswith((y, z))`
- **FURB123** (`acb/queues/rabbitmq.py:764`): Remove unnecessary `str()` conversion
- **FURB168** (`acb/services/validation/output.py:214`): Simplify `isinstance()` check

### Complexipy - 6 High-Complexity Functions

| File | Function | Complexity | Location | Priority |
|------|----------|------------|----------|----------|
| `queues/memory.py` | `MemoryQueue::_process_delayed_messages` | 16 | queues module | Medium |
| `adapters/vector/weaviate.py` | `Vector::upsert` | 16 | vector adapter | Medium |
| `migration/manager.py` | `MigrationManager::migrate` | 16 | migration system | Medium |
| `adapters/embedding/openai.py` | `OpenAIEmbedding::_embed_texts` | 17 | embedding adapter | Medium |
| `adapters/graph/arangodb.py` | `Graph::_get_node` | 17 | graph adapter | Medium |
| `services/performance/serverless.py` | `ServerlessOptimizer::_cleanup_expired` | 17 | performance service | Medium |

**Refactoring Strategy**:
- Extract conditional logic into helper methods
- Simplify nested if/else chains
- Use early returns to reduce nesting
- Break down large methods into smaller focused methods
- Target: Reduce complexity to ≤ 15 for all functions

---

## Issue #3: Coverage Drop ⚠️

### Current State

- **Baseline** (Sept 25): 77.89%
- **Current** (Oct 3): 45.91%
- **Drop**: -32 percentage points

### Investigation Needed

1. **Identify missing coverage areas**:
   ```bash
   python -m pytest --cov=acb --cov-report=term-missing | grep "MISSING"
   ```

2. **Compare coverage reports**:
   - Historical coverage data from Sept 25
   - Current coverage data

3. **Likely causes**:
   - New code added without tests
   - Test files deleted or disabled
   - Import errors preventing test discovery
   - Configuration changes affecting test execution

### Recovery Plan

1. Generate coverage report with missing lines
2. Prioritize high-value modules for test coverage
3. Add tests incrementally (target: 2-3% increase per session)
4. Update coverage baseline in `.coverage-ratchet.json`

---

## Detailed Remediation Steps

### Phase 1: Fix AI Auto-Fix (High Priority)

**Goal**: Get automated fixing working so future issues auto-resolve

1. **Investigate workflow orchestrator**:
   ```bash
   # Read the key functions
   grep -A50 "_execute_ai_fixing_workflow" .venv/lib/python3.13/site-packages/crackerjack/core/workflow_orchestrator.py
   ```

2. **Check options.ai_fix propagation**:
   - Verify `options.ai_fix` is passed to workflow orchestrator
   - Confirm it's checked before AI agent initialization
   - Add debug logging to trace execution flow

3. **Test MCP agent connection**:
   - Verify crackerjack can connect to MCP server on localhost:8676
   - Check WebSocket server on localhost:8675
   - Confirm agent coordinator can be initialized

4. **Create minimal test case**:
   ```bash
   # Create intentional refurb violation
   echo "x = 1; y = 2; result = []; [result.append(i) for i in range(10)]" > test_autofix.py

   # Run with ai-fix
   python -m crackerjack --ai-fix --verbose

   # Check if violation gets fixed
   ```

5. **Enable debug logging**:
   ```bash
   python -m crackerjack --ai-fix --ai-debug --verbose
   ```

**Success Criteria**: AI agent runs at least 1 iteration and modifies code

---

### Phase 2: Manual Quality Fixes (Immediate)

**Goal**: Clear all refurb and complexipy violations manually

#### 2A: Refurb Fixes (Estimated: 2-3 hours)

**Batch 1 - contextlib.suppress (13 files)**:
```python
# Add import at top of each file
from contextlib import suppress

# Replace all try/except pass patterns
# Estimated time: 45 minutes
```

**Batch 2 - List comprehensions (7 files)**:
```python
# Convert loops to comprehensions
# Estimated time: 30 minutes
```

**Batch 3 - Dict merge operator (4 files)**:
```python
# Replace {**dict1, **dict2} with dict1 | dict2
# Estimated time: 15 minutes
```

**Batch 4 - Remaining issues (9 files)**:
```python
# Fix .extend(), operator.itemgetter(), etc.
# Estimated time: 30 minutes
```

**Total estimated time**: 2 hours

#### 2B: Complexity Reduction (6 functions)

**For each high-complexity function**:

1. **Analyze control flow**:
   - Identify decision points
   - Find repeated patterns
   - Locate extraction opportunities

2. **Extract helper methods**:
   ```python
   # BEFORE:
   def complex_function(self, data):
       if condition1:
           if condition2:
               # 20 lines of logic
           else:
               # 15 lines of logic
       # More nested conditions...

   # AFTER:
   def complex_function(self, data):
       if condition1:
           return self._handle_condition1(data, condition2)
       return self._handle_default(data)

   def _handle_condition1(self, data, condition2):
       if condition2:
           return self._process_case_a(data)
       return self._process_case_b(data)
   ```

3. **Use early returns**:
   ```python
   # BEFORE:
   def function(self, value):
       result = None
       if value:
           if value > 0:
               result = process(value)
       return result

   # AFTER:
   def function(self, value):
       if not value or value <= 0:
           return None
       return process(value)
   ```

**Estimated time per function**: 30-45 minutes
**Total estimated time**: 3-4 hours

---

### Phase 3: Coverage Recovery (Medium Priority)

**Goal**: Restore coverage to 77%+ baseline

1. **Generate detailed coverage report**:
   ```bash
   python -m pytest --cov=acb --cov-report=html --cov-report=term-missing
   open htmlcov/index.html  # Review in browser
   ```

2. **Identify priority modules**:
   - Core modules with <50% coverage
   - Recently modified files
   - High-value business logic

3. **Add tests incrementally**:
   - Target 5-10 additional tests per day
   - Focus on uncovered branches
   - Aim for 2-3% coverage increase per session

4. **Update baseline**:
   ```bash
   # After reaching 50%
   python -c "import json; data = json.load(open('.coverage-ratchet.json')); data['baseline'] = 50.0; data['current_minimum'] = 50.0; json.dump(data, open('.coverage-ratchet.json', 'w'), indent=2)"
   ```

**Estimated time**: Ongoing, 1-2 hours per session

---

### Phase 4: Prevention Measures

**Goal**: Prevent quality regressions

1. **Enable pre-commit hooks locally**:
   ```bash
   pre-commit install
   pre-commit install --hook-type pre-push
   ```

2. **Add CI/CD quality gates**:
   - Require refurb passing
   - Require complexipy passing (threshold: 15)
   - Require coverage > baseline

3. **Set up automated AI fixing**:
   - Once Phase 1 complete, enable by default
   - Configure to run on pre-commit

4. **Regular quality reviews**:
   - Weekly crackerjack runs
   - Monthly coverage audits
   - Quarterly complexity refactoring sprints

---

## Timeline and Effort Estimates

| Phase | Task | Estimated Time | Dependencies |
|-------|------|----------------|--------------|
| 1 | Debug AI auto-fix | 2-4 hours | None |
| 2A | Fix refurb violations | 2 hours | None |
| 2B | Reduce complexity | 3-4 hours | None |
| 3 | Coverage recovery | Ongoing | None |
| 4 | Prevention setup | 1 hour | Phase 1 complete |

**Total immediate effort**: 8-11 hours (Phases 1, 2A, 2B)
**Ongoing effort**: 1-2 hours per week (Phase 3)

---

## Success Metrics

1. **AI Auto-Fix Working**:
   - ✅ Intentional violation gets fixed automatically
   - ✅ Agent execution logs appear in `~/.crackerjack/intelligence/`
   - ✅ Code modifications visible in git status

2. **Quality Hooks Passing**:
   - ✅ All 33 refurb issues resolved
   - ✅ All 6 complexity violations resolved
   - ✅ `python -m crackerjack --comp` passes cleanly

3. **Coverage Restored**:
   - ✅ Coverage ≥ 77.89% (original baseline)
   - ✅ No modules with <40% coverage
   - ✅ Coverage ratchet updated

4. **Quality Maintained**:
   - ✅ Pre-commit hooks enabled
   - ✅ CI/CD quality gates active
   - ✅ No new violations in past 30 days

---

## Next Steps - Recommended Order

1. **Immediate** (Today):
   - [ ] Debug AI auto-fix workflow (2-4 hours)
   - [ ] Apply refurb fixes manually (2 hours)
   - [ ] Run `python -m crackerjack -t` to verify fixes

2. **Short-term** (This week):
   - [ ] Refactor high-complexity functions (3-4 hours)
   - [ ] Generate coverage report and identify gaps
   - [ ] Enable pre-commit hooks

3. **Medium-term** (Next 2 weeks):
   - [ ] Add tests to restore coverage to 60%+
   - [ ] Set up CI/CD quality gates
   - [ ] Document quality standards for team

4. **Long-term** (Ongoing):
   - [ ] Continue coverage improvements (target: 80%+)
   - [ ] Monthly quality reviews
   - [ ] Quarterly refactoring sprints

---

## Questions for Consideration

1. **AI Auto-Fix Priority**: Should we fix AI auto-fix first, or proceed with manual fixes?
   - **Recommendation**: Fix AI auto-fix first - it will prevent future regressions

2. **Complexity Threshold**: Should we keep threshold at 15 or raise temporarily?
   - **Recommendation**: Keep at 15, refactor the 6 violations

3. **Coverage Target**: What's realistic coverage target given codebase size?
   - **Recommendation**: 70-75% is realistic for framework, 80%+ for core modules

4. **Test Strategy**: Unit tests vs integration tests for coverage recovery?
   - **Recommendation**: Mix - unit tests for adapters, integration for services

---

## Files Generated

- `crackerjack-autofix-investigation.md`: Detailed investigation report
- `acb-quality-remediation-plan.md`: This remediation plan (you are here)

---

## Contact & Questions

For questions about this plan:
- Review investigation report: `crackerjack-autofix-investigation.md`
- Check crackerjack logs: `~/.crackerjack/intelligence/execution_log.jsonl`
- Verify MCP servers: `lsof -i :8675 -i :8676`
