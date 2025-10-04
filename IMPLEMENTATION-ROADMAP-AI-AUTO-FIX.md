# Implementation Roadmap: AI Auto-Fix for ACB

**Based on Crackerjack Architecture Analysis**

## Executive Summary

Crackerjack's `--ai-fix` provides an excellent architectural blueprint but the AI-powered fixing is **not implemented** (it's a stub). This document provides a roadmap for implementing **real** AI auto-fix functionality using ACB patterns.

**Key Finding:** ClaudeCodeBridge is a simulation layer that returns hardcoded recommendations but never modifies files.

**What Works:** Tool-based fixes (Tier 1) - ruff, bandit, etc.
**What Doesn't:** AI-powered fixes (Tier 2) - completely unimplemented

---

## Phase 1: Core AI Integration (Critical)

### 1.1 Create Real LLM Adapter

**ACB Pattern:**
```python
# acb/adapters/ai/anthropic.py
from acb.config import AdapterBase, Settings
from acb.adapters import AdapterMetadata, AdapterStatus, AdapterCapability
from anthropic import AsyncAnthropic
import uuid

MODULE_METADATA = AdapterMetadata(
    module_id=str(uuid.uuid7()),
    name="Anthropic AI",
    category="ai",
    provider="anthropic",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.AI_INFERENCE,
    ],
    required_packages=["anthropic>=0.18.0"],
    description="Anthropic Claude AI adapter for code generation and fixing",
)

class AnthropicSettings(Settings):
    """Settings for Anthropic AI adapter"""
    api_key: str = ""
    model: str = "claude-sonnet-4"
    max_tokens: int = 8192
    temperature: float = 0.0
    timeout: int = 300

class AI(AdapterBase):
    """Anthropic AI adapter for ACB"""

    settings: AnthropicSettings | None = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = AsyncAnthropic(
                api_key=self.settings.api_key,
                timeout=self.settings.timeout
            )
        return self._client

    async def generate_fix(
        self,
        issue_description: str,
        file_content: str,
        file_path: str,
        context: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Generate a code fix for an issue"""
        client = await self._ensure_client()

        prompt = self._build_fix_prompt(
            issue_description,
            file_content,
            file_path,
            context
        )

        response = await client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_fix_response(response)

    def _build_fix_prompt(
        self,
        issue: str,
        content: str,
        path: str,
        context: dict[str, Any] = None
    ) -> str:
        """Build prompt for fix generation"""
        return f"""You are a code fixing assistant. Fix the following issue:

Issue: {issue}
File: {path}

Current code:
```python
{content}
```

Context: {context or 'None'}

Provide the fix in this format:
1. Explanation of the issue
2. The fixed code (complete file)
3. List of changes made

Format your response as JSON:
{{
    "explanation": "...",
    "fixed_code": "...",
    "changes": ["change1", "change2", ...]
}}
"""

    async def _parse_fix_response(self, response) -> dict[str, Any]:
        """Parse LLM response into structured fix"""
        import json

        # Extract JSON from response
        content = response.content[0].text

        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            fix_data = json.loads(content.strip())
            return {
                "success": True,
                "explanation": fix_data.get("explanation", ""),
                "fixed_code": fix_data.get("fixed_code", ""),
                "changes": fix_data.get("changes", []),
                "confidence": 0.9,  # Could be extracted from response
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse LLM response: {e}",
                "raw_response": content,
            }
```

**Configuration:**
```yaml
# settings/adapters.yml
ai: anthropic

# settings/ai.yml
api_key: ${ANTHROPIC_API_KEY}
model: claude-sonnet-4
max_tokens: 8192
temperature: 0.0
timeout: 300
```

### 1.2 Implement File Modification Service

