# Workflow Engine Refactoring Plan

## Current Complexity Analysis

### Critical Functions
1. **`execute_step` (line 248)**: Simple function with low complexity - actually **NOT** the problem
2. **`_execute_step_with_retry` (line 204)**: Complexity ~18 - needs refactoring
3. **`execute` (line 53)**: Main workflow execution - likely complexity 42+ due to nested loops and conditionals

### Actual Complexity Sources

**`execute` method complexity breakdown:**
- Main while loop with multiple nested conditions (line 79)
- Step completion tracking logic (lines 88-101)
- Step task execution loop (lines 104-109)
- Result processing loop with nested error handling (lines 112-138)
- State transition logic (lines 140-143, 145-150)
- Multiple exception handlers

**`_execute_step_with_retry` complexity breakdown:**
- Retry loop with conditional logic (line 213)
- Nested try-except blocks (lines 214-238)
- State checking and error handling
- Exponential backoff calculation

## Refactoring Strategy

### 1. Extract Step Execution Phases (for `execute`)

**Current monolithic method → Separate phase methods:**

```python
# Phase 1: Initialize workflow
async def _initialize_workflow_execution(workflow, context) -> tuple[WorkflowResult, dict, set]

# Phase 2: Find and execute ready steps
async def _execute_ready_steps(workflow, completed, failed, context) -> list[tuple[str, StepResult]]

# Phase 3: Process step results
def _process_step_results(workflow, step_results, completed, failed, result) -> bool

# Phase 4: Determine final state
def _determine_final_workflow_state(result, failed_steps)

# Phase 5: Finalize workflow
def _finalize_workflow_execution(workflow_id, result, start_time)
```

### 2. Simplify Retry Logic (for `_execute_step_with_retry`)

**Extract retry coordination:**

```python
# Retry handler with clear separation
class RetryHandler:
    async def execute_with_retry(step, context) -> StepResult
    def _calculate_backoff_delay(retry_count, base_delay) -> float
    def _should_retry(retry_count, max_retries) -> bool
    async def _execute_single_attempt(step, context) -> StepResult
```

### 3. State Machine Pattern

**Step lifecycle states:**
```python
class StepExecutionPhase(Enum):
    INITIALIZING = "initializing"
    EXECUTING = "executing"
    VALIDATING = "validating"
    RETRYING = "retrying"
    FINALIZING = "finalizing"
```

### 4. Early Returns and Guard Clauses

Replace nested conditionals with early returns:
- Check for empty ready steps → return early
- Check for workflow failure → break early
- Check for deadlock → break early

## Implementation Plan

### Step 1: Extract `execute` method phases
1. `_initialize_workflow_execution` - Setup result and tracking
2. `_find_and_execute_ready_steps` - Get ready steps and create tasks
3. `_wait_for_step_completion` - Await tasks and collect results
4. `_handle_step_failure` - Process failed steps
5. `_check_workflow_deadlock` - Detect and handle deadlocks
6. `_finalize_workflow_result` - Set final state and timing

### Step 2: Refactor `_execute_step_with_retry`
1. Extract retry loop into separate method
2. Create `_execute_single_step_attempt` method
3. Extract backoff calculation
4. Simplify error handling with early returns

### Step 3: Verify complexity
- Run complexity analysis on all methods
- Ensure all methods ≤13 complexity
- Maintain test coverage

## Expected Complexity Reduction

### Before:
- `execute`: ~42 complexity
- `_execute_step_with_retry`: ~18 complexity

### After (target):
- `execute`: ≤10 complexity (main orchestration only)
- `_initialize_workflow_execution`: ≤5
- `_find_and_execute_ready_steps`: ≤8
- `_wait_for_step_completion`: ≤10
- `_handle_step_failure`: ≤5
- `_check_workflow_deadlock`: ≤5
- `_finalize_workflow_result`: ≤5
- `_execute_step_with_retry`: ≤8 complexity
- `_execute_single_step_attempt`: ≤5
- `_calculate_retry_delay`: ≤3

## Quality Assurance

1. **Type Safety**: Add comprehensive type hints for all extracted methods
2. **Test Coverage**: Run existing tests to ensure behavior preserved
3. **Async Patterns**: Maintain proper async/await usage
4. **Error Handling**: Preserve all error handling semantics
5. **Performance**: No performance regression from refactoring

## Success Criteria

- ✅ All methods have complexity ≤13
- ✅ All existing tests pass
- ✅ Type hints added for all new methods
- ✅ Workflow execution semantics preserved
- ✅ Error handling behavior unchanged
- ✅ Performance maintained or improved
