"""Main MCP server implementation for ACB."""

from typing import Any

from fastapi import FastAPI
from acb.config import Config
from acb.depends import depends
from acb.logger import Logger

from .orchestrator import WorkflowOrchestrator
from .registry import ComponentRegistry
from .resources import ACBMCPResources
from .tools import ACBMCPTools


class ACMCPServer:
    """ACB MCP Server implementation."""

    def __init__(self, app: FastAPI | None = None):
        """Initialize the MCP server."""
        self.app = app or FastAPI(title="ACB MCP Server")
        self.config: Config = depends.get(Config)
        self.logger: Logger = depends.get(Logger)
        self.component_registry = ComponentRegistry()
        self.tools = ACBMCPTools(self.component_registry)
        self.resources = ACBMCPResources(self.component_registry)
        self.orchestrator = WorkflowOrchestrator(self.component_registry)
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up the MCP server routes."""

        # Health check endpoint
        @self.app.get("/health")
        async def health_check() -> dict[str, Any]:
            return {"status": "healthy", "server": "ACB MCP Server", "version": "1.0.0"}

        # MCP protocol endpoints would be implemented here
        # This is a simplified implementation for demonstration

    async def start(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Start the MCP server."""
        self.logger.info(f"Starting ACB MCP Server on {host}:{port}")

        # Initialize all components
        await self.component_registry.initialize()
        await self.tools.initialize()
        await self.resources.initialize()
        await self.orchestrator.initialize()

        # Start the server
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)

    async def stop(self) -> None:
        """Stop the MCP server."""
        self.logger.info("Stopping ACB MCP Server")
        await self.orchestrator.cleanup()
        await self.resources.cleanup()
        await self.tools.cleanup()
        await self.component_registry.cleanup()


def create_mcp_server() -> ACMCPServer:
    """Create and return an ACB MCP server instance."""
    return ACMCPServer()