**ACB Pattern:**
```python
# acb/services/code_fixer.py
from acb.depends import depends
from acb.adapters import import_adapter
from pathlib import Path
import difflib
import typing as t

class CodeFixerService:
    """Service for applying AI-generated code fixes"""

    def __init__(self):
        self.AI = import_adapter("ai")
        self.ai = depends.get(self.AI)
        self.backup_dir = Path(".crackerjack/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def apply_fix(
        self,
        file_path: Path,
        issue: dict[str, t.Any],
        context: dict[str, t.Any] = None
    ) -> dict[str, t.Any]:
        """Apply AI-generated fix to a file"""

        # 1. Backup original file
        backup_path = self._create_backup(file_path)

        # 2. Read current content
        original_content = file_path.read_text()

        # 3. Generate fix using AI
        fix_result = await self.ai.generate_fix(
            issue_description=issue["message"],
            file_content=original_content,
            file_path=str(file_path),
            context=context
        )

        if not fix_result["success"]:
            return {
                "success": False,
                "error": fix_result.get("error", "Fix generation failed"),
                "backup_path": backup_path,
            }

        # 4. Apply the fix
        fixed_content = fix_result["fixed_code"]

        # 5. Validate the fix (basic checks)
        if not self._validate_fix(original_content, fixed_content):
            return {
                "success": False,
                "error": "Fix validation failed (suspicious changes)",
                "backup_path": backup_path,
            }

        # 6. Write fixed content
        file_path.write_text(fixed_content)

        # 7. Generate diff for logging
        diff = self._generate_diff(original_content, fixed_content, file_path)

        return {
            "success": True,
            "file_path": str(file_path),
            "backup_path": str(backup_path),
            "explanation": fix_result["explanation"],
            "changes": fix_result["changes"],
            "diff": diff,
        }

    def _create_backup(self, file_path: Path) -> Path:
        """Create backup of file before modification"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name

        backup_path.write_text(file_path.read_text())
        return backup_path

    def _validate_fix(self, original: str, fixed: str) -> bool:
        """Basic validation of fix (prevent major corruption)"""
        # Check that fix isn't empty
        if not fixed.strip():
            return False

        # Check that file isn't suspiciously smaller (>50% reduction)
        if len(fixed) < len(original) * 0.5:
            return False

        # Check that fix is valid Python syntax
        try:
            compile(fixed, "<string>", "exec")
            return True
        except SyntaxError:
            return False

    def _generate_diff(
        self,
        original: str,
        fixed: str,
        file_path: Path
    ) -> str:
        """Generate unified diff for logging"""
        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile=f"a/{file_path.name}",
            tofile=f"b/{file_path.name}",
        )

        return "".join(diff)

    def rollback(self, backup_path: Path, target_path: Path) -> bool:
        """Rollback to backup if fix fails verification"""
        try:
            backup_content = backup_path.read_text()
            target_path.write_text(backup_content)
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

# Register service
depends.set(CodeFixerService)
```

### 1.3 Replace ClaudeCodeBridge Stub

**Crackerjack Integration:**
```python
# crackerjack/agents/real_claude_code_bridge.py
from acb.depends import depends
from acb.adapters import import_adapter
from acb.services.code_fixer import CodeFixerService
from .base import Issue, FixResult
from pathlib import Path

class RealClaudeCodeBridge:
    """Real implementation of Claude Code bridge using ACB AI adapter"""

    def __init__(self, context):
        self.context = context
        self.code_fixer = depends.get(CodeFixerService)
        self.AI = import_adapter("ai")
        self.ai = depends.get(self.AI)

    async def consult_external_agent(
        self,
        issue: Issue,
        agent_name: str,
        context: dict = None
    ) -> dict:
        """REAL agent consultation using AI adapter"""

        # Build context for AI
        fix_context = {
            "agent_type": agent_name,
            "issue_type": issue.type.value,
            "severity": issue.severity.value,
            "project_context": self.context.project_root,
        }

        if context:
            fix_context.update(context)

        # Generate fix using AI
        file_path = Path(issue.file_path) if issue.file_path else None

        if file_path and file_path.exists():
            # Apply real fix
            fix_result = await self.code_fixer.apply_fix(
                file_path=file_path,
                issue={
                    "message": issue.message,
                    "type": issue.type.value,
                    "line": issue.line_number,
                },
                context=fix_context
            )

            return {
                "status": "success" if fix_result["success"] else "failed",
                "agent": agent_name,
                "fix_applied": fix_result["success"],
                "file_modified": fix_result.get("file_path"),
                "backup_path": fix_result.get("backup_path"),
                "explanation": fix_result.get("explanation", ""),
                "changes": fix_result.get("changes", []),
                "diff": fix_result.get("diff", ""),
                "error": fix_result.get("error"),
            }
        else:
            # No file path, provide recommendations only
            return {
                "status": "advisory",
                "agent": agent_name,
                "fix_applied": False,
                "recommendations": [
                    f"Fix {issue.type.value} in {issue.file_path or 'unknown file'}"
                ],
            }
```

