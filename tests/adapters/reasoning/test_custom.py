"""Tests for Custom reasoning adapter."""

from unittest.mock import MagicMock

import pytest

from acb.adapters.reasoning._base import (
    DecisionTree,
    MemoryType,
    ReasoningContext,
    ReasoningRequest,
    ReasoningStep,
    ReasoningStrategy,
)
from acb.adapters.reasoning.custom import Reasoning, RuleEngine


class MockCustomSettings:
    """Mock settings for Custom reasoning adapter."""

    def __init__(self):
        self.max_reasoning_depth = 10
        self.enable_parallel_reasoning = True
        self.confidence_threshold = 0.6
        self.enable_self_reflection = True
        self.enable_step_validation = True


@pytest.fixture
def mock_settings():
    """Mock adapter settings."""
    return MockCustomSettings()


@pytest.fixture
def mock_config(mock_settings):
    """Mock config with reasoning settings."""
    config = MagicMock()
    config.reasoning = mock_settings
    return config


@pytest.fixture
def reasoning_adapter(mock_config):
    """Create reasoning adapter with mocked dependencies."""
    adapter = Reasoning()
    adapter._settings = mock_config.reasoning
    return adapter


@pytest.fixture
def sample_rule():
    """Create a sample rule for testing."""
    return EnhancedRule(
        id="test_rule",
        name="Test Rule",
        description="A test rule",
        conditions=[
            {"field": "age", "operator": ">=", "value": 18},
            {"field": "status", "operator": "==", "value": "active"},
        ],
        action="approve",
        priority=1,
        confidence=0.9,
        tags=["test", "approval"],
    )


@pytest.fixture
def sample_decision_tree():
    """Create a sample decision tree for testing."""
    return DecisionTree(
        id="test_tree",
        name="Test Decision Tree",
        description="A test decision tree",
        root_node=DecisionNode(
            id="root",
            condition={"field": "age", "operator": ">=", "value": 18},
            true_branch=DecisionNode(
                id="adult",
                condition={"field": "income", "operator": ">", "value": 50000},
                true_branch=DecisionNode(
                    id="high_income", action="premium_approve", confidence=0.9
                ),
                false_branch=DecisionNode(
                    id="low_income", action="standard_approve", confidence=0.7
                ),
            ),
            false_branch=DecisionNode(id="minor", action="reject", confidence=0.95),
        ),
    )


class TestCustomSettings:
    """Test settings validation and initialization."""

    def test_settings_initialization(self, mock_settings):
        """Test settings are properly initialized."""
        assert mock_settings.max_reasoning_depth == 10
        assert mock_settings.enable_parallel_reasoning is True
        assert mock_settings.confidence_threshold == 0.6
        assert mock_settings.enable_self_reflection is True
        assert mock_settings.enable_step_validation is True


