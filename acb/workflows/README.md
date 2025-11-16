> **ACB Documentation**: [Main](../../README.md) | [Core Systems](../README.md) | [Workflows](./README.md) | [Services](../services/README.md) | [Testing](../testing/README.md)

# ACB: Workflows

ACB workflows orchestrate multi-step operations with dependency-aware scheduling,
automatic retries, and full integration with the services layer.

## Table of Contents

- [Overview](#overview)
- [Core Concepts](#core-concepts)
- [Usage Patterns](#usage-patterns)
- [Integration Points](#integration-points)
- [Extensibility](#extensibility)
- [Related Resources](#related-resources)

## Overview

The workflows package bundles models, engines, and services that coordinate
business processes. Definitions describe discrete steps, engines execute them,
and the workflow service manages lifecycle, health, and metrics just like other
ACB services.

## Core Concepts

- `WorkflowDefinition` / `WorkflowStep`: Declarative workflow and step schemas with
  dependency graphs, retry policies, and timeouts
- `WorkflowEngine`: Abstract base for execution engines; `BasicWorkflowEngine`
  ships with parallelism, retry, and state tracking
- `WorkflowService`: ServiceBase implementation that runs workflows through the
  DI container with health checks and background management
- `WorkflowSettings` / `WorkflowConfig`: Control concurrency, persistence, and
  engine selection
- `WorkflowResult` / `StepResult`: Captured execution state, errors, and metadata

## Timeout Configuration

Workflows and individual steps can be configured with specific timeout values to prevent long-running operations from hanging indefinitely:

```python
from acb.workflows import WorkflowDefinition, WorkflowStep

workflow = WorkflowDefinition(
    workflow_id="publish-report",
    name="Publish Report",
    timeout=3600.0,  # 1 hour total workflow timeout
    steps=[
        WorkflowStep(
            step_id="security_scan",
            name="Security Scan",
            action="actions.run_security_scan",
            params={"target": "src/"},
            timeout=300.0,  # 5 minutes timeout for this step
            retry_attempts=2,
            retry_delay=5.0,
        ),
        WorkflowStep(
            step_id="render_pdf",
            name="Render PDF",
            action="actions.render_pdf",
            depends_on=["security_scan"],
            timeout=120.0,  # 2 minutes timeout for this step
        ),
    ],
)
```

For quality assurance tools that run in workflow steps, it's important to configure appropriate timeouts:

```yaml
# settings/app.yaml - Configure default workflow timeouts
workflow:
  default_timeout: 3600.0  # 1 hour
  default_step_timeout: 600.0  # 10 minutes per step
```

## Usage Patterns

Define a workflow and execute it with the built-in engine:

```python
from acb.workflows import BasicWorkflowEngine, WorkflowDefinition, WorkflowStep

engine = BasicWorkflowEngine(max_concurrent_steps=3)

workflow = WorkflowDefinition(
    workflow_id="publish-report",
    name="Publish Report",
    steps=[
        WorkflowStep(
            step_id="ingest",
            name="Ingest Data",
            action="actions.fetch_source",
            params={"source": "warehouse"},
        ),
        WorkflowStep(
            step_id="render",
            name="Render PDF",
            action="actions.render_pdf",
            depends_on=["ingest"],
        ),
    ],
)

result = await engine.execute(workflow, context={"tenant_id": "acme"})
assert result.state.name == "COMPLETED"
```

Wrap the engine in a managed service when you need lifecycle management:

```python
import asyncio
from acb.workflows import WorkflowService, WorkflowSettings

async with WorkflowService(engine, WorkflowSettings(max_concurrent_workflows=5)) as svc:
    workflow_id = await svc.submit_workflow(workflow)

    while (workflow_result := await svc.get_workflow_result(workflow_id)) is None:
        await asyncio.sleep(0.01)

# workflow_result now holds the final state, step details, and output
```

## Integration Points

- Dependency injection: engines, services, and loggers resolve through `depends`
- Services layer: `WorkflowService` extends `ServiceBase` with health checks,
  metrics, and cleanup hooks
- Events and task queue: configuration toggles enable event emission and
  deferred execution
- Testing: `acb.testing` fixtures provide registry isolation and provider overrides

## Extensibility

- Implement custom engines by subclassing `WorkflowEngine` and registering them
  with `register_workflow_engine()`
- Use `import_workflow_engine()` to load engines dynamically from configuration
- Attach domain-specific metadata by extending `WorkflowMetadata`
- Persist state or integrate with external schedulers by overriding state methods
  on your engine implementation

## Related Resources

- [Services Layer](../services/README.md)
- [Testing Layer](../testing/README.md)
- [Actions Documentation](../actions/README.md)
- [Main Documentation](../../README.md)
