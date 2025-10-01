"""MCP (Model Context Protocol) Server for ACB.

This module provides a FastMCP-based server implementation that exposes ACB's
capabilities to AI applications through the standardized Model Context Protocol.

The server exposes:
- Tools: ACB actions, adapter operations, and workflows
- Resources: Component registry, system metrics, and configuration
"""

from .registry import ComponentRegistry
from .server import (
    ACBMCPServer,
    ACMCPServer,  # Backwards compatibility
    create_mcp_server,
    mcp,  # Direct access to FastMCP instance
)

__all__ = [
    "ACBMCPServer",
    "ACMCPServer",
    "ComponentRegistry",
    "create_mcp_server",
    "mcp",
]
