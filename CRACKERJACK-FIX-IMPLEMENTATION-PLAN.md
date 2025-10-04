# Crackerjack Auto-Fix Implementation Plan

## Executive Summary

**Goal**: Fix the auto-fix workflow in crackerjack to enable actual AI-powered code fixing, improve MCP integration usability, and update documentation.

**Projects Affected**:
- **crackerjack** (primary) - Core auto-fix implementation
- **session-mgmt-mcp** (secondary) - Interface improvements and validation

**Timeline Estimate**: 3-5 days
**Quality Score Target**: 95/100 (production-ready)

---

## Phase 1: Crackerjack Core Fixes

### Task 1.1: Input Validation & Command Mapping

**Location**: `/Users/les/Projects/crackerjack/crackerjack/cli/facade.py`

**Problem**: Users can pass invalid commands like `"--ai-fix -t"` instead of semantic commands.

**Implementation**:
```python
# Add validation function
def validate_command(command: str, args: str) -> tuple[str, list[str]]:
    """Validate command and detect common misuse patterns.

    Returns:
        (validated_command, cleaned_args)

    Raises:
        ValueError: If command is invalid or misused
    """
    # Detect if user put flags in command parameter
    if command.startswith("--"):
        raise ValueError(
            f"Invalid command: {command!r}\n"
            f"Commands should be semantic (e.g., 'test', 'lint', 'check')\n"
            f"Use ai_agent_mode=True parameter for auto-fix, not --ai-fix in command"
        )

    # Validate against known commands
    valid_commands = {"test", "lint", "check", "format", "security", "complexity", "all"}
    if command not in valid_commands:
        raise ValueError(
            f"Unknown command: {command!r}\n"
            f"Valid commands: {', '.join(sorted(valid_commands))}"
        )

    # Parse args and detect --ai-fix misuse
    parsed_args = args.split() if args else []
    if "--ai-fix" in parsed_args:
        raise ValueError(
            "Do not pass --ai-fix in args parameter\n"
            "Use ai_agent_mode=True parameter instead"
        )

    return command, parsed_args
```

**Files to Modify**:
- `crackerjack/cli/facade.py` - Add validation function
- `crackerjack/cli/main.py` - Call validation before execution

**Testing**:
- Test valid commands: `validate_command("test", "")`
- Test invalid: `validate_command("--ai-fix", "-t")` → raises ValueError
- Test misuse: `validate_command("test", "--ai-fix")` → raises ValueError

**Agents to Use**:
- **python-pro** - Implement validation logic
- **code-reviewer** - Review for edge cases

**Verification**:
- **python-pro** - Verify implementation
- **pytest-hypothesis-specialist** - Create property-based tests

---

### Task 1.2: Implement Real AI-Powered Code Fixing

**Location**: `/Users/les/Projects/crackerjack/crackerjack/agents/claude_code_bridge.py`

**Problem**: Current implementation is a stub that never actually modifies code.

**Implementation**:

**Step 1: Create AI Adapter**
```python
# crackerjack/adapters/ai/claude.py (NEW FILE)
from acb.adapters import AdapterMetadata, AdapterStatus, AdapterCapability
from acb.depends import depends
from acb.config import Config

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Claude AI Code Fixer",
    category="ai",
    provider="anthropic",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.AI_OPERATIONS,
    ],
    required_packages=["anthropic>=0.25.0"],
    description="Claude AI integration for code fixing",
)

class ClaudeCodeFixer:
    """Real AI-powered code fixing using Claude API."""

    def __init__(self):
        self._client = None
        self._settings = None

    async def _ensure_client(self):
        """Lazy client initialization."""
        if self._client is None:
            self._settings = depends.get(Config)
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=self._settings.anthropic_api_key
            )
        return self._client

    async def fix_code_issue(
        self,
        file_path: str,
        issue_description: str,
        code_context: str,
        fix_type: str,
    ) -> dict[str, Any]:
        """Generate code fix using Claude AI.

        Args:
            file_path: Path to file with issue
            issue_description: Description of the issue
            code_context: Relevant code context
            fix_type: Type of fix (refurb, complexity, etc.)

        Returns:
            {
                "success": bool,
                "fixed_code": str,
                "explanation": str,
                "confidence": float,
            }
        """
        client = await self._ensure_client()

        prompt = self._build_fix_prompt(
            file_path, issue_description, code_context, fix_type
        )

        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_fix_response(response)

    def _build_fix_prompt(self, file_path, issue, context, fix_type):
        """Build prompt for Claude API."""
        return f"""Fix the following code issue:

File: {file_path}
Issue Type: {fix_type}
Issue: {issue}

Current Code:
```python
{context}
```

Provide:
1. Fixed code
2. Explanation of changes
3. Confidence score (0-1)

Format response as JSON:
{{
    "fixed_code": "...",
    "explanation": "...",
    "confidence": 0.95
}}
"""

    def _parse_fix_response(self, response) -> dict[str, Any]:
        """Parse Claude's response."""
        import json
        content = response.content[0].text

        # Extract JSON from response
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
        else:
            json_str = content

        data = json.loads(json_str)
        return {
            "success": True,
            "fixed_code": data["fixed_code"],
            "explanation": data["explanation"],
            "confidence": data.get("confidence", 0.8),
        }
```

