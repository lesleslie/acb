#!/usr/bin/env python3
"""Example script demonstrating the ACB MCP server."""

import sys
from pathlib import Path

# Add the project root to the path so we can import acb
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main() -> int:
    """Main function to demonstrate the MCP server."""
    try:
        pass

    except ImportError:
        return 1
    except Exception:
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
