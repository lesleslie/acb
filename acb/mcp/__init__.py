"""MCP (Model Context Protocol) Server for ACB.

This module provides a FastMCP-based server implementation that exposes ACB's
capabilities to AI applications through the standardized Model Context Protocol.

The server exposes:
- Tools: ACB actions, adapter operations, and workflows
- Resources: Component registry, system metrics, and configuration
"""

from .orchestrator import WorkflowOrchestrator
from .registry import ComponentRegistry
from .resources import ACBMCPResources
from .server import (
    ACBMCPServer,
    ACMCPServer,  # Backwards compatibility
    create_mcp_server,
    mcp,  # Direct access to FastMCP instance
)
from .tool_registry import register_resources, register_tools
from .tools import ACBMCPTools

__all__ = [
    "ACBMCPResources",
    "ACBMCPServer",
    "ACBMCPTools",
    "ACMCPServer",
    "ComponentRegistry",
    "WorkflowOrchestrator",
    "create_mcp_server",
    "mcp",
    "register_resources",
    "register_tools",
]