**Step 2: Update ClaudeCodeBridge**
```python
# crackerjack/agents/claude_code_bridge.py
from crackerjack.adapters.ai.claude import ClaudeCodeFixer

class ClaudeCodeBridge:
    def __init__(self):
        self.ai_fixer = ClaudeCodeFixer()

    async def consult_on_issue(self, issue_context):
        """Actually fix the issue using Claude AI."""
        result = await self.ai_fixer.fix_code_issue(
            file_path=issue_context.file_path,
            issue_description=issue_context.description,
            code_context=issue_context.code_snippet,
            fix_type=issue_context.category,
        )

        if result["success"] and result["confidence"] > 0.7:
            # Apply the fix to the file
            self._apply_fix_to_file(
                issue_context.file_path,
                result["fixed_code"]
            )

        return result
```

**Step 3: Add File Modification Service**
```python
# crackerjack/services/file_modifier.py (NEW FILE)
from pathlib import Path
from typing import Optional
import difflib

class SafeFileModifier:
    """Safely modify files with backup and validation."""

    async def apply_fix(
        self,
        file_path: str,
        original_content: str,
        fixed_content: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Apply code fix with safety checks.

        Args:
            file_path: Path to file
            original_content: Original code
            fixed_content: Fixed code
            dry_run: If True, don't actually modify file

        Returns:
            {
                "success": bool,
                "diff": str,
                "backup_path": Optional[str],
            }
        """
        # Generate diff
        diff = self._generate_diff(original_content, fixed_content)

        if dry_run:
            return {
                "success": True,
                "diff": diff,
                "backup_path": None,
                "dry_run": True,
            }

        # Create backup
        backup_path = self._create_backup(file_path)

        try:
            # Write fixed content
            Path(file_path).write_text(fixed_content, encoding="utf-8")

            return {
                "success": True,
                "diff": diff,
                "backup_path": backup_path,
            }
        except Exception as e:
            # Restore from backup on error
            if backup_path:
                self._restore_backup(file_path, backup_path)
            raise

    def _generate_diff(self, original, fixed):
        """Generate unified diff."""
        return "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                fixed.splitlines(),
                lineterm="",
            )
        )

    def _create_backup(self, file_path: str) -> str:
        """Create backup file."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.backup_{timestamp}"

        original = Path(file_path).read_text(encoding="utf-8")
        Path(backup_path).write_text(original, encoding="utf-8")

        return backup_path
```

**Files to Create**:
- `crackerjack/adapters/ai/__init__.py`
- `crackerjack/adapters/ai/claude.py`
- `crackerjack/services/file_modifier.py`

**Files to Modify**:
- `crackerjack/agents/claude_code_bridge.py`
- `crackerjack/agents/coordinator.py`

**Configuration Required**:
```yaml
# settings/adapters.yml
ai: claude

# settings/secrets/anthropic.yml
api_key: ${ANTHROPIC_API_KEY}
model: claude-sonnet-4-5-20250929
```

**Agents to Use**:
- **ai-engineer** - Design AI adapter architecture
- **python-pro** - Implement Claude API integration
- **acb-specialist** - Ensure ACB patterns followed
- **security-auditor** - Review API key handling

