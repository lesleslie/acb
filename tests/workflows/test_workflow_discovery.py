"""Tests for workflow discovery system."""

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


class TestWorkflowEngineStatus:
    """Test workflow engine status enum."""

    def test_status_values(self):
        """Test all status values are defined."""
        assert WorkflowEngineStatus.ALPHA.value == "alpha"
        assert WorkflowEngineStatus.BETA.value == "beta"
        assert WorkflowEngineStatus.STABLE.value == "stable"
        assert WorkflowEngineStatus.DEPRECATED.value == "deprecated"
        assert WorkflowEngineStatus.EXPERIMENTAL.value == "experimental"


class TestWorkflowCapability:
    """Test workflow capability enum."""

    def test_core_capabilities(self):
        """Test core workflow capabilities."""
        assert WorkflowCapability.STEP_EXECUTION.value == "step_execution"
        assert WorkflowCapability.DEPENDENCY_RESOLUTION.value == "dependency_resolution"
        assert WorkflowCapability.PARALLEL_EXECUTION.value == "parallel_execution"
        assert WorkflowCapability.STATE_MANAGEMENT.value == "state_management"
        assert WorkflowCapability.ERROR_HANDLING.value == "error_handling"

    def test_execution_control(self):
        """Test execution control capabilities."""
        assert WorkflowCapability.PAUSE_RESUME.value == "pause_resume"
        assert WorkflowCapability.CANCELLATION.value == "cancellation"
        assert WorkflowCapability.RETRY_LOGIC.value == "retry_logic"

    def test_integration_capabilities(self):
        """Test integration capabilities."""
        assert WorkflowCapability.EVENT_INTEGRATION.value == "event_integration"
        assert (
            WorkflowCapability.TASK_QUEUE_INTEGRATION.value == "task_queue_integration"
        )


class TestWorkflowMetadata:
    """Test workflow metadata model."""

    def test_metadata_creation(self):
        """Test creating workflow metadata."""
        metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="test-engine",
            provider="test",
            version="1.0.0",
            description="Test engine",
        )

        assert metadata.name == "test-engine"
        assert metadata.provider == "test"
        assert metadata.version == "1.0.0"
        assert metadata.status == WorkflowEngineStatus.STABLE
        assert metadata.acb_min_version == "0.19.0"

    def test_metadata_with_capabilities(self):
        """Test metadata with capabilities."""
        metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="capable-engine",
            provider="test",
            version="1.0.0",
            capabilities=[
                WorkflowCapability.STEP_EXECUTION,
                WorkflowCapability.PARALLEL_EXECUTION,
            ],
            description="Engine with capabilities",
        )

        assert len(metadata.capabilities) == 2
        assert WorkflowCapability.STEP_EXECUTION in metadata.capabilities
        assert WorkflowCapability.PARALLEL_EXECUTION in metadata.capabilities

    def test_metadata_performance_settings(self):
        """Test metadata performance settings."""
        metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="perf-engine",
            provider="test",
            version="1.0.0",
            max_concurrent_workflows=20,
            max_concurrent_steps=10,
            default_timeout=7200.0,
            description="Performance-tuned engine",
        )

        assert metadata.max_concurrent_workflows == 20
        assert metadata.max_concurrent_steps == 10
        assert metadata.default_timeout == 7200.0


class TestWorkflowEngineRegistry:
    """Test workflow engine registration and discovery."""

    def test_generate_engine_id(self):
        """Test engine ID generation."""
        engine_id = generate_engine_id()
        assert engine_id is not None
        assert isinstance(engine_id, type(engine_id))  # UUID type

    def test_register_engine(self):
        """Test registering a workflow engine."""
        metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="test-register",
            provider="test",
            version="1.0.0",
            description="Test registration",
        )

        register_workflow_engine(metadata)

        # Verify registration
        retrieved = get_workflow_engine_descriptor("test-register")
        assert retrieved is not None
        assert retrieved.name == "test-register"
        assert retrieved.provider == "test"

    def test_list_workflow_engines(self):
        """Test listing all workflow engines."""
        # Register test engine
        metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="list-test",
            provider="test",
            version="1.0.0",
            description="Test listing",
        )
        register_workflow_engine(metadata)

        engines = list_workflow_engines()
        assert len(engines) > 0
        assert any(e.name == "list-test" for e in engines)

    def test_list_enabled_engines(self):
        """Test listing only enabled engines."""
        # Register deprecated engine
        deprecated_metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="deprecated-engine",
            provider="test",
            version="1.0.0",
            status=WorkflowEngineStatus.DEPRECATED,
            description="Deprecated engine",
        )
        register_workflow_engine(deprecated_metadata)

        # Register stable engine
        stable_metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="stable-engine",
            provider="test",
            version="1.0.0",
            status=WorkflowEngineStatus.STABLE,
            description="Stable engine",
        )
        register_workflow_engine(stable_metadata)

        enabled = list_enabled_workflow_engines()

        # Verify deprecated not in list
        assert not any(e.name == "deprecated-engine" for e in enabled)
        assert any(e.name == "stable-engine" for e in enabled)

    def test_list_available_by_capability(self):
        """Test filtering engines by capability."""
        # Register engine with specific capability
        metadata = WorkflowMetadata(
            engine_id=generate_engine_id(),
            name="parallel-engine",
            provider="test",
            version="1.0.0",
            capabilities=[WorkflowCapability.PARALLEL_EXECUTION],
            description="Engine with parallel execution",
        )
        register_workflow_engine(metadata)

        # Filter by capability
        available = list_available_workflow_engines(
            capability=WorkflowCapability.PARALLEL_EXECUTION
        )

        assert any(e.name == "parallel-engine" for e in available)


class TestWorkflowEngineImport:
    """Test workflow engine import functionality."""

    def test_import_basic_engine(self):
        """Test importing basic workflow engine."""
        WorkflowEngine = import_workflow_engine("basic")

        assert WorkflowEngine is not None
        assert hasattr(WorkflowEngine, "execute")
        assert hasattr(WorkflowEngine, "execute_step")

    def test_import_default_engine(self):
        """Test importing with no engine type (defaults to basic)."""
        WorkflowEngine = import_workflow_engine()

        assert WorkflowEngine is not None

    def test_import_unknown_engine_fallback(self):
        """Test importing unknown engine falls back to basic."""
        WorkflowEngine = import_workflow_engine("nonexistent")

        # Should fallback to basic engine
        assert WorkflowEngine is not None

    def test_imported_engine_instantiation(self):
        """Test that imported engine can be instantiated."""
        WorkflowEngine = import_workflow_engine("basic")
        engine = WorkflowEngine(max_concurrent_steps=5)

        assert engine is not None
        assert hasattr(engine, "execute")


class TestBuiltinEngineRegistration:
    """Test built-in engine auto-registration."""

    def test_basic_engine_registered(self):
        """Test that basic engine is auto-registered."""
        basic = get_workflow_engine_descriptor("basic")

        assert basic is not None
        assert basic.name == "basic"
        assert basic.provider == "acb"
        assert basic.status == WorkflowEngineStatus.STABLE

    def test_basic_engine_capabilities(self):
        """Test basic engine has correct capabilities."""
        basic = get_workflow_engine_descriptor("basic")

        assert basic is not None
        assert WorkflowCapability.STEP_EXECUTION in basic.capabilities
        assert WorkflowCapability.DEPENDENCY_RESOLUTION in basic.capabilities
        assert WorkflowCapability.PARALLEL_EXECUTION in basic.capabilities
        assert WorkflowCapability.RETRY_LOGIC in basic.capabilities
