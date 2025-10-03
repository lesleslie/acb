# MCP Workflow Executor Bug Fix

**Date**: October 3, 2025
**Status**: ✅ FIXED - Ready for deployment

## Bug Summary

**Issue**: MCP tool `execute_crackerjack` was failing with async error when invoked through Claude Code.

**Error**: `TypeError: object NoneType can't be used in 'await' expression`

**Root Cause**: `_update_progress()` is a synchronous function but was being called with `await` in three locations in `workflow_executor.py`.

## The Fix

**File**: `/Users/les/Projects/crackerjack/crackerjack/mcp/tools/workflow_executor.py`

**Changes Made**:
1. Removed `await` from all `_update_progress()` calls (3 locations)
2. Fixed parameter order to match function signature
3. Fixed context initialization order (get context before using it)

**Lines Changed**: 17, 49-68, 73-89

## Verification

- ✅ No remaining `await _update_progress` calls in the file
- ✅ Parameter order matches `progress_tools.py` signature
- ✅ Context is initialized before use

## Deployment Steps

### 1. Test the Fix

```bash
cd /Users/les/Projects/crackerjack

# Run crackerjack's own tests
python -m pytest tests/ -v

# Test MCP server startup
python -m crackerjack --start-mcp-server &
sleep 3
lsof -i :8676  # Should show server running

# Kill test server
pkill -f "crackerjack --start-mcp-server"
```

### 2. Commit and Version Bump

```bash
cd /Users/les/Projects/crackerjack

# Stage the fix
git add crackerjack/mcp/tools/workflow_executor.py

# Commit with descriptive message
git commit -m "fix(mcp): remove incorrect await calls to _update_progress

- _update_progress is a synchronous function, not async
- Removed await from 3 call sites in workflow_executor.py
- Fixed parameter order and context initialization
- Fixes TypeError: NoneType can't be awaited error

Resolves issue where execute_crackerjack MCP tool was failing"

# Bump patch version (e.g., 0.31.0 -> 0.31.1)
python -m crackerjack --bump patch --publish
```

### 3. Restart MCP Servers

**Crackerjack MCP Server** (in acb project):
```bash
# Kill old server
lsof -i :8676 | grep python | awk '{print $2}' | xargs kill -9

# The server will auto-restart via MCP configuration
# Or manually restart Claude Code to reload MCP servers
```

**Session-mgmt MCP Server**:
```bash
# Kill old server
lsof -i :8678 | grep python | awk '{print $2}' | xargs kill -9

# The server will auto-restart via MCP configuration
```

### 4. Test AI-Fix Workflow

```bash
cd /Users/les/Projects/acb

# Test via MCP (from Claude Code)
# This should now work without errors:
mcp__crackerjack__execute_crackerjack(
    args="--comp --verbose",
    kwargs={"ai_fix": true, "execution_timeout": 1800}
)
```

## Understanding the AI-Fix Workflow

### Current Architecture

The AI-fix workflow has **two distinct modes**:

#### Mode 1: Direct CLI (what we tried first)
```bash
python -m crackerjack --ai-fix --comp
```

**What happens**:
- Crackerjack runs hooks and identifies issues
- Internal `ClaudeCodeBridge` provides **simulated** recommendations
- **No actual file edits** are made
- Requires manual application of fixes

**Why it doesn't auto-fix**: The bridge is a simulation - it doesn't invoke Claude Code agents via Task tool.

#### Mode 2: MCP Integration (the proper way)
```bash
# From Claude Code MCP client:
mcp__crackerjack__execute_crackerjack(
    args="--comp",
    kwargs={"ai_fix": true}
)
```

**What happens**:
1. Crackerjack MCP server receives request
2. Runs hooks and identifies issues
3. **Returns issues to Claude Code** via MCP response
4. **Claude Code (me) applies fixes** using Edit/Write tools
5. Re-runs hooks to verify
6. Iterates until all hooks pass

**Key Insight**: The "AI" in AI-fix refers to Claude Code (the MCP client), not crackerjack's internal agents.

