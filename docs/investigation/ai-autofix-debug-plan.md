# AI Auto-Fix Debug & Implementation Plan

**Project**: Crackerjack Quality Automation Framework
**Issue**: `--ai-fix` flag recognized but AI agent workflow not engaging
**Created**: October 3, 2025
**Status**: Ready for execution

______________________________________________________________________

## Executive Summary

The AI auto-fix feature in crackerjack is partially implemented but not fully functional. The workflow correctly identifies when AI fixing is needed (hook failures), but the AI agent never executes iterations to fix the code.

**Evidence**:

- ✅ `--ai-fix` flag is recognized
- ✅ Environment setup occurs (`setup_ai_agent_env()`)
- ✅ `_determine_ai_fixing_needed()` returns `True` on failures
- ❌ No AI agent iterations occur
- ❌ No code modifications made
- ❌ No execution logs in `~/.crackerjack/intelligence/`

**Hypothesis**: The `options.ai_fix` flag is not properly checked before executing the AI fixing workflow, OR there's a gate condition inside `_execute_ai_fixing_workflow()` preventing agent execution.

______________________________________________________________________

## Phase 1: Investigation & Root Cause Analysis

### 1.1 Examine Workflow Orchestrator

**File**: `../crackerjack/crackerjack/core/workflow_orchestrator.py`

**Key Functions to Investigate**:

```bash
# Navigate to crackerjack repo
cd ../crackerjack

# Find the workflow orchestrator
find . -name "workflow_orchestrator.py" -type f

# Extract key function: _determine_ai_fixing_needed
grep -A20 "def _determine_ai_fixing_needed" crackerjack/core/workflow_orchestrator.py

# Extract key function: _execute_ai_fixing_workflow
grep -A50 "def _execute_ai_fixing_workflow" crackerjack/core/workflow_orchestrator.py

# Find all references to options.ai_fix
grep -n "options\.ai_fix" crackerjack/core/workflow_orchestrator.py
```

**Expected Finding**: Should find where `options.ai_fix` is checked

**Red Flag**: If `options.ai_fix` is never checked in workflow orchestrator

### 1.2 Trace Flag Propagation

**File**: `../crackerjack/crackerjack/__main__.py`

```bash
# Find where ai_fix flag is defined
grep -B5 -A10 '"ai_fix"' crackerjack/__main__.py

# Find where it's set up
grep -A15 "def _setup_debug_and_verbose_flags" crackerjack/__main__.py

# Find where environment is configured
grep -A20 "def setup_ai_agent_env" crackerjack/__main__.py

# Check how options are passed to workflow
grep -A10 "WorkflowOrchestrator" crackerjack/__main__.py
```

**Expected Finding**: Options object should be passed to workflow orchestrator with `ai_fix` attribute

### 1.3 Check Agent Coordinator Initialization

**Files**:

- `../crackerjack/crackerjack/core/autofix_coordinator.py`
- `../crackerjack/crackerjack/agents/coordinator.py`

```bash
# Find agent coordinator files
find . -name "*coordinator*.py" -path "*/agents/*" -o -path "*/core/*"

# Check initialization requirements
grep -A30 "class.*Coordinator" crackerjack/core/autofix_coordinator.py
grep -A30 "class.*Coordinator" crackerjack/agents/coordinator.py

# Find where coordinator is instantiated
grep -n "Coordinator(" crackerjack/core/workflow_orchestrator.py
```

**Expected Finding**: Coordinator should be initialized inside `_execute_ai_fixing_workflow()`

**Red Flag**: If coordinator initialization has unmet dependencies or fails silently

### 1.4 Examine Agent Execution Loop

```bash
# Find the iteration loop
grep -B5 -A30 "for.*iteration\|while.*iteration" crackerjack/core/workflow_orchestrator.py

# Find agent invocation
grep -n "agent.*execute\|coordinator.*run\|coordinator.*fix" crackerjack/core/workflow_orchestrator.py

# Check logging statements
grep -n "iteration\|AI.*fix\|agent.*start" crackerjack/core/workflow_orchestrator.py
```

**Expected Finding**: Should find a loop that calls agent methods

**Red Flag**: If loop exists but never executes, or agent methods never called

______________________________________________________________________

## Phase 2: Diagnosis - Key Questions

Work through these questions systematically:

### Q1: Is `options.ai_fix` checked before AI workflow execution?

**Test**:

```python
# In workflow_orchestrator.py, find this pattern:
def _execute_ai_fixing_workflow(...):
    if not self.options.ai_fix:  # <-- Does this exist?
        return
    # ... rest of workflow
```

**If NO**: This is likely the bug. The workflow runs but immediately exits because the flag isn't checked.

**If YES**: Continue to Q2.

