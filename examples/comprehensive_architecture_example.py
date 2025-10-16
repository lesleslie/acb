"""Comprehensive ACB Architecture Example.

This example demonstrates how all ACB architectural layers work together:
- Services: For business logic and lifecycle management
- Orchestration: Events, Tasks, and Workflows for communication and process management
- Adapters: For external system integration
- Core: Configuration and dependency injection
"""

import asyncio
from datetime import datetime
from typing import Any

from acb.adapters import import_adapter
from acb.depends import depends
from acb.events import EventHandlerResult, EventPublisher, create_event, event_handler
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings
from acb.tasks import TaskData, create_task_queue, task_handler


class UserManagementSettings(ServiceSettings):
    """Settings for user management service."""

    default_user_role: str = "user"
    enable_email_notifications: bool = True
    notification_delay_seconds: float = 1.0


class UserManagementService(ServiceBase):
    """Service for managing users with full lifecycle management."""

    def __init__(self):
        service_config = ServiceConfig(
            service_id="user_management_service",
            name="User Management Service",
            description="Handles user lifecycle operations",
            dependencies=["cache", "sql"],
            priority=60,
        )
        super().__init__(service_config, UserManagementSettings())

        # Service state
        self._users_created = 0
        self._publisher: EventPublisher | None = None

    async def _initialize(self) -> None:
        """Initialize the service."""
        self.logger.info(f"Initializing {self.name}")

        # Initialize event publisher
        self._publisher = EventPublisher()
        await self._publisher.initialize()

    async def _shutdown(self) -> None:
        """Shutdown the service."""
        if self._publisher:
            await self._publisher.shutdown()

    async def _health_check(self) -> dict[str, Any]:
        """Check service health."""
        return {
            "status": "healthy",
            "users_created": self._users_created,
            "email_notifications_enabled": self._settings.enable_email_notifications,
        }

    @property
    def users_created(self) -> int:
        """Get count of users created."""
        return self._users_created

    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new user and emit event."""
        # Use adapters
        Cache = import_adapter("cache")
        SQL = import_adapter("sql")

        cache = depends.get(Cache)
        sql = depends.get(SQL)

        # Create user record
        user = {
            "id": user_data.get("id", self._users_created + 1),
            "name": user_data.get("name"),
            "email": user_data.get("email"),
            "role": user_data.get("role", self._settings.default_user_role),
            "created_at": datetime.now().isoformat(),
        }

        # Save to database
        async with sql.get_session():
            # This is a simplified example - in real app you'd use proper ORM patterns
            print(f"Saving user to database: {user}")

        # Save to cache
        await cache.set(f"user:{user['id']}", user, ttl=3600)

        # Update service metrics
        self._users_created += 1

        # Emit event
        user_event = create_event(
            "user.created",
            "user_management_service",
            {
                "user_id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "timestamp": user["created_at"],
            },
        )
        await self._publisher.publish(user_event)

        return user


@event_handler("user.created")
async def handle_user_created(event):
    """Handle user creation event."""
    user_id = event.payload.get("user_id")
    email = event.payload.get("email")

    print(f"Event handler: Processing new user {user_id} ({email})")

    # In a real app, you might send a welcome email, update statistics, etc.
    # For demo, we'll simulate with a task
    if True:  # Assuming email notifications are enabled
        # Enqueue a task to send welcome email
        async with create_task_queue("memory") as queue:
            email_task = TaskData(
                task_type="send_welcome_email",
                payload={"user_email": email, "user_id": user_id},
            )
            await queue.enqueue(email_task)

    return EventHandlerResult(success=True)


@task_handler("send_welcome_email")
async def send_welcome_email_task(task_data: TaskData) -> dict[str, Any]:
    """Task to send welcome email."""
    payload = task_data.payload
    user_email = payload.get("user_email")
    user_id = payload.get("user_id")

    print(f"Task: Sending welcome email to {user_email} (user {user_id})")

    # Simulate email sending delay
    await asyncio.sleep(1.0)

    return {"status": "email_sent", "user_email": user_email, "user_id": user_id}


async def main():
    """Demonstrate the complete architecture."""
    print("=== ACB Architecture Example ===")
    print("Demonstrating Services + Events + Tasks + Adapters working together\n")

    # 1. Create and initialize service
    user_service = UserManagementService()
    await user_service.initialize()

    # 2. Create a user (this triggers events and tasks)
    print("1. Creating a new user...")
    new_user = await user_service.create_user(
        {"name": "John Doe", "email": "john@example.com", "role": "user"}
    )
    print(f"   Created user: {new_user}\n")

    # 3. Wait a bit for event processing and task execution
    print("2. Waiting for event handlers and tasks to execute...")
    await asyncio.sleep(2)  # Allow time for event/task processing
    print("   Event handlers and tasks completed\n")

    # 4. Check service health
    print("3. Checking service health...")
    health = await user_service.health_check()
    print(f"   Health status: {health}\n")

    # 5. Show final metrics
    print("4. Service metrics:")
    print(f"   Total users created: {user_service.users_created}")

    # 6. Shutdown service
    await user_service.shutdown()
    print("\nService shutdown completed")

    print("\n=== Architecture Layers Demonstrated ===")
    print("✓ Services: UserManagementService with lifecycle management")
    print("✓ Events: Event publishing and handling for user creation")
    print("✓ Tasks: Background email sending")
    print("✓ Adapters: Cache and SQL integration")
    print("✓ Core: Dependency injection and configuration")


if __name__ == "__main__":
    asyncio.run(main())
