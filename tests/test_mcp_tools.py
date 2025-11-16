"""Test to verify that MCP tools can be imported correctly."""

import sys
from pathlib import Path

# Add the project root to the path so we can import acb
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_mcp_tools_imports():
    """Test that MCP tools can be imported."""
    try:
        from acb.mcp.tools import (
            ActionExecutionTool,
            AdapterManagementTool,
            ComponentDiscoveryTool,
            HealthCheckTool,
        )

        # Just test that we can import the classes
        assert ComponentDiscoveryTool is not None
        assert ActionExecutionTool is not None
        assert AdapterManagementTool is not None
        assert HealthCheckTool is not None

        print("✓ All MCP tools imported successfully")

    except Exception as e:
        print(f"✗ Error importing MCP tools: {e}")
        raise


def main():
    """Main test function."""
    try:
        test_mcp_tools_imports()
        print("All MCP tools import tests passed!")
        return 0
    except Exception as e:
        print(f"Error running MCP tools import tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
