#!/usr/bin/env python3
"""Example script demonstrating the ACB MCP server."""

import sys
from pathlib import Path

# Add the project root to the path so we can import acb
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """Main function to demonstrate the MCP server."""
    try:
        print("ACB MCP Server Example")
        print("=" * 30)
        print("Successfully imported MCP server components")

        print("\nExample usage:")
        print("To run the server, use:")
        print("  uvicorn examples.mcp_demo:app --host 0.0.0.0 --port 8000")

    except ImportError as e:
        print(f"Failed to import MCP server: {e}")
        return 1
    except Exception as e:
        print(f"Error running MCP server example: {e}")
        return 1

    return 0


# Create the app for uvicorn at module level
try:
    from acb.mcp import create_mcp_server

    app = create_mcp_server()
except Exception:
    app = None

if __name__ == "__main__":
    sys.exit(main())
