"""Simple example of using the ACB MCP Server with FastMCP.

This example demonstrates:
1. Creating an MCP server instance
2. Initializing the component registry
3. Running the server with stdio transport (for Claude Desktop integration)
"""

import asyncio

from acb.mcp import create_mcp_server


async def main() -> None:
    """Simple example of using the ACB MCP Server."""
    # Create the server
    server = create_mcp_server()

    # Initialize components
    await server.initialize()

    # Server is now ready to handle MCP requests
    # In production, you would run the server with:
    # server.run(transport="stdio")  # For Claude Desktop
    # server.run(transport="sse", host="127.0.0.1", port=8000)  # For HTTP/SSE

    # Cleanup
    await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