**Verification**:
- **code-reviewer** - Review implementation quality
- **python-pro** - Verify error handling and edge cases

---

### Task 1.3: Implement Iteration Loop

**Location**: `/Users/les/Projects/crackerjack/crackerjack/workflows/auto_fix.py`

**Problem**: No iteration loop to re-run checks after fixes.

**Implementation**:
```python
# crackerjack/workflows/auto_fix.py
from dataclasses import dataclass
from typing import List

@dataclass
class FixIteration:
    """Single iteration of the fix cycle."""
    iteration_num: int
    hooks_run: List[str]
    issues_found: int
    fixes_applied: int
    fixes_successful: int
    hooks_passing: List[str]
    hooks_failing: List[str]

class AutoFixWorkflow:
    """Iterative auto-fix workflow."""

    MAX_ITERATIONS = 10
    CONVERGENCE_THRESHOLD = 0  # No new fixes needed

    async def run(self, command: str, max_iterations: int = None) -> dict:
        """Run iterative auto-fix workflow.

        Args:
            command: Semantic command (test, lint, check, etc.)
            max_iterations: Max fix iterations (default: 10)

        Returns:
            {
                "success": bool,
                "iterations": List[FixIteration],
                "total_fixes": int,
                "final_status": str,
            }
        """
        max_iter = max_iterations or self.MAX_ITERATIONS
        iterations = []

        for i in range(1, max_iter + 1):
            logger.info(f"🔄 Iteration {i}/{max_iter}")

            # Run hooks and collect failures
            hook_results = await self._run_hooks(command)

            # If all passing, we're done!
            if hook_results["all_passing"]:
                logger.info("✅ All hooks passing - convergence achieved!")
                break

            # Apply fixes for failures
            fix_results = await self._apply_fixes(hook_results["failures"])

            # Record iteration
            iteration = FixIteration(
                iteration_num=i,
                hooks_run=hook_results["hooks_run"],
                issues_found=len(hook_results["failures"]),
                fixes_applied=fix_results["fixes_applied"],
                fixes_successful=fix_results["fixes_successful"],
                hooks_passing=hook_results["passing"],
                hooks_failing=hook_results["failing"],
            )
            iterations.append(iteration)

            # Check for convergence (no new fixes possible)
            if fix_results["fixes_applied"] == 0:
                logger.warning("⚠️  No fixes applied - cannot make progress")
                break

        return {
            "success": iterations[-1].hooks_passing == iterations[-1].hooks_run,
            "iterations": iterations,
            "total_fixes": sum(it.fixes_successful for it in iterations),
            "final_status": "converged" if hook_results["all_passing"] else "incomplete",
        }

    async def _run_hooks(self, command: str) -> dict:
        """Run pre-commit hooks and collect results."""
        # Use existing hook runner
        from crackerjack.hooks import HookRunner
        runner = HookRunner()
        results = await runner.run_all(command)

        return {
            "hooks_run": [h.name for h in results],
            "passing": [h.name for h in results if h.passed],
            "failing": [h.name for h in results if not h.passed],
            "failures": [h for h in results if not h.passed],
            "all_passing": all(h.passed for h in results),
        }

    async def _apply_fixes(self, failures: List) -> dict:
        """Apply AI fixes for all failures."""
        from crackerjack.agents.coordinator import EnhancedAgentCoordinator
        coordinator = EnhancedAgentCoordinator()

        fixes_applied = 0
        fixes_successful = 0

        for failure in failures:
            try:
                result = await coordinator.coordinate_fix(failure)
                if result["action_taken"]:
                    fixes_applied += 1
                    if result["success"]:
                        fixes_successful += 1
            except Exception as e:
                logger.error(f"Fix failed for {failure.hook_name}: {e}")

        return {
            "fixes_applied": fixes_applied,
            "fixes_successful": fixes_successful,
        }
```

**Files to Create**:
- `crackerjack/workflows/__init__.py`
- `crackerjack/workflows/auto_fix.py`

**Files to Modify**:
- `crackerjack/cli/main.py` - Use AutoFixWorkflow when ai_agent_mode=True

**Agents to Use**:
- **python-pro** - Implement iteration logic
- **refactoring-specialist** - Optimize workflow structure