---

## Phase 2: Iteration Loop (Important)

### 2.1 Implement Iterative Fixing

**Workflow Integration:**
```python
# crackerjack/core/ai_fixing_workflow.py
from acb.depends import depends
import asyncio

class AIFixingWorkflow:
    """Iterative AI fixing workflow"""

    def __init__(self, coordinator, options):
        self.coordinator = coordinator
        self.options = options
        self.max_iterations = options.effective_max_iterations
        self.logger = logging.getLogger(__name__)

    async def run(self) -> dict[str, t.Any]:
        """Run iterative AI fixing workflow"""

        all_fixes_applied = []
        iteration_results = []

        for iteration in range(1, self.max_iterations + 1):
            self.logger.info(f"AI Fixing Iteration {iteration}/{self.max_iterations}")

            # 1. Collect current issues
            issues = await self._collect_issues()

            if not issues:
                self.logger.info(f"No issues remaining after iteration {iteration}")
                break

            # 2. Apply AI fixes
            fix_result = await self.coordinator.handle_issues(issues)

            # 3. Track results
            iteration_results.append({
                "iteration": iteration,
                "issues_found": len(issues),
                "fixes_applied": len(fix_result.fixes_applied),
                "success": fix_result.success,
            })

            all_fixes_applied.extend(fix_result.fixes_applied)

            # 4. Verify fixes
            verification_passed = await self._verify_fixes(fix_result)

            if verification_passed:
                self.logger.info(f"All fixes verified successfully at iteration {iteration}")
                break

            # 5. Convergence check
            if iteration > 1:
                prev_issues = iteration_results[iteration - 2]["issues_found"]
                curr_issues = len(fix_result.remaining_issues)

                if curr_issues >= prev_issues:
                    self.logger.warning(
                        f"No progress made (issues: {prev_issues} → {curr_issues}). "
                        "Stopping iterations."
                    )
                    break

            # 6. Small delay between iterations
            if iteration < self.max_iterations:
                await asyncio.sleep(2)

        return {
            "success": len(issues) == 0 or fix_result.success,
            "iterations_run": len(iteration_results),
            "total_fixes_applied": len(all_fixes_applied),
            "fixes_applied": all_fixes_applied,
            "iteration_results": iteration_results,
        }

    async def _collect_issues(self) -> list[Issue]:
        """Collect current issues from tests and hooks"""
        # Reuse crackerjack's existing collection logic
        from crackerjack.core.workflow_orchestrator import WorkflowPipeline

        pipeline = depends.get(WorkflowPipeline)
        return await pipeline._collect_issues_from_failures()

    async def _verify_fixes(self, fix_result: FixResult) -> bool:
        """Verify that fixes worked by re-running checks"""
        if not fix_result.files_modified:
            return True

        # Re-run tests if test fixes were applied
        test_fixes = [f for f in fix_result.fixes_applied if "test" in f.lower()]
        if test_fixes:
            from crackerjack.core.phase_coordinator import PhaseCoordinator
            phases = depends.get(PhaseCoordinator)
            test_passed = phases.run_testing_phase(self.options)
            if not test_passed:
                return False

        # Re-run hooks if code fixes were applied
        code_fixes = [f for f in fix_result.files_modified if not "test" in f.lower()]
        if code_fixes:
            from crackerjack.core.phase_coordinator import PhaseCoordinator
            phases = depends.get(PhaseCoordinator)
            hooks_passed = phases.run_comprehensive_hooks_only(self.options)
            if not hooks_passed:
                return False

        return True
```

### 2.2 Update WorkflowOrchestrator