### Q2: Is the agent coordinator properly initialized?

**Test**:

```python
# Look for this pattern in _execute_ai_fixing_workflow:
coordinator = AgentCoordinator(...)  # Does this succeed?
issues = self._collect_issues()  # Are issues collected?

# Check for error handling
try:
    coordinator = AgentCoordinator(...)
except Exception as e:
    # Is this caught and silently ignored?
    pass
```

**If coordinator init fails silently**: This is the bug.

**If coordinator initializes**: Continue to Q3.

### Q3: Are the agent execution conditions met?

**Test**:

```python
# Look for conditions like:
if issues and coordinator:
    await coordinator.fix_issues(issues)  # Does this execute?

# Or:
if len(issues) > 0:
    # ... fixing logic
else:
    return  # Early exit?
```

**If conditions aren't met**: Issues list might be empty or wrong format.

### Q4: Is the MCP connection required and failing?

**Test**:

```bash
# Check if agent needs MCP client
grep -n "mcp.*client\|MCP.*Client" crackerjack/agents/coordinator.py

# Check connection requirements
grep -n "localhost:8676\|websocket\|connect" crackerjack/agents/*.py
```

**If MCP required but not connected**: This could be the bug.

### Q5: Are there any silent exceptions?

**Test**:

```python
# Look for broad exception handlers:
try:
    await self._execute_ai_fixing_workflow(...)
except Exception:
    pass  # <-- Silent failure!

# Or:
try:
    result = await coordinator.run()
except:  # <-- Even worse, bare except!
    return
```

**If found**: This is definitely the bug.

______________________________________________________________________

## Phase 3: Common Fix Patterns

Based on investigation, here are likely fixes:

### Fix Pattern A: Missing `options.ai_fix` Check

**Location**: `crackerjack/core/workflow_orchestrator.py:_execute_ai_fixing_workflow()`

**Current Code** (likely):

```python
async def _execute_ai_fixing_workflow(self, options, iteration: int):
    """Execute AI-powered fixing workflow."""
    # No check of options.ai_fix!

    self._initialize_ai_fixing_phase(options)
    # ... rest of workflow
```

**Fixed Code**:

```python
async def _execute_ai_fixing_workflow(self, options, iteration: int):
    """Execute AI-powered fixing workflow."""
    # Add guard clause
    if not getattr(options, "ai_fix", False):
        self.logger.debug("AI fix not enabled, skipping agent workflow")
        return

    self._initialize_ai_fixing_phase(options)
    # ... rest of workflow
```

### Fix Pattern B: Silent Exception in Agent Initialization

**Location**: `crackerjack/core/workflow_orchestrator.py:_setup_ai_fixing_workflow()`

**Current Code** (likely):

```python
async def _setup_ai_fixing_workflow(self):
    try:
        coordinator = AgentCoordinator(...)
        issues = await self._collect_issues()
        return coordinator, issues
    except Exception:
        # Silent failure!
        return None, []
```

**Fixed Code**:

```python
async def _setup_ai_fixing_workflow(self):
    try:
        coordinator = AgentCoordinator(...)
        issues = await self._collect_issues()
        return coordinator, issues
    except Exception as e:
        # Log the error so we know what failed
        self.logger.error(f"Failed to setup AI fixing: {e}")
        self.logger.debug(f"Traceback: {traceback.format_exc()}")
        return None, []
```

### Fix Pattern C: Missing Agent Execution Call

**Location**: `crackerjack/core/workflow_orchestrator.py:_execute_ai_fixing_workflow()`

**Current Code** (likely):

```python
async def _execute_ai_fixing_workflow(self, options, iteration: int):
    coordinator, issues = await self._setup_ai_fixing_workflow()

    if not coordinator or not issues:
        return

    # Missing: actual agent execution!
    # The workflow sets up but never runs the agent
```

**Fixed Code**:

```python
async def _execute_ai_fixing_workflow(self, options, iteration: int):
    coordinator, issues = await self._setup_ai_fixing_workflow()

    if not coordinator or not issues:
        self.logger.warning("No coordinator or issues, skipping AI fix")
        return

    # Add the missing execution
    self.logger.info(f"Starting AI fix iteration {iteration} with {len(issues)} issues")
    results = await coordinator.fix_issues(issues)
    self.logger.info(f"AI fix iteration {iteration} complete: {results}")

    return results
```

### Fix Pattern D: Environment Variable Not Set

**Location**: `crackerjack/__main__.py:setup_ai_agent_env()`

**Current Code** (likely):

```python
def setup_ai_agent_env(ai_fix: bool, debug: bool):
    """Setup environment for AI agents."""
    if ai_fix:
        os.environ["CRACKERJACK_AI_FIX"] = "1"
    # Missing: other required env vars?
```

