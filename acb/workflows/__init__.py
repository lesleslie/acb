"""Workflow Management Package for ACB Framework.

This package provides comprehensive workflow orchestration functionality including:
- Workflow definition and execution
- Step-based workflow composition
- Dependency resolution and parallel execution
- State management and persistence
- Retry logic and error handling
- Integration with Events System and Task Queue
- Dynamic workflow engine discovery and loading

Key Components:
    - WorkflowService: Main workflow service with dependency injection
    - WorkflowEngine: Abstract base class for workflow engine implementations
    - BasicWorkflowEngine: Simple workflow engine with dependency resolution
    - WorkflowDefinition: Workflow and step definition models
    - WorkflowResult: Execution status and outputs
    - Discovery System: Dynamic engine loading and registration

Performance:
    - Parallel step execution where dependencies allow
    - Configurable concurrency limits
    - Efficient dependency resolution
    - Memory-efficient state tracking

Integration:
    - Services Layer: Full ServiceBase integration
    - Events System: Workflow execution events (when enabled)
    - Task Queue: Background workflow execution (when enabled)
    - Dependency Injection: ACB services integration

Usage:
    >>> from acb.workflows import (
    ...     import_workflow_engine,
    ...     WorkflowDefinition,
    ...     WorkflowStep,
    ... )
    >>> from acb.depends import depends
    >>>
    >>> # Import workflow engine
    >>> WorkflowEngine = import_workflow_engine("basic")
    >>> engine = WorkflowEngine(max_concurrent_steps=5)
    >>>
    >>> # Define workflow
    >>> workflow = WorkflowDefinition(
    ...     workflow_id="example-workflow",
    ...     name="Example Workflow",
    ...     steps=[
    ...         WorkflowStep(
    ...             step_id="step1",
    ...             name="First Step",
    ...             action="process_data",
    ...             params={"input": "data"},
    ...         )
    ...     ],
    ... )
    >>>
    >>> # Execute workflow
    >>> result = await engine.execute(workflow)
    >>> print(f"Workflow completed: {result.state}")
"""

from acb.workflows._base import (
    StepResult,
    StepState,
    WorkflowConfig,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowResult,
    WorkflowService,
    WorkflowSettings,
    WorkflowState,
    WorkflowStep,
)
from acb.workflows.discovery import (
    WorkflowCapability,
    WorkflowEngineStatus,
    WorkflowMetadata,
    generate_engine_id,
    get_workflow_engine_descriptor,
    import_workflow_engine,
    list_available_workflow_engines,
    list_enabled_workflow_engines,
    list_workflow_engines,
    register_workflow_engine,
)
from acb.workflows.engine import BasicWorkflowEngine

__all__ = [
    "BasicWorkflowEngine",
    "StepResult",
    "StepState",
    # Discovery system
    "WorkflowCapability",
    # Configuration and settings
    "WorkflowConfig",
    # Workflow definitions
    "WorkflowDefinition",
    # Engine interface and implementations
    "WorkflowEngine",
    "WorkflowEngineStatus",
    "WorkflowMetadata",
    "WorkflowResult",
    # Core service
    "WorkflowService",
    "WorkflowSettings",
    # Workflow states and results
    "WorkflowState",
    "WorkflowStep",
    "generate_engine_id",
    "get_workflow_engine_descriptor",
    "import_workflow_engine",
    "list_available_workflow_engines",
    "list_enabled_workflow_engines",
    "list_workflow_engines",
    "register_workflow_engine",
]