**Replace single-pass with iteration:**
```python
# crackerjack/core/workflow_orchestrator.py
async def _run_ai_agent_fixing_phase(self, options: OptionsProtocol) -> bool:
    """Run AI fixing with iteration loop"""

    self._update_mcp_status("ai_fixing", "running")

    # Create workflow with iteration support
    workflow = AIFixingWorkflow(
        coordinator=self._setup_agent_coordinator(),
        options=options
    )

    # Run iterative fixing
    result = await workflow.run()

    # Update MCP status
    if result["success"]:
        self._update_mcp_status("ai_fixing", "completed")
    else:
        self._update_mcp_status("ai_fixing", "failed")

    # Log results
    self.logger.info(
        f"AI Fixing completed: {result['iterations_run']} iterations, "
        f"{result['total_fixes_applied']} fixes applied"
    )

    return result["success"]
```

---

## Phase 3: Robustness (Nice to Have)

### 3.1 Error Handling

```python
class SafeCodeFixer:
    """Code fixer with comprehensive error handling"""

    async def apply_fix_with_rollback(
        self,
        file_path: Path,
        issue: dict,
        context: dict = None
    ) -> dict:
        """Apply fix with automatic rollback on failure"""

        backup_path = None

        try:
            # Create backup
            backup_path = self._create_backup(file_path)

            # Apply fix
            fix_result = await self.code_fixer.apply_fix(
                file_path, issue, context
            )

            if not fix_result["success"]:
                # Rollback on failure
                self.rollback(backup_path, file_path)
                return fix_result

            # Verify fix worked
            verification_ok = await self._verify_fix_works(file_path, issue)

            if not verification_ok:
                # Rollback if verification fails
                self.logger.warning(f"Fix verification failed, rolling back {file_path}")
                self.rollback(backup_path, file_path)
                return {
                    "success": False,
                    "error": "Fix applied but verification failed",
                    "rolled_back": True,
                }

            return fix_result

        except Exception as e:
            self.logger.error(f"Fix application failed: {e}")

            # Rollback on exception
            if backup_path:
                self.rollback(backup_path, file_path)

            return {
                "success": False,
                "error": str(e),
                "rolled_back": bool(backup_path),
            }

    async def _verify_fix_works(self, file_path: Path, issue: dict) -> bool:
        """Verify fix by running relevant checks"""

        # Run syntax check
        try:
            compile(file_path.read_text(), str(file_path), "exec")
        except SyntaxError:
            return False

        # Run specific check based on issue type
        if issue.get("type") == "TYPE_ERROR":
            # Run pyright on this file
            result = subprocess.run(
                ["uv", "run", "pyright", str(file_path)],
                capture_output=True,
                text=True
            )
            return result.returncode == 0

        elif issue.get("type") == "SECURITY":
            # Run bandit on this file
            result = subprocess.run(
                ["uv", "run", "bandit", str(file_path)],
                capture_output=True,
                text=True
            )
            return "No issues identified" in result.stdout

        # Default: syntax check passed
        return True
```

### 3.2 Caching

```python
from acb.adapters import import_adapter

class CachedAIFixer:
    """AI fixer with result caching"""

    def __init__(self):
        self.Cache = import_adapter("cache")
        self.cache = depends.get(self.Cache)
        self.code_fixer = depends.get(CodeFixerService)

    async def apply_fix(self, file_path, issue, context=None) -> dict:
        """Apply fix with caching"""

        # Generate cache key from issue
        cache_key = self._generate_cache_key(file_path, issue)

        # Check cache
        cached_fix = await self.cache.get(cache_key)
        if cached_fix:
            self.logger.info(f"Using cached fix for {file_path}")
            return cached_fix

        # Generate new fix
        fix_result = await self.code_fixer.apply_fix(file_path, issue, context)

        # Cache successful fixes
        if fix_result["success"]:
            await self.cache.set(cache_key, fix_result, ttl=3600)

        return fix_result

    def _generate_cache_key(self, file_path: Path, issue: dict) -> str:
        """Generate cache key for fix"""
        import hashlib

        # Hash file content + issue type + message
        content = file_path.read_text()
        key_data = f"{content}:{issue.get('type')}:{issue.get('message')}"
        return f"fix:{hashlib.md5(key_data.encode()).hexdigest()}"
```

---

## Phase 4: Testing & Validation

### 4.1 Unit Tests

