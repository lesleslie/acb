"""Base reasoning adapter interface for AI/ML decision-making and reasoning operations."""

from abc import ABC, abstractmethod
from enum import Enum

import asyncio
import typing as t
from dataclasses import dataclass
from pydantic import BaseModel, Field, SecretStr

from acb.cleanup import CleanupMixin
from acb.config import Config, Settings
from acb.depends import Inject, depends
from acb.logger import Logger
from acb.ssl_config import SSLConfigMixin


class ReasoningStrategy(str, Enum):
    """Reasoning strategy types."""

    CHAIN_OF_THOUGHT = "chain_of_thought"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    REACT = "react"  # Reasoning and Acting
    SELF_REFLECTION = "self_reflection"
    RULE_BASED = "rule_based"
    RAG_WORKFLOW = "rag_workflow"
    FUNCTION_CALLING = "function_calling"
    MULTI_AGENT = "multi_agent"


class ReasoningProvider(str, Enum):
    """Reasoning provider implementations."""

    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    CUSTOM = "custom"
    OPENAI_FUNCTIONS = "openai_functions"


class ReasoningCapability(str, Enum):
    """Reasoning capabilities."""

    CHAIN_REASONING = "chain_reasoning"
    RAG_WORKFLOWS = "rag_workflows"
    RULE_ENGINE = "rule_engine"
    TOOL_CALLING = "tool_calling"
    MEMORY_MANAGEMENT = "memory_management"
    AGENT_WORKFLOWS = "agent_workflows"
    SELF_REFLECTION = "self_reflection"
    PARALLEL_REASONING = "parallel_reasoning"
    CONTEXT_PRESERVATION = "context_preservation"
    CITATION_TRACKING = "citation_tracking"


class MemoryType(str, Enum):
    """Types of reasoning memory."""

    CONVERSATION = "conversation"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"
    LONG_TERM = "long_term"


@dataclass
class ReasoningStep:
    """Individual step in a reasoning chain."""

    step_id: str
    description: str
    input_data: dict[str, t.Any]
    output_data: dict[str, t.Any] | None = None
    reasoning: str | None = None
    confidence: float | None = None
    tools_used: list[str] | None = None
    duration_ms: int | None = None
    error: str | None = None


@dataclass
class ReasoningContext:
    """Context for reasoning operations."""

    session_id: str
    user_id: str | None = None
    conversation_history: list[dict[str, t.Any]] | None = None
    knowledge_base: str | None = None
    retrieved_contexts: list[dict[str, t.Any]] | None = None
    memory_data: dict[MemoryType, t.Any] | None = None
    metadata: dict[str, t.Any] | None = None


@dataclass
class ToolDefinition:
    """Definition for a reasoning tool/function."""

    name: str
    description: str
    parameters: dict[str, t.Any]
    required_parameters: list[str] | None = None
    return_schema: dict[str, t.Any] | None = None
    examples: list[dict[str, t.Any]] | None = None


@dataclass
class ReasoningRequest:
    """Request for reasoning operation."""

    query: str
    strategy: ReasoningStrategy
    context: ReasoningContext | None = None
    tools: list[ToolDefinition] | None = None
    max_steps: int = 10
    max_tokens: int = 4000
    temperature: float = 0.7
    model: str | None = None
    enable_reflection: bool = False
    enable_memory: bool = True
    retrieval_config: dict[str, t.Any] | None = None
    custom_instructions: str | None = None


@dataclass
class ReasoningResponse:
    """Response from reasoning operation."""

    final_answer: str
    reasoning_chain: list[ReasoningStep]
    strategy_used: ReasoningStrategy
    provider: ReasoningProvider
    total_tokens: int | None = None
    total_duration_ms: int | None = None
    confidence_score: float | None = None
    sources_cited: list[dict[str, t.Any]] | None = None
    memory_updates: dict[MemoryType, t.Any] | None = None
    tool_calls: list[dict[str, t.Any]] | None = None
    reflection_notes: str | None = None
    error: str | None = None


