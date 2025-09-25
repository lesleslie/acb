#!/bin/bash
# Script to run MCP examples

echo "ACB MCP Examples"
echo "==============="

echo "1. Running MCP module import test..."
python tests/test_mcp_imports.py

echo ""
echo "2. Running MCP demo script..."
python examples/mcp_demo.py

echo ""
echo "3. Running MCP client example..."
python examples/mcp_client.py

echo ""
echo "To run the full MCP server:"
echo "  uvicorn examples.mcp_demo:app --host 0.0.0.0 --port 8000"
