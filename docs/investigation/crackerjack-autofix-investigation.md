# Crackerjack Auto-Fix Investigation Report

**Date**: October 3, 2025
**Issue**: AI auto-fix didn't engage during crackerjack run + discrepancy between session-mgmt and direct execution

## Summary

Two critical issues were identified:

1. **MCP Integration Bug**: The session-mgmt:crackerjack-run tool has an async/await error preventing execution
1. **AI Auto-Fix Not Engaging**: The `--ai-fix` flag doesn't trigger automatic fixing iterations

## Detailed Findings

### Issue #1: MCP Server Bug in session-mgmt:crackerjack-run

**Error Message**:

```
"error": "Async execution error: A function returned None instead of an awaitable.
object NoneType can't be used in 'await' expression",
"traceback": "... File \"/Users/les/Projects/crackerjack/crackerjack/mcp/tools/workflow_executor.py\",
line 17, in execute_crackerjack_workflow
    await _update_progress(...)
TypeError: object NoneType can't be used in 'await' expression"
```

**Root Cause**: The `_update_progress()` function in `crackerjack/mcp/tools/workflow_executor.py` is returning `None` instead of an awaitable object.

**Impact**: Session-mgmt integration completely broken - cannot execute crackerjack commands through MCP.

**Location**: `crackerjack/mcp/tools/workflow_executor.py:17`

### Issue #2: AI Auto-Fix Not Engaging

**Observed Behavior**:

- Command: `python -m crackerjack --ai-fix --run-tests --verbose`
- Expected: AI agent should run iterative fixing for refurb and complexipy failures
- Actual: No AI iterations occurred, no agent invocations logged, no code changes made

**Evidence**:

1. **No execution logs**: `~/.crackerjack/intelligence/execution_log.jsonl` shows no entries from Oct 3
1. **No code changes**: `git status` shows only deleted `__pycache__` files, no source code modifications
1. **No iteration output**: Crackerjack output showed failures but no "Iteration 1", "Iteration 2" messages
1. **Services running**: MCP server (port 8675) and WebSocket server confirmed running

**Hook Failures Found**:

- **Refurb**: 33 code quality suggestions (FURB108, FURB118, FURB113, FURB138, FURB107, FURB173)
- **Complexipy**: 6 functions exceeding complexity threshold (16-17 complexity)

### Issue #3: Coverage Discrepancy Explained

**Three Different Coverage Values**:

1. **77.89%**: Baseline from `.coverage-ratchet.json` (last updated Sept 25, 2025)
1. **34.43%**: Reported by session-mgmt:crackerjack-run (stale/cached result)
1. **45.91%**: Actual current coverage from `coverage.json`

**Explanation**:

- The ratchet system uses 77.89% as baseline for regression detection
- Current actual coverage is 45.91% (significant drop since Sept 25)
- Crackerjack correctly flagged: "Coverage decreased from 77.89% to 45.91%"
- Session-mgmt result (34.43%) was likely from cached/stale test run

### Issue #4: Session-Mgmt vs Direct Execution Discrepancy

**Session-mgmt:crackerjack-run output** (Before MCP error):

```
✅ All Pre-commit Hooks Passed (12/12)
✅ Test Suite Passed (166.2s runtime)
✅ Quality Checks Passed (6/6)
Coverage: 34.43%
```

**Direct crackerjack:run output**:

```
✅ Fast Hooks Passed (12/12)
✅ Tests Passed (300.2s runtime)
❌ Refurb Failed (33 issues)
❌ Complexipy Failed (6 functions)
Coverage: 45.91%
```

**Root Cause**: Session-mgmt was reporting cached results before hitting the MCP async error. The direct run showed actual current state.

## Infrastructure Status

**Confirmed Running**:

- MCP Servers: Multiple instances running (pids 73999, 75713)
- WebSocket Server: Running on port 8675 (pid 74292)
- Watchdog Service: Active (pid 74303)

**Not Working**:

- AI auto-fix integration (no agent invocations)
- MCP session-mgmt:crackerjack-run (async error)

## Immediate Action Items

### Critical (Blocking AI Auto-Fix)

1. **Fix MCP async error** in `crackerjack/mcp/tools/workflow_executor.py:17`

   - Ensure `_update_progress()` returns an awaitable
   - Add proper async/await handling

1. **Debug AI auto-fix engagement**

   - Verify `--ai-fix` flag triggers agent initialization
   - Check if agent requires specific MCP connection
   - Add logging to track why agent doesn't engage

### High Priority (Code Quality)

3. **Apply refurb fixes** (33 issues)

   - Replace boolean chains with `in` operator
   - Use `operator.itemgetter()` instead of lambda
   - Use `.extend()` instead of multiple `.append()`
   - Use list comprehensions
   - Replace try/except with `contextlib.suppress()`
   - Use dict merge operator `|`

1. **Address complexity issues** (6 functions > 15)

   - Refactor high-complexity functions
   - Extract helper methods
   - Simplify conditional logic

### Medium Priority (Coverage)

5. **Investigate coverage drop** (77.89% → 45.91%)
   - Identify which modules lost coverage
   - Add missing tests
   - Update coverage baseline in ratchet system

## Technical Details

### AI Auto-Fix Expected Workflow

Per `/crackerjack:run` slash command documentation:

1. **Pre-execution**: Status check, conflict prevention
1. **Fast hooks**: Formatting & basic fixes (retry once if fail)
1. **Full test suite**: Collect ALL test failures
1. **Comprehensive hooks**: Type checking, security, complexity
1. **AI analysis**: Batch fix ALL issues in one coordinated pass
1. **Iterate**: Repeat until all checks pass (max 10 iterations)

### What's Missing

- **No iteration loop**: Direct run executed once and stopped
- **No agent invocation**: No calls to ImportOptimizationAgent or similar
- **No progress updates**: No WebSocket progress messages
- **No code modifications**: Agent should write fixes to source files

## Recommendations

1. **Immediate**: Fix the MCP async error to restore session-mgmt integration
1. **Short-term**: Debug and fix AI auto-fix engagement mechanism
1. **Manual workaround**: Apply refurb and complexipy fixes manually until auto-fix works
1. **Testing**: Add integration tests for AI auto-fix workflow
1. **Documentation**: Update troubleshooting guide with these findings

## Files for Review

- `crackerjack/mcp/tools/workflow_executor.py` (MCP async error)
- `crackerjack/mcp/tools/execution_tools.py` (AI agent initialization)
- `~/.crackerjack/intelligence/execution_log.jsonl` (agent execution history)
- `.coverage-ratchet.json` (coverage baseline tracking)
- `coverage.json` (actual current coverage)