```python
# tests/test_ai_fixer.py
import pytest
from pathlib import Path
from acb.services.code_fixer import CodeFixerService

@pytest.fixture
def test_file(tmp_path):
    """Create test Python file"""
    file_path = tmp_path / "test.py"
    file_path.write_text("""
def foo(x, y):
    result = x + y  # Missing type hints
    return result
""")
    return file_path

@pytest.mark.asyncio
async def test_apply_fix(test_file):
    """Test applying AI-generated fix"""
    fixer = CodeFixerService()

    issue = {
        "message": "Missing type hints on function parameters",
        "type": "TYPE_ERROR",
        "line": 2
    }

    result = await fixer.apply_fix(test_file, issue)

    assert result["success"]
    assert "def foo(x: int, y: int)" in test_file.read_text()
    assert result["backup_path"].exists()

@pytest.mark.asyncio
async def test_rollback_on_syntax_error(test_file):
    """Test rollback when fix creates syntax error"""
    fixer = CodeFixerService()

    # Mock AI to return invalid Python
    with patch.object(fixer.ai, 'generate_fix') as mock_gen:
        mock_gen.return_value = {
            "success": True,
            "fixed_code": "def foo(x, y\n  return x + y",  # Syntax error
            "explanation": "Test",
            "changes": []
        }

        result = await fixer.apply_fix(test_file, {})

        # Should fail validation and not modify file
        assert not result["success"]
        assert "Missing type hints" in test_file.read_text()  # Original content
```

### 4.2 Integration Tests

```python
# tests/integration/test_ai_workflow.py
@pytest.mark.asyncio
async def test_full_ai_fixing_workflow(test_project):
    """Test complete AI fixing workflow"""

    # Setup test project with known issues
    (test_project / "src" / "broken.py").write_text("""
def calculate(a, b):  # Missing type hints
    if a > b:
        result = a - b
    else:
        result = b - a
    return result  # Complexity too high
""")

    # Run AI fixing workflow
    workflow = AIFixingWorkflow(
        coordinator=create_enhanced_coordinator(...),
        options=Options(ai_fix=True, max_iterations=3)
    )

    result = await workflow.run()

    # Verify fixes applied
    assert result["success"]
    assert result["total_fixes_applied"] > 0
    assert result["iterations_run"] <= 3

    # Verify file was actually fixed
    fixed_content = (test_project / "src" / "broken.py").read_text()
    assert "def calculate(a: int, b: int) -> int:" in fixed_content
```

---

## Deployment Checklist

### Configuration

- [ ] Add `ANTHROPIC_API_KEY` to environment
- [ ] Configure `settings/ai.yml`
- [ ] Set up backup directory (`.crackerjack/backups`)
- [ ] Configure cache adapter (redis recommended)

### Code Changes

- [ ] Implement `acb/adapters/ai/anthropic.py`
- [ ] Implement `acb/services/code_fixer.py`
- [ ] Replace `ClaudeCodeBridge` stub with `RealClaudeCodeBridge`
- [ ] Add `AIFixingWorkflow` to workflow orchestrator
- [ ] Update `_run_ai_agent_fixing_phase` with iteration loop

### Testing

- [ ] Unit tests for AI adapter
- [ ] Unit tests for code fixer service
- [ ] Integration tests for full workflow
- [ ] Manual testing with real issues
- [ ] Performance testing (iteration time)

### Documentation

- [ ] Update CLAUDE.md with new AI features
- [ ] Document configuration requirements
- [ ] Add examples of AI fixing in action
- [ ] Create troubleshooting guide

---

## Success Metrics

**Phase 1 Complete:**
- AI adapter can generate fixes ✅
- Files can be modified safely ✅
- Backups are created automatically ✅

**Phase 2 Complete:**
- Iteration loop runs multiple times ✅
- Convergence detection works ✅
- Fixes are verified after application ✅

**Phase 3 Complete:**
- Rollback works on failures ✅
- Caching reduces duplicate work ✅
- Error handling prevents corruption ✅

**Production Ready:**
- 80%+ of simple fixes succeed
- Zero file corruption incidents
- Average 2-3 iterations to convergence
- Sub-60-second per-iteration time