**Fixed Code**:

```python
def setup_ai_agent_env(ai_fix: bool, debug: bool):
    """Setup environment for AI agents."""
    if ai_fix:
        os.environ["CRACKERJACK_AI_FIX"] = "1"
        os.environ["CRACKERJACK_AI_ENABLED"] = "true"
        os.environ["CRACKERJACK_AGENT_MODE"] = "auto"

        # Ensure MCP connection details are set
        if "CRACKERJACK_MCP_URL" not in os.environ:
            os.environ["CRACKERJACK_MCP_URL"] = "http://localhost:8676/mcp"

    if debug:
        os.environ["CRACKERJACK_DEBUG"] = "1"
```

______________________________________________________________________

## Phase 4: Implementation Steps

### Step 1: Create Feature Branch

```bash
cd ../crackerjack
git checkout -b fix/ai-autofix-engagement
git status  # Ensure clean working directory
```

### Step 2: Apply The Fix

Based on investigation from Phase 1 & 2, apply the appropriate fix pattern from Phase 3.

**Example** (assuming Fix Pattern A):

```bash
# Open the file in editor
code crackerjack/core/workflow_orchestrator.py

# Find _execute_ai_fixing_workflow
# Add the guard clause at the beginning
```

```python
async def _execute_ai_fixing_workflow(self, options, iteration: int):
    """Execute AI-powered fixing workflow."""
    # Add this guard clause
    if not getattr(options, "ai_fix", False):
        self.logger.debug("AI fix not enabled, skipping agent workflow")
        return {"success": False, "reason": "ai_fix_not_enabled", "iterations": 0}

    # Rest of existing code...
```

### Step 3: Add Defensive Logging

Add debug logging at key decision points:

```python
async def _execute_ai_fixing_workflow(self, options, iteration: int):
    if not getattr(options, "ai_fix", False):
        self.logger.debug("AI fix not enabled, skipping agent workflow")
        return

    self.logger.info(f"🤖 AI auto-fix enabled, starting iteration {iteration}")

    coordinator, issues = await self._setup_ai_fixing_workflow()

    if not coordinator:
        self.logger.error("❌ Failed to initialize agent coordinator")
        return

    if not issues:
        self.logger.warning("⚠️  No issues collected for AI fixing")
        return

    self.logger.info(f"📋 Found {len(issues)} issues to fix")

    results = await coordinator.fix_issues(issues)

    self.logger.info(f"✅ AI fix iteration {iteration} complete")

    return results
```

### Step 4: Reinstall Crackerjack

```bash
# From crackerjack repo
cd ../crackerjack

# Install in editable mode
uv pip install -e .

# Verify installation
python -c "import crackerjack; print(crackerjack.__file__)"
# Should show: ../crackerjack/crackerjack/__init__.py (not .venv/lib/...)
```

______________________________________________________________________

## Phase 5: Testing

### Test 1: Create Intentional Violation

```bash
# From ACB project
cd ~/Projects/acb

# Create test file with refurb violation
cat > test_autofix.py << 'EOF'
"""Test file for AI auto-fix."""

def test_function():
    """Function with intentional refurb violations."""
    result = []
    for i in range(10):
        result.append(i * 2)

    # Another violation
    try:
        x = int("not a number")
    except ValueError:
        pass

    return result
EOF

git add test_autofix.py
```

### Test 2: Run Crackerjack With AI Fix

```bash
# Run with maximum verbosity
python -m crackerjack --ai-fix --verbose --ai-debug --run-tests

# Expected output should include:
# - "🤖 AI auto-fix enabled, starting iteration 1"
# - "📋 Found X issues to fix"
# - "✅ AI fix iteration 1 complete"
```

### Test 3: Verify Fix Was Applied

```bash
# Check if test_autofix.py was modified
git diff test_autofix.py

# Expected changes:
# - Loop converted to list comprehension
# - try/except replaced with contextlib.suppress

# Check execution logs
tail -5 ~/.crackerjack/intelligence/execution_log.jsonl

# Should show recent agent execution with success: true
```

### Test 4: Full Quality Run

```bash
# Run comprehensive quality check on ACB
python -m crackerjack --ai-fix --run-tests --verbose

# Should see:
# - Multiple iterations (up to 10)
# - Refurb violations fixed
# - All hooks eventually passing
```

______________________________________________________________________

## Phase 6: Verification Checklist

