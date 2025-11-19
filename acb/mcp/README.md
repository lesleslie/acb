# ACB MCP Server

The ACB MCP Server provides a Model Context Protocol interface for ACB applications, allowing AI assistants and other tools to interact with ACB's components through a standardized protocol.

## Overview

The MCP Server exposes ACB's actions, adapters, services, and other components as tools and resources that can be accessed by MCP-compatible clients. This enables AI assistants to:

- Discover available components in the system
- Execute actions with parameters
- Interact with adapters and services
- Monitor system health and metrics
- Orchestrate complex workflows

## Architecture

The MCP Server is organized into several modules:

- `server.py`: Main server implementation
- `registry.py`: Component registry for tracking available components
- `tools.py`: Implementation of MCP tools
- `resources.py`: Implementation of MCP resources
- `orchestrator.py`: Workflow orchestration system
- `utils.py`: Utility functions

## Installation

The MCP server is included with ACB and requires no extra install beyond the
standard project dependencies. If you're setting up the repo locally, install
the toolchain and deps with:

```bash
uv sync --group dev
```

## Usage

### Starting the Server

```python
from acb.mcp import create_mcp_server

# Create and start the MCP server (STDIO transport for Claude Desktop)
server = create_mcp_server()
server.run(transport="stdio")

# Or start an HTTP endpoint
# server.run(transport="http", host="127.0.0.1", port=8080)
```

### Using MCP Tools

The MCP server provides several tools for interacting with ACB components:

1. **Component Discovery**: List available actions, adapters, and services
1. **Action Execution**: Execute actions with parameters
1. **Adapter Management**: Interact with configured adapters
1. **Health Monitoring**: Check system component health
1. **Workflow Orchestration**: Execute complex multi-step workflows

### Example: Component Discovery

```python
from acb.mcp import create_mcp_server

server = create_mcp_server()
tools = server.tools

# List all available actions
actions = await tools.list_components("actions")
print(actions)

# List all available adapters
adapters = await tools.list_components("adapters")
print(adapters)
```

### Example: Action Execution

```python
from acb.mcp import create_mcp_server

server = create_mcp_server()
tools = server.tools

# Execute a compression action
result = await tools.execute_action(
    action_category="compress", action_name="brotli", data="Hello, World!", level=4
)
print(result)
```

### Example: Workflow Orchestration

```python
from acb.mcp import create_mcp_server

server = create_mcp_server()
orchestrator = server.orchestrator

# Define a workflow
workflow_steps = [
    {
        "name": "compress_data",
        "type": "action",
        "component": "compress",
        "action": "brotli",
        "parameters": {"data": "Hello, World!", "level": 4},
    },
    {
        "name": "encode_result",
        "type": "action",
        "component": "encode",
        "action": "base64",
        "parameters": {"data": "compressed_data_here"},
    },
]

# Execute the workflow
result = await orchestrator.execute_workflow("example_workflow", workflow_steps)
print(result)
```

## Integration with AI Assistants

The MCP server can be integrated with AI assistants like Claude Desktop by configuring the assistant to connect to the MCP server endpoint.

Example configuration for Claude Desktop:

```json
{
  "mcpServers": {
    "acb": {
      "command": "python",
      "args": ["-m", "acb.mcp.server"],
      "env": {
        "ACB_MCP_HOST": "127.0.0.1",
        "ACB_MCP_PORT": "8000"
      }
    }
  }
}
```

## Extending the MCP Server

To add custom tools or resources to the MCP server:

1. Create a new tool class that implements the required functionality
1. Register the tool with the MCP server
1. Implement any necessary resource endpoints

Example of adding a custom tool:

```python
from acb.mcp import create_mcp_server


class CustomTool:
    async def custom_action(self, parameter: str) -> str:
        return f"Processed: {parameter}"


# Create server and add custom tool
server = create_mcp_server()
server.custom_tool = CustomTool()
```

## Security Considerations

When running the MCP server in production:

1. Use authentication and authorization mechanisms
1. Limit network access to trusted sources
1. Encrypt data in transit using HTTPS
1. Regularly update dependencies
1. Monitor server logs for suspicious activity

## API Reference

### Tools

#### `list_components(component_type: Optional[str] = None)`

List available components of a specific type or all components.

#### `execute_action(action_category: str, action_name: str, **kwargs)`

Execute a specific action with the given parameters.

#### `get_adapter_info(adapter_name: str)`

Get information about a specific adapter.

### Resources

#### `get_component_registry()`

Get the component registry as a resource.

#### `get_system_metrics()`

Get system metrics as a resource.

#### `get_event_stream()`

Get a stream of system events.

### Orchestrator

#### `execute_workflow(workflow_name: str, steps: List[Dict[str, Any]])`

Execute a complex workflow consisting of multiple steps.

#### `start_background_workflow(workflow_id: str, steps: List[Dict[str, Any]])`

Start a workflow in the background.

#### `get_workflow_status(workflow_id: str)`

Get the status of a background workflow.