**Verification**:
- **code-reviewer** - Review loop logic and convergence
- **qa-strategist** - Design test strategy for iteration workflow

---

### Task 1.4: Update CLI Documentation

**Location**: `/Users/les/Projects/crackerjack/README.md`, CLI help text

**Updates Needed**:

**README.md**:
```markdown
## Auto-Fix Usage

### Basic Usage

```bash
# Run tests with AI-powered auto-fix
python -m crackerjack test --ai-fix

# Run all quality checks with auto-fix
python -m crackerjack check --ai-fix

# Comprehensive fix with verbose output
python -m crackerjack all --ai-fix --verbose
```

### MCP Integration

When using via MCP tools:

```python
# ✅ CORRECT - Use semantic command + ai_agent_mode parameter
crackerjack_run(command="test", ai_agent_mode=True)

# ❌ WRONG - Don't put flags in command
crackerjack_run(command="--ai-fix -t")  # This won't work!
```

### Configuration

Auto-fix requires:
1. Anthropic API key: `export ANTHROPIC_API_KEY=sk-...`
2. Configuration file: `settings/adapters.yml`
```yaml
ai: claude
```

### How It Works

1. **Run Hooks**: Execute pre-commit hooks to detect issues
2. **Detect Failures**: Parse hook output for failures
3. **AI Analysis**: Send issues to Claude AI for fix generation
4. **Apply Fixes**: Safely modify files with backups
5. **Verify**: Re-run hooks to confirm fixes work
6. **Iterate**: Repeat until all hooks pass or max iterations reached

Default: 10 iterations max, stops when all hooks pass.

### Safety Features

- **Automatic backups**: `.backup_TIMESTAMP` files created
- **Dry-run mode**: `--dry-run` to preview fixes
- **Confidence thresholds**: Only applies fixes with >70% confidence
- **Validation**: Runs hooks after each fix to verify
```

**CLI Help Text** (`crackerjack/cli/main.py`):
```python
@click.option(
    "--ai-fix",
    is_flag=True,
    help=(
        "Enable AI-powered auto-fixing. "
        "Iteratively fixes code issues using Claude AI. "
        "Requires ANTHROPIC_API_KEY environment variable. "
        "Max 10 iterations, stops when all hooks pass."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview fixes without modifying files (implies --ai-fix)",
)
@click.option(
    "--max-iterations",
    type=int,
    default=10,
    help="Maximum auto-fix iterations (default: 10)",
)
```

**Files to Modify**:
- `README.md`
- `crackerjack/cli/main.py`
- `docs/AUTO_FIX_GUIDE.md` (new file)

**Agents to Use**:
- **documentation-specialist** - Write comprehensive docs
- **tutorial-engineer** - Create step-by-step guides

**Verification**:
- **content-designer** - Review documentation clarity
- **python-pro** - Verify code examples work

---

## Phase 2: Session-Mgmt-MCP Improvements

### Task 2.1: Add MCP Tool Input Validation

**Location**: `/Users/les/Projects/session-mgmt-mcp/session_mgmt_mcp/tools/crackerjack_tools.py`

