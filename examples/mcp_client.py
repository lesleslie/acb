#!/usr/bin/env python3
"""Example script demonstrating how to interact with the ACB MCP server using HTTP requests."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path so we can import acb
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def main():
    """Main function to demonstrate interacting with the MCP server."""
    try:
        # Example of how to interact with the MCP server
        print("ACB MCP Client Example")
        print("=" * 30)

        # Note: This would normally connect to a running server
        # For this example, we'll just show the request structure

        # Example request to list tools
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        print("Example request to list tools:")
        print("POST /mcp/tools")
        print(f"Body: {list_tools_request}")

        # Example request to call a tool
        call_tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "list_components",
                "arguments": {"component_type": "adapter"},
            },
        }

        print("\nExample request to call a tool:")
        print("POST /mcp/tools/call")
        print(f"Body: {call_tool_request}")

        # Example request to list resources
        list_resources_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {},
        }

        print("\nExample request to list resources:")
        print("GET /mcp/resources")
        print(f"Body: {list_resources_request}")

        print("\nTo run a complete example:")
        print(
            "1. Start the MCP server: uvicorn examples.mcp_demo:app --host 0.0.0.0 --port 8000"
        )
        print("2. Run this client script to interact with the server")

    except ImportError as e:
        print(f"Failed to import required modules: {e}")
        return 1
    except Exception as e:
        print(f"Error running MCP client example: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
