"""Base workflow engine for ACB workflow orchestration.

This module provides the foundation for workflow management, including:
- Workflow execution and state management
- Integration with Events System and Task Queue
- Step-based workflow composition
- Error handling and retry mechanisms
"""

from abc import ABC, abstractmethod
from enum import Enum

import asyncio
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from acb.config import Config
from acb.depends import Inject, depends
from acb.logger import Logger
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings


class WorkflowState(Enum):
    """Workflow execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class StepState(Enum):
    """Individual step execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class StepResult:
    """Result of a workflow step execution."""

    step_id: str
    state: StepState
    output: t.Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    retry_count: int = 0
    metadata: dict[str, t.Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    workflow_id: str
    state: WorkflowState
    steps: list[StepResult] = field(default_factory=list)
    output: t.Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    metadata: dict[str, t.Any] = field(default_factory=dict)


class WorkflowStep(BaseModel):
    """Definition of a workflow step."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(description="Unique step identifier")
    name: str = Field(description="Human-readable step name")
    action: str = Field(description="Action to execute (function/method name)")
    params: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Parameters for the action",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Step IDs this step depends on",
    )
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    retry_delay: float = Field(
        default=1.0,
        description="Delay between retries in seconds",
    )
    timeout: float = Field(default=300.0, description="Step timeout in seconds")
    skip_on_failure: bool = Field(
        default=False,
        description="Skip this step if dependencies fail",
    )
    parallel: bool = Field(
        default=False,
        description="Can execute in parallel with other steps",
    )


class WorkflowDefinition(BaseModel):
    """Complete workflow definition."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(description="Unique workflow identifier")
    name: str = Field(description="Human-readable workflow name")
    description: str | None = Field(default=None, description="Workflow description")
    version: str = Field(default="1.0.0", description="Workflow version")
    steps: list[WorkflowStep] = Field(description="Workflow steps")
    timeout: float = Field(
        default=3600.0,
        description="Total workflow timeout in seconds",
    )
    retry_failed_steps: bool = Field(
        default=True,
        description="Retry failed steps automatically",
    )
    continue_on_error: bool = Field(
        default=False,
        description="Continue execution even if steps fail",
    )
    metadata: dict[str, t.Any] = Field(
        default_factory=dict,
        description="Additional workflow metadata",
    )


class WorkflowSettings(ServiceSettings):
    """Settings for workflow engine."""

    max_concurrent_workflows: int = 10
    max_concurrent_steps: int = 5
    default_timeout: float = 3600.0
    enable_events: bool = True
    enable_task_queue: bool = True
    persist_state: bool = True

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class WorkflowConfig(ServiceConfig):
    """Configuration for workflow engine."""

    engine_type: str = Field(default="basic", description="Workflow engine type")
    storage_backend: str | None = Field(
        default=None,
        description="State persistence backend",
    )


class WorkflowEngine(ABC):
    """Abstract base class for workflow engines.

    Defines the interface that all workflow engine implementations must follow.
    """

    @abstractmethod
    async def execute(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, t.Any] | None = None,
    ) -> WorkflowResult:
        """Execute a workflow.

        Args:
            workflow: Workflow definition to execute
            context: Optional execution context/variables

        Returns:
            WorkflowResult with execution status and outputs
        """
        ...

    @abstractmethod
    async def execute_step(
        self,
        step: WorkflowStep,
        context: dict[str, t.Any] | None = None,
    ) -> StepResult:
        """Execute a single workflow step.

        Args:
            step: Step definition to execute
            context: Optional execution context/variables

        Returns:
            StepResult with step execution status
        """
        ...

    @abstractmethod
    async def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow.

        Args:
            workflow_id: ID of workflow to pause

        Returns:
            True if paused successfully
        """
        ...

    @abstractmethod
    async def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow.

        Args:
            workflow_id: ID of workflow to resume

        Returns:
            True if resumed successfully
        """
        ...

    @abstractmethod
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running or paused workflow.

        Args:
            workflow_id: ID of workflow to cancel

        Returns:
            True if cancelled successfully
        """
        ...

    @abstractmethod
    async def get_workflow_state(self, workflow_id: str) -> WorkflowResult | None:
        """Get current state of a workflow.

        Args:
            workflow_id: ID of workflow to query

        Returns:
            WorkflowResult if found, None otherwise
        """
        ...

    @abstractmethod
    async def list_workflows(
        self,
        state: WorkflowState | None = None,
        limit: int = 100,
    ) -> list[WorkflowResult]:
        """List workflows, optionally filtered by state.

        Args:
            state: Optional state filter
            limit: Maximum number of results

        Returns:
            List of WorkflowResult objects
        """
        ...


class WorkflowService(ServiceBase):
    """Base service for workflow management.

    Provides workflow orchestration with integration to Events System and Task Queue.
    """

    @depends.inject
    def __init__(
        self,
        engine: WorkflowEngine,
        config: Inject[Config],
        logger: Inject[Logger],
        settings: WorkflowSettings | None = None,
        service_config: WorkflowConfig | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config
            or WorkflowConfig(service_id="workflow", name="Workflow Service"),
            settings=settings or WorkflowSettings(),
        )

        # Store injected dependencies
        self.config = config
        self.logger = logger

        self._engine = engine
        self._settings: WorkflowSettings = self._settings  # type: ignore
        self._active_workflows: dict[str, asyncio.Task[WorkflowResult]] = {}
        self._workflow_semaphore = asyncio.Semaphore(
            self._settings.max_concurrent_workflows,
        )

    async def _initialize(self) -> None:
        """Initialize workflow service."""
        self.logger.info("Initializing workflow service")

        # Initialize workflow engine if it has initialization
        if hasattr(self._engine, "initialize"):
            await self._engine.initialize()

        self.logger.info("Workflow service initialized")

    async def _shutdown(self) -> None:
        """Shutdown workflow service."""
        self.logger.info("Shutting down workflow service")

        # Cancel all active workflows
        for workflow_id, task in self._active_workflows.items():
            self.logger.info(f"Cancelling workflow {workflow_id}")
            task.cancel()

        # Wait for cancellation
        if self._active_workflows:
            await asyncio.gather(
                *self._active_workflows.values(),
                return_exceptions=True,
            )

        # Shutdown workflow engine if it has shutdown
        if hasattr(self._engine, "shutdown"):
            await self._engine.shutdown()

        self.logger.info("Workflow service shut down")

    async def _health_check(self) -> dict[str, t.Any]:
        """Check workflow service health."""
        return {
            "status": "ok",
            "active_workflows": len(self._active_workflows),
            "max_concurrent": self._settings.max_concurrent_workflows,
        }

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, t.Any] | None = None,
    ) -> str:
        """Submit a workflow for execution.

        Args:
            workflow: Workflow definition to execute
            context: Optional execution context

        Returns:
            Workflow ID for tracking
        """
        self.increment_requests()

        async with self._workflow_semaphore:
            # Create execution task
            task = asyncio.create_task(
                self._execute_workflow_with_tracking(workflow, context),
            )
            self._active_workflows[workflow.workflow_id] = task

            return workflow.workflow_id

    async def _execute_workflow_with_tracking(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, t.Any] | None,
    ) -> WorkflowResult:
        """Execute workflow with tracking and cleanup."""
        try:
            return await self._engine.execute(workflow, context)
        except Exception as e:
            self.record_error(e)
            self.logger.exception(f"Workflow {workflow.workflow_id} failed: {e}")
            raise
        finally:
            # Remove from active workflows
            self._active_workflows.pop(workflow.workflow_id, None)

    async def get_workflow_result(self, workflow_id: str) -> WorkflowResult | None:
        """Get workflow execution result.

        Args:
            workflow_id: ID of workflow to query

        Returns:
            WorkflowResult if available, None otherwise
        """
        # Check if still executing
        if workflow_id in self._active_workflows:
            task = self._active_workflows[workflow_id]
            if task.done():
                with suppress(Exception):
                    return task.result()

        # Query engine for state
        return await self._engine.get_workflow_state(workflow_id)

    async def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow."""
        return await self._engine.pause_workflow(workflow_id)

    async def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow."""
        return await self._engine.resume_workflow(workflow_id)

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow."""
        # Cancel task if still running
        if workflow_id in self._active_workflows:
            task = self._active_workflows[workflow_id]
            task.cancel()

        return await self._engine.cancel_workflow(workflow_id)

    async def list_workflows(
        self,
        state: WorkflowState | None = None,
        limit: int = 100,
    ) -> list[WorkflowResult]:
        """List workflows by state."""
        return await self._engine.list_workflows(state, limit)
