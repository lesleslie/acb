"""Test for the ACB MCP module."""

from acb.mcp import (
    ACBMCPResources,
    ACBMCPTools,
    ACMCPServer,
    ComponentRegistry,
    WorkflowOrchestrator,
    create_mcp_server,
)


def test_mcp_module_imports():
    """Test that all MCP module components can be imported."""
    # This test ensures that the MCP module structure is correct
    # and all expected components are available
    assert create_mcp_server is not None
    assert ACMCPServer is not None
    assert ComponentRegistry is not None
    assert ACBMCPTools is not None
    assert ACBMCPResources is not None
    assert WorkflowOrchestrator is not None


def test_mcp_server_creation():
    """Test that an MCP server can be created."""
    server = create_mcp_server()
    assert isinstance(server, ACMCPServer)
    assert server.component_registry is not None
    assert server.tools is not None
    assert server.resources is not None
    assert server.orchestrator is not None
