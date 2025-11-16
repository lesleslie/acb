"""Tests for workflow base components and service."""

import asyncio
import pytest

from acb.workflows import (
    BasicWorkflowEngine,
    StepState,
    WorkflowDefinition,
    WorkflowService,
    WorkflowSettings,
    WorkflowState,
    WorkflowStep,
)


class TestWorkflowState:
    """Test workflow state enum."""

    def test_workflow_states(self):
        """Test all workflow states are defined."""
        assert WorkflowState.PENDING.value == "pending"
        assert WorkflowState.RUNNING.value == "running"
        assert WorkflowState.COMPLETED.value == "completed"
        assert WorkflowState.FAILED.value == "failed"
        assert WorkflowState.CANCELLED.value == "cancelled"
        assert WorkflowState.PAUSED.value == "paused"


class TestStepState:
    """Test step state enum."""

    def test_step_states(self):
        """Test all step states are defined."""
        assert StepState.PENDING.value == "pending"
        assert StepState.RUNNING.value == "running"
        assert StepState.COMPLETED.value == "completed"
        assert StepState.FAILED.value == "failed"
        assert StepState.SKIPPED.value == "skipped"
        assert StepState.RETRYING.value == "retrying"


class TestWorkflowStep:
    """Test workflow step model."""

    def test_step_creation(self):
        """Test creating a workflow step."""
        step = WorkflowStep(
            step_id="test-step",
            name="Test Step",
            action="test_action",
            params={"key": "value"},
        )

        assert step.step_id == "test-step"
        assert step.name == "Test Step"
        assert step.action == "test_action"
        assert step.params == {"key": "value"}
        assert step.retry_attempts == 3
        assert step.retry_delay == 1.0

    def test_step_with_dependencies(self):
        """Test step with dependencies."""
        step = WorkflowStep(
            step_id="step2",
            name="Step 2",
            action="process",
            depends_on=["step1"],
        )

        assert step.depends_on == ["step1"]

    def test_step_parallel_flag(self):
        """Test parallel execution flag."""
        step = WorkflowStep(
            step_id="parallel-step",
            name="Parallel Step",
            action="process",
            parallel=True,
        )

        assert step.parallel is True


class TestWorkflowDefinition:
    """Test workflow definition model."""

    def test_workflow_creation(self):
        """Test creating a workflow definition."""
        workflow = WorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1", action="action1"),
            ],
        )

        assert workflow.workflow_id == "test-workflow"
        assert workflow.name == "Test Workflow"
        assert workflow.description == "A test workflow"
        assert len(workflow.steps) == 1
        assert workflow.timeout == 3600.0

    def test_workflow_with_multiple_steps(self):
        """Test workflow with multiple steps."""
        workflow = WorkflowDefinition(
            workflow_id="multi-step",
            name="Multi-Step Workflow",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1", action="action1"),
                WorkflowStep(
                    step_id="step2",
                    name="Step 2",
                    action="action2",
                    depends_on=["step1"],
                ),
                WorkflowStep(
                    step_id="step3",
                    name="Step 3",
                    action="action3",
                    depends_on=["step2"],
                ),
            ],
        )

        assert len(workflow.steps) == 3
        assert workflow.steps[1].depends_on == ["step1"]
        assert workflow.steps[2].depends_on == ["step2"]


class TestWorkflowSettings:
    """Test workflow settings."""

    def test_default_settings(self, mock_config):
        """Test default workflow settings."""
        settings = WorkflowSettings()

        assert settings.enabled is True
        assert settings.max_concurrent_workflows == 10
        assert settings.max_concurrent_steps == 5
        assert settings.default_timeout == 3600.0

    def test_custom_settings(self, mock_config):
        """Test custom workflow settings."""
        settings = WorkflowSettings(
            max_concurrent_workflows=20, max_concurrent_steps=10, default_timeout=7200.0
        )

        assert settings.max_concurrent_workflows == 20
        assert settings.max_concurrent_steps == 10
        assert settings.default_timeout == 7200.0


