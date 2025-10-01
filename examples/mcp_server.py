"""Example MCP server that can be used with Claude Desktop.

This server exposes ACB's capabilities through the Model Context Protocol.
To use with Claude Desktop, add this to your claude_desktop_config.json:

{
  "mcpServers": {
    "acb": {
      "command": "uv",
      "args": ["run", "python", "/path/to/acb/examples/mcp_server.py"]
    }
  }
}
"""

from acb.mcp import create_mcp_server


def main() -> None:
    """Run the ACB MCP server with stdio transport."""
    server = create_mcp_server()
    # Run with stdio transport for Claude Desktop integration
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
