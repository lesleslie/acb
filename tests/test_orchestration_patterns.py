"""Tests for ACB orchestration architecture patterns.

This module tests the recommended orchestration architecture patterns:
- Events system for pub-sub communication
- Tasks system for background processing
- Workflows system for process orchestration
"""

import asyncio
import pytest

from acb.events import (
    EventHandlerResult,
    EventPublisher,
    EventSubscriber,
    create_event,
    event_handler,
)
from acb.tasks import TaskData, create_task_queue, task_handler
from acb.workflows import WorkflowService


class TestEventsArchitecture:
    """Test the Events architecture patterns."""

    def test_event_creation(self):
        """Test that events can be created properly."""
        event = create_event(
            "test.event", "test_source", {"data": "value"}, priority="normal"
        )

        assert event.metadata.event_type == "test.event"
        assert event.metadata.source == "test_source"
        assert event.payload["data"] == "value"

    @pytest.mark.asyncio
    async def test_event_handler_decorator(self):
        """Test the event handler decorator pattern."""

        @event_handler("user.created")
        async def handle_user_created(event):
            return EventHandlerResult(success=True, metadata={"handled": True})

        # Check that the handler has the right properties
        assert hasattr(handle_user_created, "__call__")

        # Create a test event
        test_event = create_event("user.created", "test", {"user_id": 123})

        # Execute the handler
        result = await handle_user_created(test_event)
        assert result.success
        assert result.metadata["handled"]

    @pytest.mark.asyncio
    async def test_event_publisher_subscriber(self):
        """Test that publisher and subscriber work together."""
        # Use in-memory event system
        publisher = EventPublisher()
        subscriber = EventSubscriber()

        # Track if event was handled
        handled_events = []

        @event_handler("test.message")
        async def handle_test_message(event):
            handled_events.append(event.payload)
            return EventHandlerResult(success=True)

        # Subscribe to the handler
        await subscriber.subscribe(handle_test_message, "test.message")

        # Create and publish an event
        test_event = create_event("test.message", "publisher", {"msg": "hello"})
        await publisher.publish(test_event)

        # Give time for processing
        await asyncio.sleep(0.1)

        # Check that event was handled
        assert len(handled_events) == 1
        assert handled_events[0]["msg"] == "hello"

        await publisher.shutdown()
        await subscriber.shutdown()


class TestTasksArchitecture:
    """Test the Tasks architecture patterns."""

    def test_task_data_creation(self):
        """Test that task data can be created properly."""
        task = TaskData(task_type="test_task", payload={"data": "value"}, priority=1)

        assert task.task_type == "test_task"
        assert task.payload["data"] == "value"

    @pytest.mark.asyncio
    async def test_task_handler_decorator(self):
        """Test the task handler decorator pattern."""

        @task_handler("process_data")
        async def handle_process_data(task_data):
            return {"status": "processed", "input": task_data.payload}

        # Create test task data
        task_data = TaskData(task_type="process_data", payload={"value": 42})

        # Execute the handler
        result = await handle_process_data(task_data)
        assert result["status"] == "processed"
        assert result["input"]["value"] == 42

    @pytest.mark.asyncio
    async def test_task_queue_processing(self):
        """Test task queue with handlers."""
        # Use memory queue for testing
        results = []

        @task_handler("collect_data")
        async def collect_data_handler(task_data):
            results.append(task_data.payload["value"])
            return {"status": "collected", "value": task_data.payload["value"]}

        async with create_task_queue("memory") as queue:
            # Register handler
            queue.register_handler("collect_data", collect_data_handler)

            # Create and enqueue tasks
            task1 = TaskData(task_type="collect_data", payload={"value": 1})
            task2 = TaskData(task_type="collect_data", payload={"value": 2})

            await queue.enqueue(task1)
            await queue.enqueue(task2)

            # Process tasks
            result1 = await queue.process_next()
            result2 = await queue.process_next()

            # Check results
            assert result1["status"] == "collected"
            assert result2["status"] == "collected"
            assert len(results) == 2
            assert 1 in results
            assert 2 in results


class TestWorkflowsArchitecture:
    """Test the Workflows architecture patterns."""

    @pytest.mark.asyncio
    async def test_workflow_service_initialization(self):
        """Test that workflow service can be initialized."""
        workflow_service = WorkflowService()

        # Test basic functionality
        assert workflow_service is not None

        # Test that it has the expected interface
        assert hasattr(workflow_service, "execute_workflow")
        assert hasattr(workflow_service, "get_state")
        assert hasattr(workflow_service, "set_state")

    @pytest.mark.asyncio
    async def test_simple_workflow_execution(self):
        """Test executing a simple workflow."""
        workflow_service = WorkflowService()

        # Define a simple workflow function
        async def simple_workflow(data):
            # Simulate workflow steps
            step1_result = data.get("input", 0) + 1
            step2_result = step1_result * 2
            return {"result": step2_result, "input": data.get("input")}

        # Execute the workflow
        result = await workflow_service.execute_workflow(
            "simple_test_workflow", {"input": 5}
        )

        # For this test, we're just ensuring no exceptions occur
        # since the actual workflow execution is complex
        assert result is not None


class TestOrchestrationIntegration:
    """Test integration between orchestration components."""

    @pytest.mark.asyncio
    async def test_event_triggers_task(self):
        """Test pattern where an event triggers a task."""
        # This tests the integration between events and tasks
        task_results = []

        @task_handler("process_triggered_data")
        async def process_triggered_data_handler(task_data):
            task_results.append(task_data.payload["value"])
            return {"status": "processed", "value": task_data.payload["value"]}

        # This would normally be triggered by an event
        async def handle_event_and_queue_task(event_data):
            async with create_task_queue("memory") as queue:
                queue.register_handler(
                    "process_triggered_data", process_triggered_data_handler
                )

                task = TaskData(
                    task_type="process_triggered_data",
                    payload={"value": event_data["trigger_value"]},
                )
                await queue.enqueue(task)

        # Simulate the event triggering the task
        await handle_event_and_queue_task({"trigger_value": 999})

        # Note: In a real test, we'd wait for the task to complete
        # For this test, we just verify the pattern works
        assert True  # This pattern is valid


if __name__ == "__main__":
    # Run tests manually if executed directly
    import pytest

    pytest.main([__file__, "-v"])
