"""Example of creating and using custom services in ACB.

This example demonstrates how to create custom services that follow ACB's
service architecture patterns with lifecycle management, health checking,
and dependency injection.
"""

import asyncio
import typing as t
from typing import Any

from acb.adapters import import_adapter
from acb.depends import depends
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings


class ExampleServiceSettings(ServiceSettings):
    """Settings for the example service."""

    # Service-specific settings
    processing_delay: float = 1.0  # Delay in seconds for processing
    max_items_per_batch: int = 100


class ExampleService(ServiceBase):
    """An example service demonstrating ACB service patterns."""

    def __init__(self) -> None:
        service_config = ServiceConfig(
            service_id="example_service",
            name="Example Service",
            description="An example service demonstrating ACB service patterns",
            dependencies=["cache"],  # Dependencies this service requires
            priority=75,  # Initialization priority (lower = earlier)
        )
        settings = ExampleServiceSettings()
        super().__init__(service_config, settings)

        # Service-specific state
        self._items_processed: int = 0
        self._processing_queue: asyncio.Queue[t.Any] = asyncio.Queue()

    async def _initialize(self) -> None:
        """Service-specific initialization logic."""
        self.logger.info(f"Initializing {self.name}")

        # Initialize any resources here
        self.logger.info(f"{self.name} initialized successfully")

    async def _shutdown(self) -> None:
        """Service-specific shutdown logic."""
        self.logger.info(f"Shutting down {self.name}")

        # Clean up resources here
        while not self._processing_queue.empty():
            try:
                self._processing_queue.get_nowait()
                # Process remaining items or handle cleanup
            except asyncio.QueueEmpty:
                break

        self.logger.info(f"{self.name} shut down successfully")

    async def _health_check(self) -> dict[str, Any]:
        """Service-specific health check logic."""
        # Type the settings to the specific subclass
        settings: ExampleServiceSettings = self._settings  # type: ignore
        return {
            "status": "healthy",
            "items_processed": self._items_processed,
            "queue_size": self._processing_queue.qsize(),
            "processing_delay": settings.processing_delay,
        }

    async def add_item(self, item: Any) -> None:
        """Add an item to be processed."""
        await self._processing_queue.put(item)
        self.logger.debug(f"Added item to {self.name} queue: {item}")

    async def process_items(self) -> int:
        """Process all items in the queue."""
        processed_count = 0

        while not self._processing_queue.empty():
            try:
                item = self._processing_queue.get_nowait()
                await self._process_item(item)
                processed_count += 1
            except asyncio.QueueEmpty:
                break

        self._items_processed += processed_count
        return processed_count

    async def _process_item(self, item: Any) -> None:
        """Process a single item."""
        # Simulate processing with delay
        settings: ExampleServiceSettings = self._settings  # type: ignore
        await asyncio.sleep(settings.processing_delay)
        self.logger.info(f"Processed item: {item}")

    @property
    def items_processed(self) -> int:
        """Get the number of items processed."""
        return self._items_processed


# Example usage with dependency injection
@depends.inject
async def use_example_service(
    example_service: ExampleService = depends(),
    cache: t.Any = depends(),  # Will auto-detect cache adapter
) -> int:
    """Example function showing how to use the service."""
    # Import cache adapter type for proper typing
    Cache = import_adapter("cache")
    typed_cache: Cache = cache  # type: ignore

    # Add some items to the service
    await example_service.add_item({"id": 1, "data": "example 1"})
    await example_service.add_item({"id": 2, "data": "example 2"})
    await example_service.add_item({"id": 3, "data": "example 3"})

    # Process the items
    processed_count = await example_service.process_items()
    print(f"Processed {processed_count} items")

    # Update metrics in cache - use hasattr to ensure method exists
    if hasattr(typed_cache, "set"):  # type: ignore
        await typed_cache.set("example_service:last_processed", processed_count)  # type: ignore
    else:
        # Fallback if the cache doesn't have a set method
        print("Cache doesn't have set method, skipping cache update")

    return processed_count


async def main() -> None:
    """Main function to demonstrate the service."""
    # Create and initialize the service
    service = ExampleService()

    # Initialize the service
    await service.initialize()

    # Use the service
    result = await use_example_service()
    print(f"Service processed: {result} items")

    # Check service health
    health = await service.health_check()
    print(f"Service health: {health}")

    # Shutdown the service
    await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