class DecisionRule(BaseModel):
    """Rule for decision-making logic."""

    name: str
    condition: str  # Expression to evaluate
    action: str  # Action to take if condition is true
    priority: int = 0
    description: str = ""
    metadata: dict[str, t.Any] = Field(default_factory=dict)


class DecisionTree(BaseModel):
    """Decision tree structure."""

    name: str
    rules: list[DecisionRule]
    default_action: str | None = None
    description: str = ""


class RAGConfig(BaseModel):
    """Configuration for RAG workflows."""

    vector_db_name: str | None = None
    collection_name: str | None = None
    similarity_threshold: float = 0.7
    max_retrieved_docs: int = 5
    rerank_results: bool = True
    enable_query_expansion: bool = False
    enable_citation_tracking: bool = True
    chunk_overlap_strategy: str = "sentence"


class ChainConfig(BaseModel):
    """Configuration for reasoning chains."""

    max_iterations: int = 10
    early_stopping: bool = True
    confidence_threshold: float = 0.8
    enable_parallel_paths: bool = False
    path_selection_strategy: str = "best_confidence"
    enable_backtracking: bool = False


class ReasoningBaseSettings(Settings, SSLConfigMixin):
    """Base settings for reasoning adapters."""

    # Provider configuration
    provider: ReasoningProvider = ReasoningProvider.LANGCHAIN
    api_key: SecretStr | None = None
    base_url: str | None = None
    model: str = "gpt-4"

    # Reasoning configuration
    default_strategy: ReasoningStrategy = ReasoningStrategy.CHAIN_OF_THOUGHT
    max_reasoning_steps: int = 10
    max_tokens_per_step: int = 1000
    temperature: float = 0.7
    enable_reflection: bool = True
    enable_memory: bool = True

    # Performance settings
    timeout_seconds: float = 120.0
    max_concurrent_operations: int = 10
    enable_caching: bool = True
    cache_ttl: int = 3600

    # RAG configuration
    rag_config: RAGConfig = Field(default_factory=RAGConfig)

    # Chain configuration
    chain_config: ChainConfig = Field(default_factory=ChainConfig)

    # Memory settings
    memory_types: list[MemoryType] = Field(
        default_factory=lambda: [MemoryType.CONVERSATION, MemoryType.WORKING],
    )
    memory_persistence: bool = True
    memory_ttl: int = 86400  # 24 hours

    # Tool calling settings
    enable_tool_calling: bool = True
    max_tool_calls_per_step: int = 5
    tool_timeout_seconds: float = 30.0

    # Integration settings
    ai_adapter_name: str = "ai"
    embedding_adapter_name: str = "embedding"
    vector_adapter_name: str = "vector"

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        # Extract SSL configuration
        ssl_enabled = values.pop("ssl_enabled", False)
        ssl_cert_path = values.pop("ssl_cert_path", None)
        ssl_key_path = values.pop("ssl_key_path", None)
        ssl_ca_path = values.pop("ssl_ca_path", None)
        ssl_verify_mode = values.pop("ssl_verify_mode", "required")
        values.pop("tls_version", "TLSv1.2")

        super().__init__(**values)
        SSLConfigMixin.__init__(self)

        # Configure SSL if enabled
        if ssl_enabled:
            from acb.ssl_config import SSLVerifyMode

            verify_mode_map = {
                "none": SSLVerifyMode.NONE,
                "optional": SSLVerifyMode.OPTIONAL,
                "required": SSLVerifyMode.REQUIRED,
            }
            verify_mode = verify_mode_map.get(ssl_verify_mode, SSLVerifyMode.REQUIRED)

            self.configure_ssl(
                enabled=True,
                cert_path=ssl_cert_path,
                key_path=ssl_key_path,
                ca_path=ssl_ca_path,
                verify_mode=verify_mode,
                check_hostname=verify_mode == SSLVerifyMode.REQUIRED,
            )


