"""Tests for the ACB MCP orchestrator module."""

from unittest.mock import AsyncMock, Mock, patch

import asyncio
import pytest

from acb.mcp.orchestrator import WorkflowOrchestrator
from acb.mcp.registry import ComponentRegistry


class TestWorkflowOrchestrator:
    """Test the WorkflowOrchestrator class."""

    def test_initialization(self) -> None:
        """Test basic initialization of WorkflowOrchestrator."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        assert orchestrator.component_registry == mock_registry
        assert hasattr(orchestrator, "logger")
        assert orchestrator._active_workflows == {}
        assert orchestrator._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_first_time(self) -> None:
        """Test initializing the orchestrator for the first time."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        with patch.object(orchestrator, "logger") as mock_logger:
            await orchestrator.initialize()

            assert orchestrator._initialized is True
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self) -> None:
        """Test that initialize is skipped when already initialized."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)
        orchestrator._initialized = True

        with patch.object(orchestrator, "logger") as mock_logger:
            await orchestrator.initialize()
            # The logger should not have been called since it was already initialized
            mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self) -> None:
        """Test executing a workflow successfully."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Mock the registry to return actions and adapters
        mock_action_category = Mock()
        mock_action_category.some_action = AsyncMock(return_value="action_result")
        mock_registry.get_actions.return_value = {"test_action": mock_action_category}

        mock_adapter = Mock()
        mock_adapter.some_method = AsyncMock(return_value="adapter_result")
        mock_registry.get_adapter.return_value = mock_adapter

        steps = [
            {
                "name": "step1",
                "type": "action",
                "component": "test_action",
                "action": "some_action",
                "parameters": {"param": "value"},
            },
            {
                "name": "step2",
                "type": "adapter",
                "component": "test_adapter",
                "action": "some_method",
                "parameters": {"param": "value"},
            },
        ]

        with patch.object(orchestrator, "logger"):
            result = await orchestrator.execute_workflow("test_workflow", steps)

            assert result["workflow"] == "test_workflow"
            assert result["status"] == "completed"
            assert "results" in result
            assert result["results"]["step1"] == "action_result"
            assert result["results"]["step2"] == "adapter_result"

    @pytest.mark.asyncio
    async def test_execute_workflow_with_exception(self) -> None:
        """Test executing a workflow that fails."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        steps = [
            {
                "name": "step1",
                "type": "action",
                "component": "test_action",
                "action": "some_action",
                "parameters": {"param": "value"},
            }
        ]

        # Mock the registry to raise an exception
        mock_registry.get_actions.side_effect = ValueError("Test error")

        with patch.object(orchestrator, "logger"):
            result = await orchestrator.execute_workflow("failing_workflow", steps)

            assert result["workflow"] == "failing_workflow"
            assert result["status"] == "failed"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_workflow_unsupported_type(self) -> None:
        """Test executing a workflow with unsupported component type."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        steps = [
            {
                "name": "step1",
                "type": "unsupported_type",
                "component": "test_component",
                "action": "some_action",
                "parameters": {"param": "value"},
            }
        ]

        with patch.object(orchestrator, "logger"):
            result = await orchestrator.execute_workflow("invalid_workflow", steps)

            assert result["workflow"] == "invalid_workflow"
            assert result["status"] == "failed"
            assert "error" in result
            assert "Unsupported component type" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_action_step_success(self) -> None:
        """Test executing an action step successfully."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Mock an action category with a function
        mock_action_func = AsyncMock(return_value="test_result")
        mock_action_category = Mock()
        type(mock_action_category).some_action = mock_action_func

        mock_registry.get_actions.return_value = {"test_category": mock_action_category}

        result = await orchestrator._execute_action_step(
            "test_category", "some_action", {"param": "value"}
        )

        assert result == "test_result"
        mock_action_func.assert_called_once_with(param="value")

    @pytest.mark.asyncio
    async def test_execute_action_step_category_not_found(self) -> None:
        """Test executing an action step when category is not found."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        mock_registry.get_actions.return_value = {}

        with pytest.raises(ValueError, match="Action category 'nonexistent' not found"):
            await orchestrator._execute_action_step(
                "nonexistent", "some_action", {"param": "value"}
            )

    @pytest.mark.asyncio
    async def test_execute_action_step_action_not_found(self) -> None:
        """Test executing an action step when action is not found."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Mock an action category without the requested action
        mock_action_category = Mock()

        mock_registry.get_actions.return_value = {"test_category": mock_action_category}

        with pytest.raises(
            ValueError,
            match="Action 'nonexistent_action' not found in category 'test_category'",
        ):
            await orchestrator._execute_action_step(
                "test_category", "nonexistent_action", {"param": "value"}
            )

    @pytest.mark.asyncio
    async def test_execute_adapter_step_success(self) -> None:
        """Test executing an adapter step successfully."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Mock an adapter with a method
        mock_adapter_method = AsyncMock(return_value="adapter_result")
        mock_adapter = Mock()
        type(mock_adapter).some_method = mock_adapter_method

        mock_registry.get_adapter.return_value = mock_adapter

        result = await orchestrator._execute_adapter_step(
            "test_adapter", "some_method", {"param": "value"}
        )

        assert result == "adapter_result"
        mock_adapter_method.assert_called_once_with(param="value")

    @pytest.mark.asyncio
    async def test_execute_adapter_step_not_found(self) -> None:
        """Test executing an adapter step when adapter is not found."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        mock_registry.get_adapter.return_value = None

        with pytest.raises(ValueError, match="Adapter 'nonexistent' not found"):
            await orchestrator._execute_adapter_step(
                "nonexistent", "some_method", {"param": "value"}
            )

    @pytest.mark.asyncio
    async def test_execute_adapter_step_method_not_found(self) -> None:
        """Test executing an adapter step when method is not found."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Mock an adapter without the requested method
        mock_adapter = Mock()

        mock_registry.get_adapter.return_value = mock_adapter

        with pytest.raises(
            ValueError,
            match="Method 'nonexistent_method' not found in adapter 'test_adapter'",
        ):
            await orchestrator._execute_adapter_step(
                "test_adapter", "nonexistent_method", {"param": "value"}
            )

    @pytest.mark.asyncio
    async def test_start_background_workflow(self) -> None:
        """Test starting a background workflow."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Mock the execute_workflow method to avoid full execution
        with patch.object(
            orchestrator, "execute_workflow", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"status": "completed"}

            await orchestrator.start_background_workflow("bg_workflow", [])

            assert "bg_workflow" in orchestrator._active_workflows
            # Wait a bit to let the task start
            await asyncio.sleep(0.01)
            # Check that the task is running or completed
            task = orchestrator._active_workflows["bg_workflow"]
            if not task.done():
                task.cancel()  # Clean up the task

    @pytest.mark.asyncio
    async def test_get_workflow_status_completed(self) -> None:
        """Test getting status of a completed workflow."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Create a completed task
        completed_task = asyncio.create_task(asyncio.sleep(0.01))
        await completed_task  # Wait for it to complete

        orchestrator._active_workflows["completed_workflow"] = completed_task

        status = await orchestrator.get_workflow_status("completed_workflow")
        assert status == "completed"

    @pytest.mark.asyncio
    async def test_get_workflow_status_running(self) -> None:
        """Test getting status of a running workflow."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Create a task that will run for a while
        async def long_running_task():
            await asyncio.sleep(0.1)
            return "done"

        running_task = asyncio.create_task(long_running_task())
        orchestrator._active_workflows["running_workflow"] = running_task

        try:
            status = await orchestrator.get_workflow_status("running_workflow")
            # The task might still be running or already completed by now
            assert status in ["running", "completed"]
        finally:
            # Clean up the task if it's still running
            if not running_task.done():
                running_task.cancel()

    @pytest.mark.asyncio
    async def test_get_workflow_status_nonexistent(self) -> None:
        """Test getting status of a nonexistent workflow."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        status = await orchestrator.get_workflow_status("nonexistent_workflow")
        assert status is None

    @pytest.mark.asyncio
    async def test_cleanup(self) -> None:
        """Test cleaning up the orchestrator."""
        mock_registry = Mock(spec=ComponentRegistry)
        orchestrator = WorkflowOrchestrator(mock_registry)

        # Add a task to the active workflows
        async def long_task():
            await asyncio.sleep(1)  # This will be cancelled

        task = asyncio.create_task(long_task())
        orchestrator._active_workflows["test_task"] = task
        orchestrator._initialized = True

        with patch.object(orchestrator, "logger") as mock_logger:
            await orchestrator.cleanup()

            # Check that the task was cancelled
            assert task.cancelled()
            # Check that workflows dict is cleared
            assert orchestrator._active_workflows == {}
            # Check that initialized flag is reset
            assert orchestrator._initialized is False
            # Check that logger was called
            mock_logger.info.assert_called()
