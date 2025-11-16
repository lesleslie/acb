"""Test to verify that all MCP modules can be imported correctly."""


def test_mcp_module_imports():
    """Test that all MCP modules can be imported."""
    modules_to_test = [
        "acb.mcp",
        "acb.mcp.server",
        "acb.mcp.tools",
        "acb.mcp.resources",
        "acb.mcp.orchestrator",
        "acb.mcp.registry",
        "acb.mcp.utils",
    ]

    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✓ {module_name} imported successfully")
        except ImportError as e:
            print(f"✗ Failed to import {module_name}: {e}")
            raise


def test_mcp_server_creation():
    """Test that the MCP server can be created."""
    try:
        from acb.mcp import create_mcp_server

        app = create_mcp_server()
        assert app is not None
        print("✓ MCP server created successfully")
    except Exception as e:
        print(f"✗ Failed to create MCP server: {e}")
        raise


if __name__ == "__main__":
    test_mcp_module_imports()
    test_mcp_server_creation()
    print("All MCP tests passed!")
