"""Workflow orchestrator for ACB MCP server."""

import asyncio
from typing import Any

from acb.depends import depends
from acb.logger import Logger

from .registry import ComponentRegistry


class WorkflowOrchestrator:
    """Orchestrator for complex workflows across ACB components."""

    def __init__(self, component_registry: ComponentRegistry):
        """Initialize the workflow orchestrator."""
        self.component_registry = component_registry
        self.logger: Logger = depends.get(Logger)
        self._active_workflows: dict[str, asyncio.Task] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the workflow orchestrator."""
        if self._initialized:
            return

        self.logger.info("Initializing ACB Workflow Orchestrator")
        # Orchestrator initialization logic would go here
        self._initialized = True
        self.logger.info("ACB Workflow Orchestrator initialized")

    async def execute_workflow(
        self, workflow_name: str, steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Execute a complex workflow consisting of multiple steps."""
        try:
            self.logger.info(f"Starting workflow: {workflow_name}")
            results = {}

            for i, step in enumerate(steps):
                step_name = step.get("name", f"step_{i}")
                component_type = step.get("type")
                component_name = step.get("component")
                action = step.get("action")
                parameters = step.get("parameters", {})

                self.logger.info(f"Executing step {i + 1}/{len(steps)}: {step_name}")

                # Execute the step based on component type
                if component_type == "action":
                    result = await self._execute_action_step(
                        component_name, action, parameters
                    )
                elif component_type == "adapter":
                    result = await self._execute_adapter_step(
                        component_name, action, parameters
                    )
                else:
                    raise ValueError(f"Unsupported component type: {component_type}")

                results[step_name] = result

            self.logger.info(f"Workflow {workflow_name} completed successfully")
            return {
                "workflow": workflow_name,
                "status": "completed",
                "results": results,
            }
        except Exception as e:
            self.logger.error(f"Workflow {workflow_name} failed: {e}")
            return {"workflow": workflow_name, "status": "failed", "error": str(e)}

    async def _execute_action_step(
        self, action_category: str, action_name: str, parameters: dict[str, Any]
    ) -> Any:
        """Execute an action step in a workflow."""
        actions = self.component_registry.get_actions()
        category = actions.get(action_category)

        if not category:
            raise ValueError(f"Action category '{action_category}' not found")

        action = getattr(category, action_name, None)
        if not action:
            raise ValueError(
                f"Action '{action_name}' not found in category '{action_category}'"
            )

        # Execute the action
        if asyncio.iscoroutinefunction(action):
            result = await action(**parameters)
        else:
            result = action(**parameters)

        return result

    async def _execute_adapter_step(
        self, adapter_name: str, method_name: str, parameters: dict[str, Any]
    ) -> Any:
        """Execute an adapter step in a workflow."""
        adapter = self.component_registry.get_adapter(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter '{adapter_name}' not found")

        method = getattr(adapter, method_name, None)
        if not method:
            raise ValueError(
                f"Method '{method_name}' not found in adapter '{adapter_name}'"
            )

        # Execute the method
        if asyncio.iscoroutinefunction(method):
            result = await method(**parameters)
        else:
            result = method(**parameters)

        return result

    async def start_background_workflow(
        self, workflow_id: str, steps: list[dict[str, Any]]
    ) -> None:
        """Start a workflow in the background."""

        async def _run_workflow():
            return await self.execute_workflow(workflow_id, steps)

        task = asyncio.create_task(_run_workflow())
        self._active_workflows[workflow_id] = task
        self.logger.info(f"Started background workflow: {workflow_id}")

    async def get_workflow_status(self, workflow_id: str) -> str | None:
        """Get the status of a background workflow."""
        task = self._active_workflows.get(workflow_id)
        if not task:
            return None

        if task.done():
            return "completed"
        return "running"

    async def cleanup(self) -> None:
        """Clean up the workflow orchestrator."""
        # Cancel any active workflows
        for workflow_id, task in self._active_workflows.items():
            if not task.done():
                task.cancel()
                self.logger.info(f"Cancelled workflow: {workflow_id}")

        self._active_workflows.clear()
        self._initialized = False
        self.logger.info("ACB Workflow Orchestrator cleaned up")
