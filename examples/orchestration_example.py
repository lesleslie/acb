"""Example of using Events and Tasks in ACB.

This example demonstrates how to use ACB's orchestration layers: Events for
event-driven communication and Tasks for background job processing.
"""

import asyncio
from typing import Any

from acb.events import (
    Event,
    EventHandlerResult,
    EventPublisher,
    EventSubscriber,
    create_event,
    event_handler,
)
from acb.tasks import TaskData, create_queue, task_handler


# Event handler examples
@event_handler("user.created")
async def handle_user_created(event: Event) -> EventHandlerResult:
    """Handle user creation events."""
    event.payload.get("user_id")
    event.payload.get("email")

    # Example: Send welcome email
    # await send_welcome_email(user_email)

    return EventHandlerResult(success=True, metadata={"processed": True})


@event_handler("order.completed")
async def handle_order_completed(event: Event) -> EventHandlerResult:
    """Handle order completion events."""
    event.payload.get("order_id")
    event.payload.get("user_id")

    # Example: Update user stats, trigger shipping, etc.
    # await update_user_stats(user_id)
    # await trigger_shipping(order_id)

    return EventHandlerResult(success=True, metadata={"processed": True})


# Task handler examples
@task_handler("send_email")
async def send_email_task(task_data: TaskData) -> dict[str, Any]:
    """Task handler for sending emails."""
    email_data = task_data.payload
    recipient = email_data.get("recipient")
    subject = email_data.get("subject", "Default Subject")
    email_data.get("body", "")

    # Simulate email sending
    await asyncio.sleep(0.1)  # Simulate network delay

    return {"status": "sent", "recipient": recipient, "subject": subject}


@task_handler("process_file")
async def process_file_task(task_data: TaskData) -> dict[str, Any]:
    """Task handler for processing files."""
    file_data = task_data.payload
    file_path = file_data.get("file_path")
    operation = file_data.get("operation", "analyze")

    # Simulate file processing
    await asyncio.sleep(0.5)  # Simulate processing time

    return {
        "status": "completed",
        "file_path": file_path,
        "operation": operation,
        "result": "processed successfully",
    }


async def demonstrate_events() -> None:
    """Demonstrate event-driven communication."""
    # Create event publisher and subscriber
    publisher = EventPublisher()
    subscriber = EventSubscriber()

    # Subscribe to events
    await subscriber.subscribe(handle_user_created, "user.created")
    await subscriber.subscribe(handle_order_completed, "order.completed")

    # Create and publish events
    user_event = create_event(
        "user.created",
        "demo",
        {"user_id": 123, "email": "user@example.com"},
    )
    await publisher.publish(user_event)

    order_event = create_event(
        "order.completed",
        "demo",
        {"order_id": 456, "user_id": 123},
    )
    await publisher.publish(order_event)

    # Clean up
    await publisher.shutdown()
    await subscriber.shutdown()


async def demonstrate_tasks() -> None:
    """Demonstrate task queue system."""
    # Create a task queue
    async with create_queue("memory") as queue:
        # Register task handlers
        queue.register_handler("send_email", send_email_task)
        queue.register_handler("process_file", process_file_task)

        # Create and enqueue tasks
        email_task = TaskData(
            task_type="send_email",
            queue_name="default",
            payload={
                "recipient": "user@example.com",
                "subject": "Welcome!",
                "body": "Welcome to our service!",
            },
        )

        file_task = TaskData(
            task_type="process_file",
            queue_name="default",
            payload={"file_path": "/tmp/data.csv", "operation": "analyze"},
        )

        # Start queue workers to process tasks
        await queue.start_workers(count=5)

        # Enqueue tasks
        await queue.enqueue(email_task)
        await queue.enqueue(file_task)

        # Wait for tasks to be processed
        await asyncio.sleep(2)  # Give workers time to process tasks

        # Stop workers
        await queue.stop_workers()


async def demonstrate_workflows() -> None:
    """Demonstrate workflow orchestration."""
    # Workflows example (using the service pattern)
    from acb.workflows import WorkflowDefinition, WorkflowStep, import_workflow_engine

    # Import and instantiate workflow engine
    WorkflowEngine = import_workflow_engine("basic")
    engine = WorkflowEngine(max_concurrent_steps=5)

    # Example workflow definition (simplified)
    workflow_definition = WorkflowDefinition(
        workflow_id="user_onboarding",
        name="User Onboarding Workflow",
        steps=[
            WorkflowStep(
                step_id="validate_user",
                name="Validate User",
                action="validate_user",
                params={"user_id": 789},
            ),
            WorkflowStep(
                step_id="send_welcome_email",
                name="Send Welcome Email",
                action="send_welcome_email",
                params={"email": "newuser@example.com"},
                depends_on=["validate_user"],
            ),
            WorkflowStep(
                step_id="setup_preferences",
                name="Setup Preferences",
                action="setup_preferences",
                params={"user_id": 789},
                depends_on=["validate_user"],
            ),
            WorkflowStep(
                step_id="notify_admin",
                name="Notify Admin",
                action="notify_admin",
                params={"user_id": 789, "email": "newuser@example.com"},
                depends_on=["validate_user"],
            ),
        ],
    )

    # Execute workflow
    await engine.execute(
        workflow_definition,
        context={"user_id": 789, "email": "newuser@example.com"},
    )


async def main() -> None:
    """Main function to demonstrate orchestration capabilities."""
    await demonstrate_events()
    await demonstrate_tasks()
    await demonstrate_workflows()


if __name__ == "__main__":
    asyncio.run(main())