**Implementation**:
```python
# In crackerjack_tools.py, update the tool registration

@mcp.tool()  # type: ignore[misc]
async def crackerjack_run(
    command: str,
    args: str = "",
    working_directory: str = ".",
    timeout: int = 300,
    ai_agent_mode: bool = False,
) -> str:
    """Run crackerjack with enhanced analytics.

    Args:
        command: Semantic command name (test, lint, check, format, security, all)
        args: Additional arguments (NOT including --ai-fix)
        working_directory: Working directory
        timeout: Timeout in seconds
        ai_agent_mode: Enable AI-powered auto-fix (replaces --ai-fix flag)

    Examples:
        # ✅ Correct usage
        crackerjack_run(command="test", ai_agent_mode=True)
        crackerjack_run(command="check", args="--verbose", ai_agent_mode=True)

        # ❌ Wrong usage
        crackerjack_run(command="--ai-fix -t")  # Will raise ValueError!

    Returns:
        Formatted execution results

    Raises:
        ValueError: If command is invalid or --ai-fix in wrong place
    """
    # Validate command parameter
    valid_commands = {"test", "lint", "check", "format", "security", "complexity", "all"}

    if command.startswith("--"):
        return (
            f"❌ **Invalid Command**: {command!r}\n\n"
            f"**Error**: Commands should be semantic names, not flags.\n\n"
            f"**Valid commands**: {', '.join(sorted(valid_commands))}\n\n"
            f"**Correct usage**:\n"
            f"```python\n"
            f"crackerjack_run(command='test', ai_agent_mode=True)\n"
            f"```\n\n"
            f"**Not**:\n"
            f"```python\n"
            f"crackerjack_run(command='--ai-fix -t')  # Wrong!\n"
            f"```"
        )

    if command not in valid_commands:
        return (
            f"❌ **Unknown Command**: {command!r}\n\n"
            f"**Valid commands**: {', '.join(sorted(valid_commands))}\n\n"
            f"**Did you mean**: {_suggest_command(command, valid_commands)}"
        )

    # Check for --ai-fix in args
    if "--ai-fix" in args:
        return (
            "❌ **Invalid Args**: Found '--ai-fix' in args parameter\n\n"
            "**Use instead**: Set `ai_agent_mode=True` parameter\n\n"
            "**Correct**:\n"
            "```python\n"
            f"crackerjack_run(command='{command}', ai_agent_mode=True)\n"
            "```"
        )

    # Proceed with validated inputs
    return await _crackerjack_run_impl(
        command, args, working_directory, timeout, ai_agent_mode
    )

def _suggest_command(invalid: str, valid: set[str]) -> str:
    """Suggest closest valid command using fuzzy matching."""
    from difflib import get_close_matches
    matches = get_close_matches(invalid, valid, n=1, cutoff=0.6)
    return matches[0] if matches else "check"
```

**Files to Modify**:
- `session_mgmt_mcp/tools/crackerjack_tools.py`

**Agents to Use**:
- **python-pro** - Implement validation and suggestions
- **api-security-specialist** - Review input validation security

**Verification**:
- **code-reviewer** - Review error messages clarity
- **python-pro** - Test all error paths

---

### Task 2.2: Update MCP Documentation

**Location**: `/Users/les/Projects/session-mgmt-mcp/README.md`

**Updates**:
```markdown
## Crackerjack Integration

### Correct Usage

```python
# ✅ Run tests with AI auto-fix
await crackerjack_run(command="test", ai_agent_mode=True)

# ✅ Run all checks with verbose output
await crackerjack_run(
    command="check",
    args="--verbose",
    ai_agent_mode=True,
    timeout=600  # 10 minutes for complex fixes
)

# ✅ Dry-run to preview fixes
await crackerjack_run(
    command="test",
    args="--dry-run",
    ai_agent_mode=True
)
```

### Common Mistakes

```python
# ❌ WRONG - Don't put flags in command parameter
await crackerjack_run(command="--ai-fix -t")

# ❌ WRONG - Don't put --ai-fix in args
await crackerjack_run(command="test", args="--ai-fix")

# ✅ CORRECT
await crackerjack_run(command="test", ai_agent_mode=True)
```

### Parameters

- `command` (required): Semantic command name
  - Valid: `test`, `lint`, `check`, `format`, `security`, `complexity`, `all`
  - Invalid: `--ai-fix`, `-t`, any CLI flags

- `ai_agent_mode` (optional, default False): Enable AI-powered auto-fix
  - Replaces the `--ai-fix` CLI flag
  - Requires Anthropic API key configured in crackerjack

- `args` (optional): Additional arguments
  - Examples: `--verbose`, `--dry-run`, `--max-iterations 5`
  - Do NOT include `--ai-fix` here
```

**Files to Modify**:
- `session_mgmt_mcp/README.md`
- `session_mgmt_mcp/tools/README.md` (if exists)

**Agents to Use**:
- **documentation-specialist** - Write clear usage docs
- **content-designer** - Optimize error message UX

**Verification**:
- **content-designer** - Review documentation clarity
- **tutorial-engineer** - Verify examples work

---

## Phase 3: Testing & Verification

### Task 3.1: Unit Tests

**Files to Create**:

```python
# tests/test_auto_fix_workflow.py
import pytest
from crackerjack.workflows.auto_fix import AutoFixWorkflow

