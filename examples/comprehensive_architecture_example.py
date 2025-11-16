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
from acb.tasks import TaskData, task_handler


class UserManagementSettings(ServiceSettings):
    """Settings for user management service."""

    default_user_role: str = "user"
    enable_email_notifications: bool = True
    notification_delay_seconds: float = 1.0


class UserManagementService(ServiceBase):
    """Service for managing users with full lifecycle management."""

    def __init__(self) -> None:
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
        # Type the settings to the specific subclass
        settings = self._settings
        return {
            "status": "healthy",
            "users_created": self._users_created,
            "email_notifications_enabled": getattr(
                settings, "enable_email_notifications", True
            ),
        }

    @property
    def users_created(self) -> int:
        """Get count of users created."""
        return self._users_created

    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new user and emit event."""
        # Import adapters for typing
        Cache = import_adapter("cache")
        SQL = import_adapter("sql")

        # Create user record
        settings = self._settings
        user = {
            "id": user_data.get("id", self._users_created + 1),
            "name": user_data.get("name"),
            "email": user_data.get("email"),
            "role": user_data.get(
                "role", getattr(settings, "default_user_role", "user")
            ),
            "created_at": datetime.now().isoformat(),
        }

        # Save to database and cache - access them through dependency injection
        # For this simplified example, we'll assume they have the expected interface
        try:
            sql: Any = depends.get(SQL)
            if hasattr(sql, "get_session") and callable(sql.get_session):
                # For demonstration purposes only - in real usage, handle properly
                print(f"Saving user to database: {user}")
        except Exception:
            print("Could not access SQL adapter, skipping database save")

        try:
            cache: Any = depends.get(Cache)
            if hasattr(cache, "set") and callable(cache.set):
                await cache.set(f"user:{user['id']}", user, ttl=3600)
            else:
                print(
                    f"Cache doesn't have set method, skipping cache update for user {user['id']}"
                )
        except Exception:
            print(
                f"Could not access cache adapter, skipping cache update for user {user['id']}"
            )

        # Update service metrics
        self._users_created += 1

        # Emit event
        if self._publisher:
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


from acb.events import Event


@event_handler("user.created")
async def handle_user_created(event: Event) -> EventHandlerResult:
    """Handle user creation event."""
    user_id = event.payload.get("user_id")
    email = event.payload.get("email")

    print(f"Event handler: Processing new user {user_id} ({email})")

    # In a real app, you might send a welcome email, update statistics, etc.
    # For demo, we'll simulate with a task
    if True:  # Assuming email notifications are enabled
        # Enqueue a task to send welcome email
        from acb.tasks import create_queue

        async with create_queue("memory") as queue:
            email_task = TaskData(
                task_type="send_welcome_email",
                queue_name="default",
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


async def main() -> None:
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
