"""Basic workflow engine implementation.

Provides a simple but robust workflow execution engine with:
- Step dependency resolution and ordering
- Parallel step execution where possible
- Retry logic with exponential backoff
- State persistence and recovery
- Event integration for workflow tracking
"""

import time

import asyncio
import typing as t
from datetime import datetime

from acb.depends import Inject, depends
from acb.logger import Logger
from acb.workflows._base import (
    StepResult,
    StepState,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowResult,
    WorkflowState,
    WorkflowStep,
)


class BasicWorkflowEngine(WorkflowEngine):
    """Basic workflow engine with dependency resolution and parallel execution."""

    logger: Inject[Logger]

    def __init__(self, max_concurrent_steps: int = 5) -> None:
        self._max_concurrent_steps = max_concurrent_steps
        self._workflow_states: dict[str, WorkflowResult] = {}
        self._step_semaphore = asyncio.Semaphore(max_concurrent_steps)
        self._action_registry: dict[str, t.Callable[..., t.Awaitable[t.Any]]] = {}

        # Initialize logger if not already set by dependency injection
        if not hasattr(self, "logger") or self.logger is None:
            try:
                self.logger = depends.get_sync(Logger)
            except Exception:
                # Fallback to basic logger if DI not configured (e.g. in tests)
                import logging

                self.logger = logging.getLogger(__name__)  # type: ignore[assignment]

    def register_action(
        self,
        name: str,
        handler: t.Callable[..., t.Awaitable[t.Any]],
    ) -> None:
        """Register an action handler.

        Args:
            name: Action name to register
            handler: Async function to handle the action
        """
        self._action_registry[name] = handler

    async def execute(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, t.Any] | None = None,
    ) -> WorkflowResult:
        """Execute a workflow with dependency resolution and parallel execution."""
        start_time = time.time()
        context = context or {}

        # Initialize workflow execution
        result, completed_steps, failed_steps = self._initialize_workflow_execution(
            workflow
        )

        try:
            # Execute workflow steps in dependency order
            await self._execute_workflow_steps(
                workflow, context, result, completed_steps, failed_steps
            )

            # Finalize workflow result
            self._finalize_workflow_result(workflow, result, failed_steps, start_time)

            return result

        except Exception as e:
            self._handle_workflow_exception(workflow, result, e, start_time)
            raise

    def _initialize_workflow_execution(
        self, workflow: WorkflowDefinition
    ) -> tuple[WorkflowResult, dict[str, StepResult], set[str]]:
        """Initialize workflow execution state."""
        result = WorkflowResult(
            workflow_id=workflow.workflow_id,
            state=WorkflowState.RUNNING,
            started_at=datetime.now(),
            metadata=workflow.metadata.copy(),
        )

        self._workflow_states[workflow.workflow_id] = result

        completed_steps: dict[str, StepResult] = {}
        failed_steps: set[str] = set()

        return result, completed_steps, failed_steps

    async def _execute_workflow_steps(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, t.Any],
        result: WorkflowResult,
        completed_steps: dict[str, StepResult],
        failed_steps: set[str],
    ) -> None:
        """Execute all workflow steps in dependency order."""
        while len(completed_steps) < len(workflow.steps):
            # Find steps ready to execute
            ready_steps = self._find_ready_steps(
                workflow.steps, completed_steps, failed_steps
            )

            # Check for completion or deadlock
            if not ready_steps:
                self._handle_no_ready_steps(workflow, completed_steps, failed_steps)
                break

            # Execute ready steps in parallel
            step_results = await self._execute_parallel_steps(ready_steps, context)

            # Process step results
            should_stop = self._process_step_results(
                workflow, step_results, completed_steps, failed_steps, result
            )

            if should_stop:
                break

    def _handle_no_ready_steps(
        self,
        workflow: WorkflowDefinition,
        completed_steps: dict[str, StepResult],
        failed_steps: set[str],
    ) -> None:
        """Handle case where no steps are ready to execute."""
        total_processed = len(completed_steps) + len(failed_steps)
        if total_processed < len(workflow.steps):
            remaining = [
                s
                for s in workflow.steps
                if s.step_id not in completed_steps and s.step_id not in failed_steps
            ]
            self.logger.warning(
                f"Workflow {workflow.workflow_id} deadlocked. "
                f"Remaining steps: {[s.step_id for s in remaining]}"
            )

    async def _execute_parallel_steps(
        self, ready_steps: list[WorkflowStep], context: dict[str, t.Any]
    ) -> list[tuple[str, StepResult]]:
        """Execute multiple steps in parallel and collect results."""
        step_tasks = [
            (
                step.step_id,
                asyncio.create_task(self._execute_step_with_retry(step, context)),
            )
            for step in ready_steps
        ]

        # Wait for all tasks to complete
        results = []
        for step_id, task in step_tasks:
            step_result = await task
            results.append((step_id, step_result))

        return results

    def _process_step_results(
        self,
        workflow: WorkflowDefinition,
        step_results: list[tuple[str, StepResult]],
        completed_steps: dict[str, StepResult],
        failed_steps: set[str],
        result: WorkflowResult,
    ) -> bool:
        """Process step results and update workflow state. Returns True if should stop."""
        for step_id, step_result in step_results:
            completed_steps[step_id] = step_result
            result.steps.append(step_result)

            if step_result.state == StepState.FAILED:
                should_stop = self._handle_step_failure(
                    workflow, step_id, step_result, failed_steps, result
                )
                if should_stop:
                    return True

        return False

    def _handle_step_failure(
        self,
        workflow: WorkflowDefinition,
        step_id: str,
        step_result: StepResult,
        failed_steps: set[str],
        result: WorkflowResult,
    ) -> bool:
        """Handle a failed step. Returns True if workflow should stop."""
        failed_steps.add(step_id)

        if not workflow.continue_on_error:
            self.logger.error(f"Step {step_id} failed, stopping workflow execution")
            result.state = WorkflowState.FAILED
            result.error = step_result.error
            return True

        return False

    def _finalize_workflow_result(
        self,
        workflow: WorkflowDefinition,
        result: WorkflowResult,
        failed_steps: set[str],
        start_time: float,
    ) -> None:
        """Finalize workflow result with state and timing."""
        # Determine final state
        if result.state != WorkflowState.FAILED:
            if failed_steps:
                result.state = WorkflowState.FAILED
                result.error = f"Steps failed: {', '.join(failed_steps)}"
            else:
                result.state = WorkflowState.COMPLETED

        # Set completion time
        result.completed_at = datetime.now()
        result.duration_ms = (time.time() - start_time) * 1000

        # Update stored state
        self._workflow_states[workflow.workflow_id] = result

    def _handle_workflow_exception(
        self,
        workflow: WorkflowDefinition,
        result: WorkflowResult,
        error: Exception,
        start_time: float,
    ) -> None:
        """Handle workflow execution exception."""
        self.logger.exception(
            f"Workflow {workflow.workflow_id} execution failed: {error}"
        )
        result.state = WorkflowState.FAILED
        result.error = str(error)
        result.completed_at = datetime.now()
        result.duration_ms = (time.time() - start_time) * 1000
        self._workflow_states[workflow.workflow_id] = result

    def _is_step_already_processed(
        self,
        step_id: str,
        completed: dict[str, StepResult],
        failed: set[str],
    ) -> bool:
        """Check if step has already been completed or failed."""
        return step_id in completed or step_id in failed

    def _check_dependency_status(
        self,
        dep_id: str,
        step: WorkflowStep,
        completed: dict[str, StepResult],
    ) -> bool:
        """Check if a single dependency is satisfied. Returns True if satisfied."""
        # Dependency must be completed
        if dep_id not in completed:
            return False

        # If dependency failed, check if step allows skipping
        if completed[dep_id].state == StepState.FAILED:
            return step.skip_on_failure

        return True

    def _are_dependencies_satisfied(
        self,
        step: WorkflowStep,
        completed: dict[str, StepResult],
    ) -> bool:
        """Check if all dependencies for a step are satisfied."""
        for dep_id in step.depends_on:
            if not self._check_dependency_status(dep_id, step, completed):
                return False

        return True

    def _find_ready_steps(
        self,
        steps: list[WorkflowStep],
        completed: dict[str, StepResult],
        failed: set[str],
    ) -> list[WorkflowStep]:
        """Find steps that are ready to execute."""
        ready = []

        for step in steps:
            # Skip if already processed
            if self._is_step_already_processed(step.step_id, completed, failed):
                continue

            # Check if dependencies are satisfied
            if self._are_dependencies_satisfied(step, completed):
                ready.append(step)

        return ready

    async def _execute_step_with_retry(
        self,
        step: WorkflowStep,
        context: dict[str, t.Any],
    ) -> StepResult:
        """Execute a step with retry logic."""
        last_error = None

        for retry_count in range(step.retry_attempts + 1):
            # Execute single attempt
            result, error = await self._execute_single_attempt(step, context)

            # Check if successful
            if result is not None and result.state == StepState.COMPLETED:
                return result

            # Track error
            last_error = error or (result.error if result else None)

            # Check if should retry
            if not self._should_retry(retry_count, step.retry_attempts):
                break

            # Wait before retry with exponential backoff
            await self._wait_before_retry(step, retry_count)

        # All retries exhausted
        return self._create_failed_result(step, last_error, retry_count)

    async def _execute_single_attempt(
        self, step: WorkflowStep, context: dict[str, t.Any]
    ) -> tuple[StepResult | None, str | None]:
        """Execute a single step attempt. Returns (result, error)."""
        try:
            async with self._step_semaphore:
                result = await self.execute_step(step, context)
                return result, None

        except Exception as e:
            self.logger.warning(f"Step {step.step_id} attempt failed: {e}")
            return None, str(e)

    def _should_retry(self, retry_count: int, max_retries: int) -> bool:
        """Check if should retry after current attempt."""
        return retry_count < max_retries

    async def _wait_before_retry(self, step: WorkflowStep, retry_count: int) -> None:
        """Wait before retry with exponential backoff."""
        delay = step.retry_delay * (2**retry_count)
        await asyncio.sleep(delay)

    def _create_failed_result(
        self, step: WorkflowStep, error: str | None, retry_count: int
    ) -> StepResult:
        """Create a failed step result after all retries exhausted."""
        return StepResult(
            step_id=step.step_id,
            state=StepState.FAILED,
            error=error or "Maximum retries exceeded",
            retry_count=retry_count,
        )

    async def execute_step(
        self,
        step: WorkflowStep,
        context: dict[str, t.Any] | None = None,
    ) -> StepResult:
        """Execute a single workflow step."""
        context = context or {}
        start_time = time.time()

        result = StepResult(
            step_id=step.step_id,
            state=StepState.RUNNING,
            started_at=datetime.now(),
        )

        try:
            # Get action handler
            if step.action not in self._action_registry:
                msg = f"Unknown action: {step.action}"
                raise ValueError(msg)

            handler = self._action_registry[step.action]

            # Prepare parameters with context
            params = step.params.copy()
            params["context"] = context
            params["step_id"] = step.step_id

            # Execute with timeout
            output = await asyncio.wait_for(handler(**params), timeout=step.timeout)

            result.state = StepState.COMPLETED
            result.output = output
            result.completed_at = datetime.now()
            result.duration_ms = (time.time() - start_time) * 1000

            return result

        except TimeoutError:
            result.state = StepState.FAILED
            result.error = f"Step timed out after {step.timeout} seconds"
            result.completed_at = datetime.now()
            result.duration_ms = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            self.logger.exception(f"Step {step.step_id} execution failed: {e}")
            result.state = StepState.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            result.duration_ms = (time.time() - start_time) * 1000
            return result

    async def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a workflow (not implemented in basic engine)."""
        if workflow_id not in self._workflow_states:
            return False

        result = self._workflow_states[workflow_id]
        if result.state == WorkflowState.RUNNING:
            result.state = WorkflowState.PAUSED
            return True

        return False

    async def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a workflow (not implemented in basic engine)."""
        if workflow_id not in self._workflow_states:
            return False

        result = self._workflow_states[workflow_id]
        if result.state == WorkflowState.PAUSED:
            result.state = WorkflowState.RUNNING
            return True

        return False

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow."""
        if workflow_id not in self._workflow_states:
            return False

        result = self._workflow_states[workflow_id]
        if result.state in (WorkflowState.RUNNING, WorkflowState.PAUSED):
            result.state = WorkflowState.CANCELLED
            result.completed_at = datetime.now()
            return True

        return False

    async def get_workflow_state(self, workflow_id: str) -> WorkflowResult | None:
        """Get current workflow state."""
        return self._workflow_states.get(workflow_id)

    async def list_workflows(
        self,
        state: WorkflowState | None = None,
        limit: int = 100,
    ) -> list[WorkflowResult]:
        """List workflows, optionally filtered by state."""
        workflows = list(self._workflow_states.values())

        if state:
            workflows = [w for w in workflows if w.state == state]

        return workflows[:limit]