class TestRuleEngine:
    """Test rule engine functionality."""

    def test_rule_engine_initialization(self):
        """Test rule engine initialization."""
        engine = RuleEngine()
        assert engine is not None
        assert len(engine.rules) == 0

    def test_add_rule(self, sample_rule):
        """Test adding rules to engine."""
        engine = RuleEngine()
        engine.add_rule(sample_rule)

        assert len(engine.rules) == 1
        assert engine.rules[0] == sample_rule

    def test_evaluate_rule_success(self, sample_rule):
        """Test successful rule evaluation."""
        engine = RuleEngine()
        data = {"age": 25, "status": "active"}

        result = engine.evaluate_rule(sample_rule, data)

        assert result.rule_id == "test_rule"
        assert result.matched is True
        assert result.action == "approve"
        assert result.confidence == 0.9

    def test_evaluate_rule_failure(self, sample_rule):
        """Test failed rule evaluation."""
        engine = RuleEngine()
        data = {"age": 16, "status": "active"}

        result = engine.evaluate_rule(sample_rule, data)

        assert result.rule_id == "test_rule"
        assert result.matched is False
        assert result.action is None
        assert result.confidence == 0.0

    def test_evaluate_rule_partial_match(self, sample_rule):
        """Test partial rule evaluation."""
        engine = RuleEngine()
        data = {"age": 25, "status": "inactive"}

        result = engine.evaluate_rule(sample_rule, data)

        assert result.rule_id == "test_rule"
        assert result.matched is False

    def test_evaluate_all_rules(self, sample_rule):
        """Test evaluating all rules."""
        engine = RuleEngine()

        # Add multiple rules
        rule2 = EnhancedRule(
            id="backup_rule",
            name="Backup Rule",
            description="Backup approval rule",
            conditions=[{"field": "score", "operator": ">", "value": 80}],
            action="backup_approve",
            priority=2,
            confidence=0.8,
        )

        engine.add_rule(sample_rule)
        engine.add_rule(rule2)

        data = {"age": 25, "status": "active", "score": 85}

        results = engine.evaluate_all_rules(data)

        assert len(results) == 2
        assert all(result.matched for result in results)
        # Should be sorted by priority
        assert results[0].rule_id == "test_rule"  # priority 1
        assert results[1].rule_id == "backup_rule"  # priority 2

    def test_condition_operators(self):
        """Test various condition operators."""
        engine = RuleEngine()

        # Test different operators
        test_cases = [
            ({"field": "value", "operator": "==", "value": 10}, {"value": 10}, True),
            ({"field": "value", "operator": "!=", "value": 10}, {"value": 5}, True),
            ({"field": "value", "operator": ">", "value": 10}, {"value": 15}, True),
            ({"field": "value", "operator": "<", "value": 10}, {"value": 5}, True),
            ({"field": "value", "operator": ">=", "value": 10}, {"value": 10}, True),
            ({"field": "value", "operator": "<=", "value": 10}, {"value": 10}, True),
            (
                {"field": "name", "operator": "in", "value": ["Alice", "Bob"]},
                {"name": "Alice"},
                True,
            ),
            (
                {"field": "tags", "operator": "contains", "value": "test"},
                {"tags": ["test", "other"]},
                True,
            ),
        ]

        for condition, data, expected in test_cases:
            rule = EnhancedRule(
                id="test",
                name="Test",
                description="Test",
                conditions=[condition],
                action="test",
                priority=1,
                confidence=0.9,
            )

            result = engine.evaluate_rule(rule, data)
            assert result.matched == expected, (
                f"Failed for condition {condition} with data {data}"
            )


class TestDecisionTree:
    """Test decision tree functionality."""

    async def test_decision_tree_evaluation(
        self, reasoning_adapter, sample_decision_tree
    ):
        """Test decision tree evaluation."""
        reasoning_adapter._decision_trees["test_tree"] = sample_decision_tree

        # Test high income adult
        data = {"age": 25, "income": 75000}
        result = await reasoning_adapter._evaluate_decision_tree("test_tree", data)

        assert result.action == "premium_approve"
        assert result.confidence == 0.9
        assert "high_income" in result.path

    async def test_decision_tree_low_income_path(
        self, reasoning_adapter, sample_decision_tree
    ):
        """Test decision tree low income path."""
        reasoning_adapter._decision_trees["test_tree"] = sample_decision_tree

        data = {"age": 30, "income": 30000}
        result = await reasoning_adapter._evaluate_decision_tree("test_tree", data)

        assert result.action == "standard_approve"
        assert result.confidence == 0.7
        assert "low_income" in result.path

    async def test_decision_tree_minor_path(
        self, reasoning_adapter, sample_decision_tree
    ):
        """Test decision tree minor path."""
        reasoning_adapter._decision_trees["test_tree"] = sample_decision_tree

        data = {"age": 16, "income": 0}
        result = await reasoning_adapter._evaluate_decision_tree("test_tree", data)

        assert result.action == "reject"
        assert result.confidence == 0.95
        assert "minor" in result.path

    async def test_decision_tree_missing_data(
        self, reasoning_adapter, sample_decision_tree
    ):
        """Test decision tree with missing data."""
        reasoning_adapter._decision_trees["test_tree"] = sample_decision_tree

        data = {"income": 50000}  # Missing age

        with pytest.raises(ValueError, match="Missing field 'age' in data"):
            await reasoning_adapter._evaluate_decision_tree("test_tree", data)

    async def test_decision_tree_not_found(self, reasoning_adapter):
        """Test decision tree not found."""
        with pytest.raises(ValueError, match="Decision tree 'nonexistent' not found"):
            await reasoning_adapter._evaluate_decision_tree("nonexistent", {})