class ReasoningBase(CleanupMixin, ABC):
    """Base class for reasoning adapters with unified interface."""

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        self._settings: ReasoningBaseSettings | None = None
        self._client: t.Any = None
        self._memory_store: dict[str, dict[MemoryType, t.Any]] = {}
        self._tool_registry: dict[str, ToolDefinition] = {}
        self._decision_trees: dict[str, DecisionTree] = {}
        # Get logger if available, otherwise None (for testing)
        try:
            logger_instance = depends.get_sync(Logger)
            # Verify it's actually a logger instance, not a string
            if isinstance(logger_instance, str):
                self.logger = None
            else:
                self.logger = logger_instance
        except Exception:
            self.logger = None

    @property
    def settings(self) -> ReasoningBaseSettings:
        """Get adapter settings."""
        if self._settings is None:
            msg = "Settings not initialized"
            raise RuntimeError(msg)
        return self._settings

    @abstractmethod
    async def _create_client(self) -> t.Any:
        """Create and configure the reasoning client."""

    async def _ensure_client(self) -> t.Any:
        """Ensure client is initialized."""
        if self._client is None:
            self._client = await self._create_client()
            self.register_resource(self._client)
        return self._client

    # Public interface methods
    async def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Perform reasoning operation."""
        return await self._reason(request)

    async def chain_of_thought(
        self,
        query: str,
        context: ReasoningContext | None = None,
        max_steps: int | None = None,
        **kwargs: t.Any,
    ) -> ReasoningResponse:
        """Perform chain-of-thought reasoning."""
        request = ReasoningRequest(
            query=query,
            strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
            context=context,
            max_steps=max_steps or self.settings.max_reasoning_steps,
            **kwargs,
        )
        return await self._reason(request)

    async def tree_of_thoughts(
        self,
        query: str,
        context: ReasoningContext | None = None,
        num_paths: int = 3,
        **kwargs: t.Any,
    ) -> ReasoningResponse:
        """Perform tree-of-thoughts reasoning with parallel paths."""
        request = ReasoningRequest(
            query=query,
            strategy=ReasoningStrategy.TREE_OF_THOUGHTS,
            context=context,
            **kwargs,
        )
        return await self._tree_of_thoughts(request, num_paths)

    async def react_reasoning(
        self,
        query: str,
        tools: list[ToolDefinition],
        context: ReasoningContext | None = None,
        **kwargs: t.Any,
    ) -> ReasoningResponse:
        """Perform ReAct (Reasoning and Acting) with tools."""
        request = ReasoningRequest(
            query=query,
            strategy=ReasoningStrategy.REACT,
            context=context,
            tools=tools,
            **kwargs,
        )
        return await self._react_reasoning(request)

    async def rag_workflow(
        self,
        query: str,
        knowledge_base: str,
        context: ReasoningContext | None = None,
        **kwargs: t.Any,
    ) -> ReasoningResponse:
        """Perform retrieval-augmented generation workflow."""
        if context is None:
            current_task = asyncio.current_task()
            task_name = (
                current_task.get_name() if current_task is not None else "default"
            )
            context = ReasoningContext(
                session_id=f"rag_{task_name}",
            )
        context.knowledge_base = knowledge_base

        request = ReasoningRequest(
            query=query,
            strategy=ReasoningStrategy.RAG_WORKFLOW,
            context=context,
            **kwargs,
        )
        return await self._rag_workflow(request)

    async def evaluate_decision_tree(
        self,
        tree_name: str,
        input_data: dict[str, t.Any],
        context: ReasoningContext | None = None,
    ) -> str:
        """Evaluate a decision tree against input data."""
        return await self._evaluate_decision_tree(tree_name, input_data, context)

    async def register_tool(self, tool: ToolDefinition) -> None:
        """Register a tool for reasoning operations."""
        self._tool_registry[tool.name] = tool

    async def register_decision_tree(self, tree: DecisionTree) -> None:
        """Register a decision tree."""
        self._decision_trees[tree.name] = tree

    async def get_memory(
        self,
        session_id: str,
        memory_type: MemoryType,
    ) -> dict[str, t.Any] | None:
        """Get memory for a session."""
        return self._memory_store.get(session_id, {}).get(memory_type)

    async def set_memory(
        self,
        session_id: str,
        memory_type: MemoryType,
        data: dict[str, t.Any],
    ) -> None:
        """Set memory for a session."""
        if session_id not in self._memory_store:
            self._memory_store[session_id] = {}
        self._memory_store[session_id][memory_type] = data

    async def clear_memory(
        self,
        session_id: str,
        memory_type: MemoryType | None = None,
    ) -> None:
        """Clear memory for a session."""
        if session_id in self._memory_store:
            if memory_type:
                self._memory_store[session_id].pop(memory_type, None)
            else:
                self._memory_store.pop(session_id, None)

    async def health_check(self) -> dict[str, t.Any]:
        """Check adapter health and connectivity."""
        return await self._health_check()

    # Abstract methods for implementation by providers
    @abstractmethod
    async def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Implementation-specific reasoning."""

    async def _tree_of_thoughts(
        self,
        request: ReasoningRequest,
        num_paths: int,
    ) -> ReasoningResponse:
        """Default tree-of-thoughts implementation - can be overridden."""
        # Default implementation creates parallel reasoning chains
        tasks = []
        for i in range(num_paths):
            path_request = ReasoningRequest(
                query=f"Path {i + 1}: {request.query}",
                strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
                context=request.context,
                max_steps=request.max_steps,
                temperature=request.temperature + (i * 0.1),  # Vary temperature
                model=request.model,
            )
            tasks.append(self._reason(path_request))

        # Execute paths in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Select best path based on confidence
        valid_results = [
            r for r in results if isinstance(r, ReasoningResponse) and not r.error
        ]
        if not valid_results:
            return ReasoningResponse(
                final_answer="Failed to generate valid reasoning paths",
                reasoning_chain=[],
                strategy_used=ReasoningStrategy.TREE_OF_THOUGHTS,
                provider=self.settings.provider,
                error="All reasoning paths failed",
            )

        best_result = max(valid_results, key=lambda r: r.confidence_score or 0.0)
        best_result.strategy_used = ReasoningStrategy.TREE_OF_THOUGHTS
        return best_result

    async def _react_reasoning(self, request: ReasoningRequest) -> ReasoningResponse:
        """Default ReAct implementation - can be overridden."""
        # Default implementation alternates between reasoning and tool use
        return await self._reason(request)

    async def _rag_workflow(self, request: ReasoningRequest) -> ReasoningResponse:
        """Default RAG workflow implementation - can be overridden."""
        try:
            # Retrieve relevant context
            if request.context and request.context.knowledge_base:
                retrieved_contexts = await self._retrieve_contexts(
                    request.query,
                    request.context.knowledge_base,
                )
                if request.context:
                    request.context.retrieved_contexts = retrieved_contexts

            # Perform reasoning with retrieved context
            return await self._reason(request)
        except Exception as e:
            return ReasoningResponse(
                final_answer="RAG workflow failed",
                reasoning_chain=[],
                strategy_used=ReasoningStrategy.RAG_WORKFLOW,
                provider=self.settings.provider,
                error=str(e),
            )

    async def _retrieve_contexts(
        self,
        query: str,
        knowledge_base: str,
    ) -> list[dict[str, t.Any]]:
        """Retrieve relevant contexts for RAG."""
        try:
            # This would integrate with vector database adapter
            from acb.adapters import import_adapter

            # Get embedding and vector adapters
            Embedding = import_adapter("embedding")
            Vector = import_adapter("vector")

            embedding_adapter = await depends.get(Embedding)
            vector_adapter = await depends.get(Vector)

            # Generate query embedding
            query_embedding = await embedding_adapter.embed_text(query)

            # Search vector database
            results = await vector_adapter.similarity_search(
                collection=knowledge_base,
                query_vector=query_embedding,
                limit=self.settings.rag_config.max_retrieved_docs,
                threshold=self.settings.rag_config.similarity_threshold,
            )

            return [
                {
                    "content": result.get("text", ""),
                    "metadata": result.get("metadata", {}),
                    "score": result.get("score", 0.0),
                }
                for result in results
            ]
        except Exception as e:
            if self.logger is not None:
                self.logger.warning(f"Failed to retrieve contexts: {e}")
            return []

    async def _evaluate_decision_tree(
        self,
        tree_name: str,
        input_data: dict[str, t.Any],
        context: ReasoningContext | None = None,
    ) -> str:
        """Evaluate decision tree against input data."""
        if tree_name not in self._decision_trees:
            msg = f"Decision tree '{tree_name}' not found"
            raise ValueError(msg)

        tree = self._decision_trees[tree_name]

        # Sort rules by priority (highest first)
        sorted_rules = sorted(tree.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            try:
                # Simple expression evaluation (in production, use a safe evaluator)
                if self._evaluate_condition(rule.condition, input_data):
                    return rule.action
            except Exception as e:
                if self.logger is not None:
                    self.logger.warning(f"Error evaluating rule {rule.name}: {e}")
                continue

        return tree.default_action or "no_action"

    def _evaluate_condition(self, condition: str, data: dict[str, t.Any]) -> bool:
        """Safely evaluate a condition expression."""
        # This is a simplified implementation
        # In production, use a proper expression evaluator
        import re

        # Replace variables in condition with actual values
        for key, value in data.items():
            pattern = f"\\b{key}\\b"
            if isinstance(value, str):
                condition = re.sub(
                    pattern,
                    f"'{value}'",
                    condition,
                )  # REGEX OK: variable replacement for condition evaluation
            else:
                condition = re.sub(
                    pattern,
                    str(value),
                    condition,
                )  # REGEX OK: variable replacement for condition evaluation

        try:
            # Use ast.literal_eval for safer evaluation
            import ast

            return bool(ast.literal_eval(condition))  # nosec B307
        except Exception:
            return False

    async def _health_check(self) -> dict[str, t.Any]:
        """Default health check implementation."""
        try:
            client = await self._ensure_client()
            return {
                "status": "healthy",
                "client_initialized": client is not None,
                "provider": self.settings.provider,
                "registered_tools": len(self._tool_registry),
                "decision_trees": len(self._decision_trees),
                "active_sessions": len(self._memory_store),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "provider": self.settings.provider,
            }


# Utility functions for reasoning operations
async def validate_reasoning_request(request: ReasoningRequest) -> None:
    """Validate reasoning request parameters."""
    if not request.query:
        msg = "Query cannot be empty"
        raise ValueError(msg)

    if request.max_steps <= 0:
        msg = "max_steps must be positive"
        raise ValueError(msg)

    if not (0.0 <= request.temperature <= 2.0):
        msg = "temperature must be between 0.0 and 2.0"
        raise ValueError(msg)

    if request.tools:
        for tool in request.tools:
            if not tool.name or not tool.description:
                msg = "Tool must have name and description"
                raise ValueError(msg)


async def calculate_confidence_score(reasoning_chain: list[ReasoningStep]) -> float:
    """Calculate overall confidence score from reasoning chain."""
    if not reasoning_chain:
        return 0.0

    # Simple average of step confidences
    confidences = [
        step.confidence for step in reasoning_chain if step.confidence is not None
    ]
    if not confidences:
        return 0.5  # Default moderate confidence

    return sum(confidences) / len(confidences)


async def merge_reasoning_contexts(
    context1: ReasoningContext,
    context2: ReasoningContext,
) -> ReasoningContext:
    """Merge two reasoning contexts."""
    return ReasoningContext(
        session_id=context1.session_id,
        user_id=context1.user_id or context2.user_id,
        conversation_history=(context1.conversation_history or [])
        + (context2.conversation_history or []),
        knowledge_base=context1.knowledge_base or context2.knowledge_base,
        retrieved_contexts=(context1.retrieved_contexts or [])
        + (context2.retrieved_contexts or []),
        memory_data={**(context1.memory_data or {}), **(context2.memory_data or {})},
        metadata={**(context1.metadata or {}), **(context2.metadata or {})},
    )