@pytest.mark.asyncio
async def test_iteration_stops_when_all_passing():
    """Workflow should stop when all hooks pass."""
    workflow = AutoFixWorkflow()
    # Mock all hooks passing on first iteration
    result = await workflow.run("test")
    assert result["success"]
    assert len(result["iterations"]) == 1

@pytest.mark.asyncio
async def test_max_iterations_respected():
    """Workflow should not exceed max iterations."""
    workflow = AutoFixWorkflow()
    result = await workflow.run("test", max_iterations=3)
    assert len(result["iterations"]) <= 3

# tests/test_claude_adapter.py
@pytest.mark.asyncio
async def test_claude_fix_generation():
    """Claude adapter should generate valid fixes."""
    from crackerjack.adapters.ai.claude import ClaudeCodeFixer
    fixer = ClaudeCodeFixer()

    result = await fixer.fix_code_issue(
        file_path="test.py",
        issue_description="Line too long",
        code_context="x = 1",
        fix_type="ruff"
    )

    assert result["success"]
    assert result["fixed_code"]
    assert 0 <= result["confidence"] <= 1

# tests/test_mcp_validation.py
def test_invalid_command_rejected():
    """MCP tool should reject invalid commands."""
    with pytest.raises(ValueError):
        validate_command("--ai-fix", "")

def test_ai_fix_in_args_rejected():
    """MCP tool should reject --ai-fix in args."""
    with pytest.raises(ValueError):
        validate_command("test", "--ai-fix")