class TestReasoningOperations:
    """Test core reasoning operations."""

    async def test_rule_based_reasoning(self, reasoning_adapter, sample_rule):
        """Test rule-based reasoning strategy."""
        reasoning_adapter._rule_engine.add_rule(sample_rule)

        request = ReasoningRequest(
            query="Should we approve this user?",
            strategy=ReasoningStrategy.RULE_BASED,
            context=ReasoningContext(data={"age": 25, "status": "active"}),
        )

        response = await reasoning_adapter.reason(request)

        assert response.result == "approve"
        assert response.confidence >= 0.9
        assert response.strategy == ReasoningStrategy.RULE_BASED

    async def test_decision_tree_reasoning(
        self, reasoning_adapter, sample_decision_tree
    ):
        """Test decision tree reasoning strategy."""
        reasoning_adapter._decision_trees["test_tree"] = sample_decision_tree

        request = ReasoningRequest(
            query="What should we do with this application?",
            strategy=ReasoningStrategy.DECISION_TREE,
            context=ReasoningContext(
                decision_tree_id="test_tree", data={"age": 25, "income": 75000}
            ),
        )

        response = await reasoning_adapter.reason(request)

        assert response.result == "premium_approve"
        assert response.confidence == 0.9
        assert response.strategy == ReasoningStrategy.DECISION_TREE

    async def test_step_by_step_reasoning(self, reasoning_adapter):
        """Test step-by-step reasoning."""
        steps = [
            ReasoningStep(
                step_number=1,
                description="Analyze the problem",
                reasoning="First, we need to understand what we're solving",
                result="Problem identified",
                confidence=0.8,
            ),
            ReasoningStep(
                step_number=2,
                description="Generate solution",
                reasoning="Based on the analysis, we can propose a solution",
                result="Solution proposed",
                confidence=0.9,
            ),
        ]

        response = await reasoning_adapter._perform_step_by_step_reasoning(
            "Solve this problem", steps
        )

        assert len(response.steps) == 2
        assert response.result == "Solution proposed"
        assert response.confidence > 0.8

    async def test_parallel_reasoning_paths(self, reasoning_adapter, sample_rule):
        """Test parallel reasoning paths."""
        # Add multiple rules
        rule2 = EnhancedRule(
            id="rule2",
            name="Alternative Rule",
            description="Alternative approval rule",
            conditions=[{"field": "score", "operator": ">", "value": 80}],
            action="score_approve",
            priority=2,
            confidence=0.8,
        )

        reasoning_adapter._rule_engine.add_rule(sample_rule)
        reasoning_adapter._rule_engine.add_rule(rule2)

        paths = [
            {"age": 25, "status": "active"},
            {"score": 85},
            {"age": 30, "status": "active", "score": 90},
        ]

        results = await reasoning_adapter._evaluate_parallel_paths(paths)

        assert len(results) == 3
        assert results[0]["matched_rules"] >= 1
        assert results[2]["matched_rules"] >= 2  # Should match both rules


class TestMemoryOperations:
    """Test memory management operations."""

    async def test_store_memory_episodic(self, reasoning_adapter):
        """Test storing episodic memory."""
        await reasoning_adapter.store_memory(
            "session_1", "User approved loan application", MemoryType.EPISODIC
        )

        memories = reasoning_adapter._memory.get("session_1", {})
        assert MemoryType.EPISODIC in memories
        assert "User approved loan application" in memories[MemoryType.EPISODIC]

    async def test_store_memory_semantic(self, reasoning_adapter):
        """Test storing semantic memory."""
        await reasoning_adapter.store_memory(
            "global", "High income threshold is 50000", MemoryType.SEMANTIC
        )

        memories = reasoning_adapter._memory.get("global", {})
        assert MemoryType.SEMANTIC in memories
        assert "High income threshold is 50000" in memories[MemoryType.SEMANTIC]

    async def test_retrieve_memory_by_type(self, reasoning_adapter):
        """Test retrieving memory by type."""
        reasoning_adapter._memory["session_1"] = {
            MemoryType.EPISODIC: ["Episode 1", "Episode 2"],
            MemoryType.SEMANTIC: ["Fact 1"],
        }

        episodic = await reasoning_adapter.retrieve_memory(
            "session_1", MemoryType.EPISODIC
        )
        semantic = await reasoning_adapter.retrieve_memory(
            "session_1", MemoryType.SEMANTIC
        )

        assert len(episodic) == 2
        assert len(semantic) == 1
        assert "Episode 1" in episodic
        assert "Fact 1" in semantic

    async def test_memory_based_reasoning(self, reasoning_adapter):
        """Test reasoning with memory context."""
        # Store relevant memories
        await reasoning_adapter.store_memory(
            "session_1", "User previously rejected for low income", MemoryType.EPISODIC
        )
        await reasoning_adapter.store_memory(
            "session_1", "Minimum income requirement: 40000", MemoryType.SEMANTIC
        )

        memories = await reasoning_adapter.retrieve_memory("session_1")
        context = ReasoningContext(
            session_id="session_1",
            previous_memories=memories,
        )

        # This would be used in actual reasoning
        assert len(context.previous_memories) == 2


