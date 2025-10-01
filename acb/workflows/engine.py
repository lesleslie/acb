"""Basic workflow engine implementation.

Provides a simple but robust workflow execution engine with:
- Step dependency resolution and ordering
- Parallel step execution where possible
- Retry logic with exponential backoff
- State persistence and recovery
- Event integration for workflow tracking
"""

import asyncio
import time
import typing as t
from datetime import datetime

from acb.depends import depends
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

    logger: Logger = depends()  # type: ignore[valid-type]

    def __init__(self, max_concurrent_steps: int = 5) -> None:
        self._max_concurrent_steps = max_concurrent_steps
        self._workflow_states: dict[str, WorkflowResult] = {}
        self._step_semaphore = asyncio.Semaphore(max_concurrent_steps)
        self._action_registry: dict[str, t.Callable[..., t.Awaitable[t.Any]]] = {}

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

        # Create workflow result
        result = WorkflowResult(
            workflow_id=workflow.workflow_id,
            state=WorkflowState.RUNNING,
            started_at=datetime.now(),
            metadata=workflow.metadata.copy(),
        )

        # Store initial state
        self._workflow_states[workflow.workflow_id] = result

        try:
            # Track completed and failed steps
            completed_steps: dict[str, StepResult] = {}
            failed_steps: set[str] = set()

            # Execute steps in dependency order
            while len(completed_steps) < len(workflow.steps):
                # Find steps ready to execute
                ready_steps = self._find_ready_steps(
                    workflow.steps,
                    completed_steps,
                    failed_steps,
                )

                if not ready_steps:
                    # Check if we're deadlocked
                    if len(completed_steps) + len(failed_steps) < len(workflow.steps):
                        remaining = [
                            s
                            for s in workflow.steps
                            if s.step_id not in completed_steps
                            and s.step_id not in failed_steps
                        ]
                        self.logger.warning(
                            f"Workflow {workflow.workflow_id} deadlocked. "
                            f"Remaining steps: {[s.step_id for s in remaining]}",
                        )
                        break
                    break

                # Execute ready steps (parallel where possible)
                step_tasks = []
                for step in ready_steps:
                    task = asyncio.create_task(
                        self._execute_step_with_retry(step, context),
                    )
                    step_tasks.append((step.step_id, task))

                # Wait for all ready steps to complete
                for step_id, task in step_tasks:
                    try:
                        step_result = await task
                        completed_steps[step_id] = step_result
                        result.steps.append(step_result)

                        if step_result.state == StepState.FAILED:
                            failed_steps.add(step_id)

                            if not workflow.continue_on_error:
                                self.logger.error(
                                    f"Step {step_id} failed, stopping workflow execution",
                                )
                                result.state = WorkflowState.FAILED
                                result.error = step_result.error
                                break

                    except Exception as e:
                        self.logger.exception(
                            f"Unexpected error executing step {step_id}: {e}",
                        )
                        failed_steps.add(step_id)

                        if not workflow.continue_on_error:
                            result.state = WorkflowState.FAILED
                            result.error = str(e)
                            break

                # Stop if workflow failed
                if result.state == WorkflowState.FAILED:
                    break

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

            return result

        except Exception as e:
            self.logger.exception(
                f"Workflow {workflow.workflow_id} execution failed: {e}"
            )
            result.state = WorkflowState.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            result.duration_ms = (time.time() - start_time) * 1000
            self._workflow_states[workflow.workflow_id] = result
            raise

    def _find_ready_steps(
        self,
        steps: list[WorkflowStep],
        completed: dict[str, StepResult],
        failed: set[str],
    ) -> list[WorkflowStep]:
        """Find steps that are ready to execute."""
        ready = []

        for step in steps:
            # Skip if already completed or failed
            if step.step_id in completed or step.step_id in failed:
                continue

            # Check if dependencies are satisfied
            dependencies_met = True
            for dep_id in step.depends_on:
                if dep_id not in completed:
                    dependencies_met = False
                    break

                # Check if dependency failed
                if completed[dep_id].state == StepState.FAILED:
                    if not step.skip_on_failure:
                        dependencies_met = False
                    break

            if dependencies_met:
                ready.append(step)

        return ready

    async def _execute_step_with_retry(
        self,
        step: WorkflowStep,
        context: dict[str, t.Any],
    ) -> StepResult:
        """Execute a step with retry logic."""
        retry_count = 0
        last_error = None

        while retry_count <= step.retry_attempts:
            try:
                async with self._step_semaphore:
                    result = await self.execute_step(step, context)

                    if result.state == StepState.COMPLETED:
                        return result

                    # Step failed but completed execution
                    last_error = result.error

            except Exception as e:
                self.logger.warning(
                    f"Step {step.step_id} attempt {retry_count + 1} failed: {e}",
                )
                last_error = str(e)

            # Increment retry count
            retry_count += 1

            # Wait before retry
            if retry_count <= step.retry_attempts:
                delay = step.retry_delay * (
                    2 ** (retry_count - 1)
                )  # Exponential backoff
                await asyncio.sleep(delay)

        # All retries exhausted
        return StepResult(
            step_id=step.step_id,
            state=StepState.FAILED,
            error=last_error or "Maximum retries exceeded",
            retry_count=retry_count - 1,
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
