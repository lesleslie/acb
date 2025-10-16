"""Example of using Events and Tasks in ACB.

This example demonstrates how to use ACB's orchestration layers: Events for
event-driven communication and Tasks for background job processing.
"""

import asyncio
from typing import Any

from acb.events import (
    EventHandlerResult,
    EventPublisher,
    EventSubscriber,
    create_event,
    event_handler,
)
from acb.tasks import TaskData, create_task_queue, task_handler


# Event handler examples
@event_handler("user.created")
async def handle_user_created(event):
    """Handle user creation events."""
    user_id = event.payload.get("user_id")
    user_email = event.payload.get("email")

    print(f"Processing user creation: {user_id} ({user_email})")

    # Example: Send welcome email
    # await send_welcome_email(user_email)

    return EventHandlerResult(success=True, metadata={"processed": True})


@event_handler("order.completed")
async def handle_order_completed(event):
    """Handle order completion events."""
    order_id = event.payload.get("order_id")
    user_id = event.payload.get("user_id")

    print(f"Processing order completion: {order_id} for user {user_id}")

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

    print(f"Sending email to {recipient}: {subject}")

    # Simulate email sending
    await asyncio.sleep(0.1)  # Simulate network delay

    return {"status": "sent", "recipient": recipient, "subject": subject}


@task_handler("process_file")
async def process_file_task(task_data: TaskData) -> dict[str, Any]:
    """Task handler for processing files."""
    file_data = task_data.payload
    file_path = file_data.get("file_path")
    operation = file_data.get("operation", "analyze")

    print(f"Processing file: {file_path} ({operation})")

    # Simulate file processing
    await asyncio.sleep(0.5)  # Simulate processing time

    return {
        "status": "completed",
        "file_path": file_path,
        "operation": operation,
        "result": "processed successfully",
    }


async def demonstrate_events():
    """Demonstrate event-driven communication."""
    print("=== Demonstrating Events System ===")

    # Create event publisher and subscriber
    publisher = EventPublisher()
    subscriber = EventSubscriber()

    # Subscribe to events
    await subscriber.subscribe(handle_user_created, "user.created")
    await subscriber.subscribe(handle_order_completed, "order.completed")

    # Create and publish events
    user_event = create_event(
        "user.created", "demo", {"user_id": 123, "email": "user@example.com"}
    )
    await publisher.publish(user_event)

    order_event = create_event(
        "order.completed", "demo", {"order_id": 456, "user_id": 123}
    )
    await publisher.publish(order_event)

    print("Events published and handlers executed")

    # Clean up
    await publisher.shutdown()
    await subscriber.shutdown()


async def demonstrate_tasks():
    """Demonstrate task queue system."""
    print("\n=== Demonstrating Tasks System ===")

    # Create a task queue
    async with create_task_queue("memory") as queue:
        # Register task handlers
        queue.register_handler("send_email", send_email_task)
        queue.register_handler("process_file", process_file_task)

        # Create and enqueue tasks
        email_task = TaskData(
            task_type="send_email",
            payload={
                "recipient": "user@example.com",
                "subject": "Welcome!",
                "body": "Welcome to our service!",
            },
        )

        file_task = TaskData(
            task_type="process_file",
            payload={"file_path": "/tmp/data.csv", "operation": "analyze"},
        )

        # Enqueue tasks
        email_task_id = await queue.enqueue(email_task)
        file_task_id = await queue.enqueue(file_task)

        print(f"Enqueued tasks: {email_task_id}, {file_task_id}")

        # Process tasks
        await queue.process_next()  # Process email task
        await queue.process_next()  # Process file task

        print("Tasks processed")


async def demonstrate_workflows():
    """Demonstrate workflow orchestration."""
    print("\n=== Demonstrating Workflows System ===")

    # Workflows example (using the service pattern)
    from acb.workflows import WorkflowService

    workflow_service = WorkflowService()

    # Example workflow definition (simplified)
    workflow_definition = {
        "name": "user_onboarding",
        "steps": [
            {"action": "validate_user", "required": True},
            {"action": "send_welcome_email", "required": True},
            {"action": "setup_preferences", "required": False},
            {"action": "notify_admin", "required": True},
        ],
    }

    # Execute workflow
    result = await workflow_service.execute_workflow(
        workflow_definition["name"],
        {"user_id": 789, "email": "newuser@example.com"},
        timeout=300,  # 5 minutes
    )

    print(f"Workflow result: {result}")


async def main():
    """Main function to demonstrate orchestration capabilities."""
    await demonstrate_events()
    await demonstrate_tasks()
    await demonstrate_workflows()

    print("\nAll orchestration examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