```

**Agents to Use**:
- **pytest-hypothesis-specialist** - Write comprehensive tests
- **python-pro** - Implement test fixtures

**Verification**:
- **qa-strategist** - Review test coverage
- **code-reviewer** - Review test quality

---

### Task 3.2: Integration Tests

**Test Scenarios**:

1. **End-to-End Auto-Fix**:
   ```bash
   # Create file with known issue
   echo "x = 1" > test_long_line.py
   # Run auto-fix
   python -m crackerjack test --ai-fix
   # Verify fix applied
   # Verify hooks pass
   ```

2. **MCP Integration**:
   ```python
   # Test via MCP
   result = await crackerjack_run(command="test", ai_agent_mode=True)
   assert "Status: Success" in result or "fixes applied" in result
   ```

3. **Iteration Convergence**:
   ```python
   # Create file with multiple issues
   # Run auto-fix
   # Verify all issues fixed
   # Verify converged in <10 iterations
   ```

**Agents to Use**:
- **qa-strategist** - Design integration test suite
- **python-pro** - Implement integration tests

**Verification**:
- **devops-troubleshooter** - Test in CI/CD environment
- **code-reviewer** - Review test reliability

---

## Phase 4: Documentation & Deployment

### Task 4.1: Create Comprehensive Documentation

**Files to Create**:

1. **`crackerjack/docs/AUTO_FIX_GUIDE.md`**:
   - How auto-fix works
   - Configuration guide
   - Troubleshooting
   - Examples

2. **`crackerjack/docs/ARCHITECTURE.md`**:
   - Update with AI adapter architecture
   - Workflow diagrams
   - Integration points

3. **`session-mgmt-mcp/docs/CRACKERJACK_INTEGRATION.md`**:
   - MCP usage guide
   - Parameter reference
   - Common mistakes
   - Examples

**Agents to Use**:
- **documentation-specialist** - Write all documentation
- **mermaid-expert** - Create architecture diagrams
- **tutorial-engineer** - Create step-by-step guides

**Verification**:
- **content-designer** - Review documentation UX
- **python-pro** - Verify code examples

---

### Task 4.2: Deployment Checklist

**Pre-Deployment**:
- [ ] All tests passing (unit + integration)
- [ ] Documentation complete
- [ ] API keys documented
- [ ] Error messages user-friendly
- [ ] Backup/restore tested
- [ ] Performance benchmarked

**Deployment Steps**:
1. Merge to crackerjack main branch
2. Tag release: `v1.0.0-ai-fix`
3. Update session-mgmt-mcp dependency
4. Test in session-mgmt-mcp
5. Update both README files
6. Create migration guide

**Agents to Use**:
- **release-manager** - Coordinate deployment
- **devops-troubleshooter** - Handle deployment issues

**Verification**:
- **qa-strategist** - Final quality gate
- **security-auditor** - Security review before release

---

## Quality Assurance Strategy

### Double-Checking Protocol

Every task MUST be reviewed by TWO different agents:

**Review Matrix**:

| Task | Primary Agent | Reviewer 1 | Reviewer 2 |
|------|---------------|------------|------------|
| Input Validation | python-pro | code-reviewer | api-security-specialist |
| AI Adapter | ai-engineer | acb-specialist | security-auditor |
| Iteration Loop | python-pro | refactoring-specialist | qa-strategist |
| File Modifier | python-pro | security-auditor | code-reviewer |
| MCP Validation | python-pro | api-security-specialist | code-reviewer |
| Documentation | documentation-specialist | content-designer | tutorial-engineer |
| Unit Tests | pytest-hypothesis-specialist | qa-strategist | python-pro |
| Integration Tests | qa-strategist | devops-troubleshooter | python-pro |

**Review Process**:
1. Primary agent implements
2. Reviewer 1 checks correctness
3. Reviewer 2 checks quality/security
4. Issues logged and fixed
5. Re-review if major changes

---

## Success Criteria

**Crackerjack**:
- [ ] Input validation prevents misuse
- [ ] AI adapter successfully fixes real issues
- [ ] Iteration loop converges on test cases
- [ ] File modification creates backups
- [ ] Documentation comprehensive
- [ ] All tests passing (95%+ coverage)

**Session-Mgmt-MCP**:
- [ ] MCP tool validates inputs
- [ ] Error messages helpful
- [ ] Documentation clear
- [ ] Examples work

**Integration**:
- [ ] End-to-end auto-fix works
- [ ] MCP → crackerjack → AI → fixes → verification
- [ ] No regression in existing features

---

## Timeline & Resource Allocation

**Day 1**: Phase 1, Tasks 1.1-1.2 (Validation + AI Adapter)
- python-pro, ai-engineer, acb-specialist

**Day 2**: Phase 1, Tasks 1.3-1.4 (Iteration + Docs)
- python-pro, refactoring-specialist, documentation-specialist

**Day 3**: Phase 2 (MCP Improvements)
- python-pro, api-security-specialist, content-designer

**Day 4**: Phase 3 (Testing)
- pytest-hypothesis-specialist, qa-strategist, devops-troubleshooter

**Day 5**: Phase 4 (Documentation + Deployment)
- documentation-specialist, mermaid-expert, release-manager

---

## Risk Management

**High-Risk Areas**:
1. **AI API Failures**: Implement retry logic, fallbacks
2. **File Corruption**: Always create backups, validate before write
3. **Infinite Loops**: Max iteration limit, convergence detection
4. **API Key Leaks**: Proper secret management, validation

**Mitigation**:
- Extensive testing before production
- Feature flags for gradual rollout
- Monitoring and alerting
- Rollback plan

---

## Post-Implementation

**Monitoring**:
- Track auto-fix success rate
- Monitor iteration counts
- Log AI confidence scores
- Alert on failures

**Continuous Improvement**:
- Collect user feedback
- Improve prompts based on results
- Add more fix types
- Optimize iteration logic

**Maintenance**:
- Update Claude SDK as needed
- Refresh documentation
- Add new examples
- Performance tuning

---

## Appendix: Agent Recommendations

### For Each Task Type

**Implementation**:
- Primary: python-pro, ai-engineer, acb-specialist
- Review: code-reviewer, refactoring-specialist

**Security**:
- Primary: security-auditor, api-security-specialist
- Review: code-reviewer, devops-troubleshooter

**Testing**:
- Primary: pytest-hypothesis-specialist, qa-strategist
- Review: python-pro, devops-troubleshooter

**Documentation**:
- Primary: documentation-specialist, tutorial-engineer
- Review: content-designer, python-pro

**Deployment**:
- Primary: release-manager, devops-troubleshooter
- Review: qa-strategist, security-auditor

---

## Next Steps

1. Review and approve this plan
2. Set up project board/tracking
3. Allocate agents to tasks
4. Begin Phase 1, Task 1.1
5. Regular check-ins after each phase
6. Final review before deployment

**Questions? Issues? Contact the implementation team!** 🚀