class TestSelfReflection:
    """Test self-reflection capabilities."""

    async def test_reflection_on_decision(self, reasoning_adapter):
        """Test self-reflection on a decision."""
        decision = "approve"
        confidence = 0.7
        reasoning_steps = [
            ReasoningStep(
                step_number=1,
                description="Check age",
                reasoning="User is 25 years old",
                result="Age requirement met",
                confidence=0.9,
            ),
            ReasoningStep(
                step_number=2,
                description="Check status",
                reasoning="User status is active",
                result="Status requirement met",
                confidence=0.8,
            ),
        ]

        reflection = await reasoning_adapter._reflect_on_decision(
            decision, confidence, reasoning_steps
        )

        assert reflection is not None
        assert "confidence" in reflection
        assert "potential_issues" in reflection
        assert "improvements" in reflection

    async def test_confidence_calculation(self, reasoning_adapter):
        """Test confidence calculation from steps."""
        steps = [
            ReasoningStep(
                step_number=1, description="", reasoning="", result="", confidence=0.9
            ),
            ReasoningStep(
                step_number=2, description="", reasoning="", result="", confidence=0.8
            ),
            ReasoningStep(
                step_number=3, description="", reasoning="", result="", confidence=0.7
            ),
        ]

        confidence = reasoning_adapter._calculate_overall_confidence(steps)

        # Should be weighted average or similar calculation
        assert 0.7 <= confidence <= 0.9

    async def test_identify_weak_steps(self, reasoning_adapter):
        """Test identification of weak reasoning steps."""
        steps = [
            ReasoningStep(
                step_number=1,
                description="Strong step",
                reasoning="",
                result="",
                confidence=0.9,
            ),
            ReasoningStep(
                step_number=2,
                description="Weak step",
                reasoning="",
                result="",
                confidence=0.4,
            ),
            ReasoningStep(
                step_number=3,
                description="Medium step",
                reasoning="",
                result="",
                confidence=0.7,
            ),
        ]

        weak_steps = reasoning_adapter._identify_weak_steps(steps, threshold=0.6)

        assert len(weak_steps) == 1
        assert weak_steps[0].description == "Weak step"


class TestToolIntegration:
    """Test tool integration capabilities."""

    async def test_register_decision_tool(self, reasoning_adapter):
        """Test registering a decision tool."""

        def approval_tool(data: dict) -> dict:
            return {"approved": data.get("score", 0) > 70}

        reasoning_adapter.register_tool("approval_checker", approval_tool)

        assert "approval_checker" in reasoning_adapter._tools
        assert reasoning_adapter._tools["approval_checker"] == approval_tool

    async def test_execute_tool(self, reasoning_adapter):
        """Test executing a registered tool."""

        def simple_tool(data: dict) -> dict:
            return {"result": data.get("value", 0) * 2}

        reasoning_adapter.register_tool("doubler", simple_tool)

        result = await reasoning_adapter._execute_tool("doubler", {"value": 5})

        assert result == {"result": 10}

    async def test_execute_nonexistent_tool(self, reasoning_adapter):
        """Test executing a nonexistent tool."""
        with pytest.raises(ValueError, match="Tool 'nonexistent' not found"):
            await reasoning_adapter._execute_tool("nonexistent", {})