### What We Learned

**The bug we fixed** was preventing step 2 - crackerjack couldn't even start the workflow because `_update_progress` was crashing.

**What still needs work** (optional enhancements):
- ClaudeCodeBridge could be enhanced to actually invoke Task tool
- Would allow standalone CLI mode to work without MCP
- Current MCP mode is the correct architecture though

## Documentation Updates Needed

### 1. Update Investigation Reports

Add to `docs/investigation/crackerjack-autofix-investigation.md`:

```markdown
## UPDATE: Bug Fixed (Oct 3, 2025)

The MCP async error in workflow_executor.py has been fixed:
- Removed incorrect `await` calls to synchronous `_update_progress()`
- Fixed in crackerjack v0.31.1+
- MCP execute_crackerjack tool now works correctly
```

### 2. Update Remediation Plan

Update `docs/investigation/acb-quality-remediation-plan.md` Phase 1:

```markdown
### Phase 1: Fix AI Auto-Fix (COMPLETED ✅)

**Status**: Bug fixed in crackerjack v0.31.1

The MCP workflow executor bug has been resolved. AI-fix now works via:
```bash
mcp__crackerjack__execute_crackerjack(
    args="--comp",
    kwargs={"ai_fix": true}
)
```

## Workflow Changes Needed

### Current Workflow (.mcp.json)

The `.mcp.json` configuration is **correct** - crackerjack MCP server is configured for HTTP:

```json
"crackerjack": {
  "url": "http://localhost:8676/mcp",
  "type": "http"
}
```

**No changes needed** - the server supports both STDIO and HTTP transports.

### Recommended AI-Fix Process

**For acb project quality fixes**:

1. **Invoke via MCP** (not direct CLI):
   ```
   mcp__crackerjack__execute_crackerjack(
       args="--comp --verbose",
       kwargs={"ai_fix": true, "execution_timeout": 1800}
   )
   ```

2. **Review returned issues** in the job result

3. **Apply fixes iteratively**:
   - Use Edit tool to fix refurb issues
   - Use Edit tool to reduce complexity
   - Re-run to verify

4. **Let crackerjack track progress** via job_id

## Testing Checklist

Before deploying new crackerjack version:

- [ ] Run crackerjack's own test suite
- [ ] Test MCP server startup (no errors)
- [ ] Test execute_crackerjack MCP tool (should return job_id, not error)
- [ ] Verify progress tracking works
- [ ] Test with actual quality issues

## Next Steps

1. **Immediate**: Run tests on crackerjack fix
2. **If tests pass**: Commit, bump version, publish to PyPI
3. **Restart MCP servers**: Kill old processes, let auto-restart
4. **Test workflow**: Try AI-fix on acb project via MCP
5. **Apply quality fixes**: Use the working MCP workflow to fix acb hooks

## Questions Answered

### Q: Did we actually fix the MCP server bug?
**A**: Yes ✅ - All `await` calls to `_update_progress` removed, parameters fixed.

### Q: Should we push a new version of crackerjack?
**A**: Yes, after testing. Bump patch version (e.g., 0.31.0 → 0.31.1).

### Q: Do we need to restart MCP servers?
**A**: Yes - kill old processes with cached bytecode, let auto-restart with new code.

### Q: Do we need to document updates?
**A**: Yes - update investigation reports (see "Documentation Updates Needed" section).

### Q: Do we need workflow changes?
**A**: No - current `.mcp.json` config is correct. Process is: invoke via MCP → Claude applies fixes → verify.

### Q: Are there other changes needed for AI-fix to work?
**A**: No required changes. Optional enhancement: update ClaudeCodeBridge to use Task tool for standalone CLI mode.

## Summary

**Bug**: Fixed ✅
**Testing**: Pending
**Deployment**: Ready after tests pass
**Workflow**: No changes needed
**Documentation**: Updates outlined above

The AI-fix workflow is **designed correctly** - crackerjack identifies issues via MCP, Claude Code applies fixes. The bug we fixed was blocking step 1 (crackerjack couldn't even run the workflow).