- [ ] **Code changes made**: `git diff ../crackerjack` shows modifications
- [ ] **Crackerjack reinstalled**: `python -c "import crackerjack; print(crackerjack.__file__)"` shows source repo
- [ ] **Test violation created**: `test_autofix.py` exists with violations
- [ ] **AI agent engaged**: Console output shows "🤖 AI auto-fix enabled"
- [ ] **Issues detected**: Console shows "📋 Found X issues"
- [ ] **Fixes applied**: `git diff test_autofix.py` shows corrections
- [ ] **Execution logged**: `~/.crackerjack/intelligence/execution_log.jsonl` has new entries
- [ ] **Hooks passing**: Final run shows all quality checks pass

______________________________________________________________________

## Phase 7: Documentation & Commit

### Commit Message Template

```
fix(ai): enable AI auto-fix workflow engagement

The --ai-fix flag was recognized but the AI agent workflow
never executed. Root cause: [DESCRIBE ISSUE FOUND].

Changes:
- Add guard clause to check options.ai_fix in _execute_ai_fixing_workflow()
- Add defensive logging at key decision points
- [OTHER CHANGES MADE]

Testing:
- Created intentional violations in test file
- Verified AI agent runs and applies fixes
- Confirmed execution logs are written
- All quality hooks now pass with auto-fix

Fixes: [ISSUE_NUMBER if applicable]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Create Commit

```bash
cd ../crackerjack

# Stage changes
git add crackerjack/core/workflow_orchestrator.py
# ... any other modified files

# Commit with detailed message
git commit -m "$(cat <<'EOF'
fix(ai): enable AI auto-fix workflow engagement

[Use template above with actual details]
EOF
)"

# Push to remote
git push origin fix/ai-autofix-engagement
```

______________________________________________________________________

## Troubleshooting Guide

### Issue: "Module 'crackerjack' not found"

**Solution**:

```bash
cd ../crackerjack
uv pip install -e .
```

### Issue: Still using old code after reinstall

**Solution**:

```bash
# Force reinstall
uv pip uninstall crackerjack
uv pip install -e ../crackerjack
```

### Issue: Agent runs but doesn't fix anything

**Check**:

1. Is MCP server running? `lsof -i :8676`
1. Are issues being collected? Check logs for "📋 Found X issues"
1. Does coordinator.fix_issues() return results?

### Issue: "Permission denied" during testing

**Solution**:

```bash
# Ensure test file is writable
chmod +w test_autofix.py

# Check git isn't blocking changes
git status
```

### Issue: No execution logs written

**Check**:

```bash
# Verify directory exists and is writable
ls -la ~/.crackerjack/intelligence/
touch ~/.crackerjack/intelligence/test.log
rm ~/.crackerjack/intelligence/test.log
```

______________________________________________________________________

## Success Criteria

✅ **AI Auto-Fix Functional** when all of these are true:

1. **Flag recognized**: `python -m crackerjack --ai-fix` starts workflow
1. **Agent engaged**: Console shows "🤖 AI auto-fix enabled"
1. **Issues detected**: Console shows "📋 Found X issues"
1. **Iterations run**: Console shows multiple iteration cycles
1. **Code modified**: `git diff` shows actual changes to source files
1. **Logs written**: `~/.crackerjack/intelligence/execution_log.jsonl` updated
1. **Quality achieved**: Final run shows all hooks passing

______________________________________________________________________

## Rollback Procedure

If the fix causes problems:

```bash
cd ../crackerjack

# Discard changes
git checkout crackerjack/core/workflow_orchestrator.py
# ... other modified files

# Reinstall original
uv pip install -e .

# Or revert to main
git checkout main
uv pip install -e .
```

______________________________________________________________________

## Additional Resources

**Log Locations**:

- Agent execution: `~/.crackerjack/intelligence/execution_log.jsonl`
- Agent metrics: `~/.crackerjack/intelligence/agent_metrics.json`
- Learning insights: `~/.crackerjack/intelligence/learning_insights.json`

**Server Status**:

```bash
# Check MCP servers
lsof -i :8676 :8678

# Check WebSocket server
lsof -i :8675

# Check all crackerjack processes
ps aux | grep crackerjack
```

**Debug Output**:

```bash
# Maximum verbosity
python -m crackerjack --ai-fix --ai-debug --verbose --debug

# Or with orchestrated mode
python -m crackerjack --ai-fix --orchestrated --verbose
```

______________________________________________________________________

## Next Steps After Success

Once AI auto-fix is working:

1. **Apply to ACB quality issues**:

   ```bash
   cd ~/Projects/acb
   python -m crackerjack --ai-fix --run-tests --verbose
   ```

1. **Document the feature**: Update crackerjack README with AI auto-fix usage

1. **Enable by default** (optional): Consider making `--ai-fix` default behavior

1. **CI/CD integration**: Add AI auto-fix to pre-commit hooks or CI pipeline

1. **Monitor performance**: Track agent success rate and iteration counts

______________________________________________________________________

**End of Debug Plan**