class TestErrorHandling:
    """Test error handling scenarios."""

    async def test_invalid_reasoning_strategy(self, reasoning_adapter):
        """Test invalid reasoning strategy."""
        request = ReasoningRequest(
            query="Test query",
            strategy="invalid_strategy",  # type: ignore
        )

        with pytest.raises(ValueError, match="Unsupported reasoning strategy"):
            await reasoning_adapter.reason(request)

    async def test_rule_based_without_data(self, reasoning_adapter):
        """Test rule-based reasoning without data."""
        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.RULE_BASED,
        )

        with pytest.raises(ValueError, match="Data must be provided"):
            await reasoning_adapter.reason(request)

    async def test_decision_tree_without_id(self, reasoning_adapter):
        """Test decision tree reasoning without tree ID."""
        request = ReasoningRequest(
            query="Test query",
            strategy=ReasoningStrategy.DECISION_TREE,
            context=ReasoningContext(data={"age": 25}),
        )

        with pytest.raises(ValueError, match="Decision tree ID must be specified"):
            await reasoning_adapter.reason(request)

    async def test_malformed_rule_condition(self):
        """Test malformed rule condition."""
        engine = RuleEngine()

        # Missing operator
        rule = EnhancedRule(
            id="bad_rule",
            name="Bad Rule",
            description="Bad rule",
            conditions=[{"field": "age", "value": 18}],  # Missing operator
            action="test",
            priority=1,
            confidence=0.9,
        )

        with pytest.raises(KeyError):
            engine.evaluate_rule(rule, {"age": 25})


class TestIntegration:
    """Test integration scenarios."""

    async def test_complex_rule_chain(self, reasoning_adapter):
        """Test complex rule chain evaluation."""
        # Create multiple related rules
        rules = [
            EnhancedRule(
                id="age_check",
                name="Age Check",
                description="Check minimum age",
                conditions=[{"field": "age", "operator": ">=", "value": 18}],
                action="age_approved",
                priority=1,
                confidence=0.9,
            ),
            EnhancedRule(
                id="income_check",
                name="Income Check",
                description="Check minimum income",
                conditions=[
                    {"field": "age", "operator": ">=", "value": 18},
                    {"field": "income", "operator": ">=", "value": 30000},
                ],
                action="income_approved",
                priority=2,
                confidence=0.8,
            ),
            EnhancedRule(
                id="premium_check",
                name="Premium Check",
                description="Check premium eligibility",
                conditions=[
                    {"field": "age", "operator": ">=", "value": 25},
                    {"field": "income", "operator": ">=", "value": 75000},
                    {"field": "credit_score", "operator": ">=", "value": 750},
                ],
                action="premium_approved",
                priority=3,
                confidence=0.95,
            ),
        ]

        for rule in rules:
            reasoning_adapter._rule_engine.add_rule(rule)

        # Test premium candidate
        request = ReasoningRequest(
            query="Evaluate premium application",
            strategy=ReasoningStrategy.RULE_BASED,
            context=ReasoningContext(
                data={"age": 30, "income": 80000, "credit_score": 780}
            ),
        )

        response = await reasoning_adapter.reason(request)

        # Should get the highest priority match
        assert response.result == "premium_approved"
        assert response.confidence >= 0.9

    async def test_memory_informed_reasoning(self, reasoning_adapter, sample_rule):
        """Test reasoning informed by previous memories."""
        # Store relevant history
        await reasoning_adapter.store_memory(
            "user_123",
            "Previous application was rejected for insufficient income",
            MemoryType.EPISODIC,
        )

        reasoning_adapter._rule_engine.add_rule(sample_rule)

        # Retrieve memories for context
        memories = await reasoning_adapter.retrieve_memory("user_123")

        request = ReasoningRequest(
            query="Should we approve this new application?",
            strategy=ReasoningStrategy.RULE_BASED,
            context=ReasoningContext(
                session_id="user_123",
                data={"age": 25, "status": "active"},
                previous_memories=memories,
            ),
        )

        response = await reasoning_adapter.reason(request)

        # Reasoning should succeed but context includes previous rejection
        assert response.result == "approve"
        assert len(response.context.previous_memories) == 1


class TestCleanup:
    """Test resource cleanup."""

    async def test_cleanup_resources(self, reasoning_adapter, sample_rule):
        """Test cleanup of adapter resources."""
        # Setup resources
        reasoning_adapter._rule_engine.add_rule(sample_rule)
        reasoning_adapter._tools["test_tool"] = lambda x: x
        reasoning_adapter._memory["session1"] = {MemoryType.CONVERSATION: ["test"]}

        # Perform cleanup
        await reasoning_adapter.cleanup()

        # Verify resources are cleared
        assert len(reasoning_adapter._rule_engine.rules) == 0
        assert len(reasoning_adapter._tools) == 0
        assert len(reasoning_adapter._memory) == 0
        assert len(reasoning_adapter._decision_trees) == 0