@pytest.mark.asyncio
class TestBasicWorkflowEngine:
    """Test basic workflow engine."""

    @pytest.fixture
    def engine(self):
        """Create workflow engine instance."""
        engine = BasicWorkflowEngine(max_concurrent_steps=5)

        # Register test actions
        async def test_action(**kwargs):
            return f"Executed with {kwargs}"

        async def failing_action(**kwargs):
            raise ValueError("Test failure")

        engine.register_action("test_action", test_action)
        engine.register_action("failing_action", failing_action)

        return engine

    async def test_single_step_workflow(self, engine):
        """Test executing a single-step workflow."""
        workflow = WorkflowDefinition(
            workflow_id="single-step",
            name="Single Step",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1", action="test_action"),
            ],
        )

        result = await engine.execute(workflow)

        assert result.workflow_id == "single-step"
        assert result.state == WorkflowState.COMPLETED
        assert len(result.steps) == 1
        assert result.steps[0].state == StepState.COMPLETED

    async def test_multi_step_workflow(self, engine):
        """Test executing a multi-step workflow with dependencies."""
        workflow = WorkflowDefinition(
            workflow_id="multi-step",
            name="Multi Step",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1", action="test_action"),
                WorkflowStep(
                    step_id="step2",
                    name="Step 2",
                    action="test_action",
                    depends_on=["step1"],
                ),
                WorkflowStep(
                    step_id="step3",
                    name="Step 3",
                    action="test_action",
                    depends_on=["step2"],
                ),
            ],
        )

        result = await engine.execute(workflow)

        assert result.state == WorkflowState.COMPLETED
        assert len(result.steps) == 3
        assert all(step.state == StepState.COMPLETED for step in result.steps)

    async def test_parallel_steps(self, engine):
        """Test executing parallel steps."""
        workflow = WorkflowDefinition(
            workflow_id="parallel",
            name="Parallel Steps",
            steps=[
                WorkflowStep(
                    step_id="step1", name="Step 1", action="test_action", parallel=True
                ),
                WorkflowStep(
                    step_id="step2", name="Step 2", action="test_action", parallel=True
                ),
                WorkflowStep(
                    step_id="step3",
                    name="Step 3",
                    action="test_action",
                    depends_on=["step1", "step2"],
                ),
            ],
        )

        result = await engine.execute(workflow)

        assert result.state == WorkflowState.COMPLETED
        assert len(result.steps) == 3

    async def test_failed_step(self, engine):
        """Test workflow with a failed step."""
        workflow = WorkflowDefinition(
            workflow_id="failed-step",
            name="Failed Step",
            steps=[
                WorkflowStep(
                    step_id="failing", name="Failing Step", action="failing_action"
                ),
            ],
        )

        result = await engine.execute(workflow)

        assert result.state == WorkflowState.FAILED
        assert result.steps[0].state == StepState.FAILED
        assert "Test failure" in result.steps[0].error

    async def test_continue_on_error(self, engine):
        """Test continue_on_error flag."""
        workflow = WorkflowDefinition(
            workflow_id="continue-on-error",
            name="Continue on Error",
            continue_on_error=True,
            steps=[
                WorkflowStep(
                    step_id="failing", name="Failing Step", action="failing_action"
                ),
                WorkflowStep(step_id="step2", name="Step 2", action="test_action"),
            ],
        )

        result = await engine.execute(workflow)

        assert result.state == WorkflowState.FAILED  # Still failed overall
        assert result.steps[0].state == StepState.FAILED
        assert result.steps[1].state == StepState.COMPLETED

    async def test_get_workflow_state(self, engine):
        """Test retrieving workflow state."""
        workflow = WorkflowDefinition(
            workflow_id="state-test",
            name="State Test",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1", action="test_action"),
            ],
        )

        result = await engine.execute(workflow)
        stored_result = await engine.get_workflow_state("state-test")

        assert stored_result is not None
        assert stored_result.workflow_id == result.workflow_id
        assert stored_result.state == result.state

    async def test_cancel_workflow(self, engine):
        """Test cancelling a workflow."""
        workflow = WorkflowDefinition(
            workflow_id="cancel-test",
            name="Cancel Test",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1", action="test_action"),
            ],
        )

        # Execute and cancel
        await engine.execute(workflow)
        cancelled = await engine.cancel_workflow("cancel-test")

        assert cancelled is True

        # Verify state
        stored_result = await engine.get_workflow_state("cancel-test")
        assert stored_result.state == WorkflowState.CANCELLED


@pytest.mark.asyncio
class TestWorkflowService:
    """Test workflow service."""

    @pytest.fixture
    def engine(self):
        """Create workflow engine."""
        engine = BasicWorkflowEngine(max_concurrent_steps=5)

        async def test_action(**kwargs):
            return "success"

        engine.register_action("test_action", test_action)
        return engine

    @pytest.fixture
    async def service(self, engine, mock_config):
        """Create workflow service."""
        service = WorkflowService(engine=engine)
        await service.initialize()
        yield service
        await service.shutdown()

    async def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.status.value == "active"
        assert service.is_healthy is True

    async def test_submit_workflow(self, service):
        """Test submitting a workflow."""
        workflow = WorkflowDefinition(
            workflow_id="submit-test",
            name="Submit Test",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1", action="test_action"),
            ],
        )

        workflow_id = await service.submit_workflow(workflow)

        assert workflow_id == "submit-test"

        # Wait for completion
        await asyncio.sleep(0.1)

        result = await service.get_workflow_result(workflow_id)
        assert result is not None
        assert result.state == WorkflowState.COMPLETED

    async def test_health_check(self, service):
        """Test service health check."""
        health = await service.health_check()

        assert health["healthy"] is True
        assert health["service_id"] == "workflow"
        assert "active_workflows" in health["service_specific"]
