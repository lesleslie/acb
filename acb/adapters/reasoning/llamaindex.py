"""LlamaIndex reasoning adapter for RAG-focused reasoning workflows."""

import time

import asyncio
import typing as t
from datetime import datetime

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
from acb.adapters.reasoning._base import (
    ReasoningBase,
    ReasoningBaseSettings,
    ReasoningProvider,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStep,
    ReasoningStrategy,
    calculate_confidence_score,
)
from acb.depends import depends

if t.TYPE_CHECKING:
    from acb.adapters.logger import LoggerProtocol as LoggerType
else:
    from acb.logger import Logger as LoggerType

# Conditional imports for LlamaIndex via dynamic loading to avoid static
# import errors when optional dependency is not installed.
import importlib
import importlib.util as _il_util

LLAMAINDEX_AVAILABLE = _il_util.find_spec("llama_index") is not None

if LLAMAINDEX_AVAILABLE:
    try:
        _li_core = importlib.import_module("llama_index.core")
        _li_agent = importlib.import_module("llama_index.core.agent")
        _li_chat = importlib.import_module("llama_index.core.chat_engine")
        _li_qi = importlib.import_module("llama_index.core.indices.query.base")
        _li_mem = importlib.import_module("llama_index.core.memory")
        _li_qe = importlib.import_module("llama_index.core.query_engine")
        _li_ret = importlib.import_module("llama_index.core.retrievers")
        _li_schema = importlib.import_module("llama_index.core.schema")
        _li_tools = importlib.import_module("llama_index.core.tools")
        _li_openai = importlib.import_module("llama_index.llms.openai")

        Document = _li_core.Document
        PromptTemplate = _li_core.PromptTemplate
        Settings = _li_core.Settings
        VectorStoreIndex = _li_core.VectorStoreIndex
        get_response_synthesizer = _li_core.get_response_synthesizer
        ReActAgent = _li_agent.ReActAgent
        SimpleChatEngine = _li_chat.SimpleChatEngine
        BaseQueryEngine = _li_qi.BaseQueryEngine
        ChatMemoryBuffer = _li_mem.ChatMemoryBuffer
        RetrieverQueryEngine = _li_qe.RetrieverQueryEngine
        VectorIndexRetriever = _li_ret.VectorIndexRetriever
        NodeWithScore = _li_schema.NodeWithScore
        FunctionTool = _li_tools.FunctionTool
        OpenAI = _li_openai.OpenAI
    except Exception:
        # If dynamic import fails at runtime, mark as unavailable and fall back
        LLAMAINDEX_AVAILABLE = False

if not LLAMAINDEX_AVAILABLE:
    # Lightweight fallbacks to satisfy type usages when llama-index is missing
    Document = t.Any
    PromptTemplate = t.Any
    Settings = t.Any
    VectorStoreIndex = t.Any
    get_response_synthesizer = t.Any  # type: ignore[assignment]
    ReActAgent = t.Any
    SimpleChatEngine = t.Any
    BaseQueryEngine = t.Any
    ChatMemoryBuffer = t.Any
    RetrieverQueryEngine = t.Any
    VectorIndexRetriever = t.Any
    NodeWithScore = t.Any
    FunctionTool = t.Any
    OpenAI = t.Any


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="LlamaIndex Reasoning",
    category="reasoning",
    provider="llamaindex",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Team",
    created_date=datetime.now().isoformat(),
    last_modified=datetime.now().isoformat(),
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.STREAMING,
        AdapterCapability.METRICS,
        AdapterCapability.LOGGING,
        AdapterCapability.CACHING,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=[
        "llama-index>=0.9.0",
        "llama-index-llms-openai>=0.1.0",
        "openai>=1.0.0",
    ],
    description="Advanced RAG-focused reasoning using LlamaIndex framework with knowledge base querying and citation tracking",
    settings_class="LlamaIndexReasoningSettings",
    config_example={
        "api_key": "your-openai-api-key",
        "model": "gpt-4",
        "temperature": 0.7,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "similarity_top_k": 5,
        "enable_citation_tracking": True,
    },
)


class LlamaIndexReasoningSettings(ReasoningBaseSettings):
    """Settings for LlamaIndex reasoning adapter."""

    # Document processing settings
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Retrieval settings
    similarity_top_k: int = 5
    similarity_threshold: float = 0.7

    # Response synthesis settings
    response_mode: str = "compact"  # compact, tree_summarize, simple_summarize
    streaming: bool = False

    # Memory settings
    chat_memory_token_limit: int = 3000

    # Agent settings
    max_function_calls: int = 10

    # Index settings
    enable_citation_tracking: bool = True
    persist_index: bool = True
    index_cache_dir: str = "./index_cache"


class LlamaIndexCallback:
    """Callback handler for LlamaIndex operations."""

    def __init__(self, logger: LoggerType | None) -> None:
        self.logger = logger
        self.steps: list[ReasoningStep] = []
        self.step_counter = 0
        self.retrieval_info: list[dict[str, t.Any]] = []

    def on_retrieve_start(self, query: str) -> None:
        """Called when retrieval starts."""
        self.step_counter += 1
        step = ReasoningStep(
            step_id=f"retrieve_{self.step_counter}",
            description="Document retrieval",
            input_data={"query": query},
        )
        self.steps.append(step)
        if self.logger is not None:
            self.logger.debug(f"Starting retrieval for query: {query[:100]}")

    def on_retrieve_end(self, nodes: list[t.Any]) -> None:
        """Called when retrieval ends."""
        if self.steps:
            last_step = self.steps[-1]
            last_step.output_data = {
                "retrieved_nodes": len(nodes),
                "scores": [node.score for node in nodes if node.score is not None],
            }

            # Store retrieval info for citation tracking
            self.retrieval_info = [
                {
                    "content": node.node.text[:200],
                    "score": node.score,
                    "metadata": node.node.metadata,
                }
                for node in nodes
            ]

        if self.logger is not None:
            self.logger.debug(f"Retrieved {len(nodes)} nodes")

    def on_synthesis_start(self, query: str) -> None:
        """Called when response synthesis starts."""
        self.step_counter += 1
        step = ReasoningStep(
            step_id=f"synthesis_{self.step_counter}",
            description="Response synthesis",
            input_data={"query": query},
        )
        self.steps.append(step)
        if self.logger is not None:
            self.logger.debug("Starting response synthesis")

    def on_synthesis_end(self, response: str) -> None:
        """Called when response synthesis ends."""
        if self.steps:
            last_step = self.steps[-1]
            last_step.output_data = {"response": response[:200]}
        if self.logger is not None:
            self.logger.debug("Response synthesis completed")


class Reasoning(ReasoningBase):
    """LlamaIndex-based reasoning adapter focused on RAG workflows."""

    def __init__(
        self,
        settings: LlamaIndexReasoningSettings | None = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings or LlamaIndexReasoningSettings()
        self._llm: t.Any | None = None
        self._indices: dict[str, t.Any] = {}
        self._query_engines: dict[str, t.Any] = {}
        self._agents: dict[str, t.Any] = {}
        self._chat_engines: dict[str, t.Any] = {}

        if not LLAMAINDEX_AVAILABLE:
            msg = (
                "LlamaIndex is not installed. Please install with: "
                "pip install 'acb[reasoning]' or pip install llama-index"
            )
            raise ImportError(
                msg,
            )

    async def _create_client(self) -> t.Any:
        """Create LlamaIndex OpenAI LLM client."""
        settings = self._settings
        if settings is None:
            msg = "Settings not initialized"
            raise ValueError(msg)

        if settings.api_key:
            api_key = settings.api_key.get_secret_value()
        else:
            import os

            api_key = os.getenv("OPENAI_API_KEY")  # type: ignore[assignment]
            if not api_key:
                msg = "OpenAI API key required. Set OPENAI_API_KEY or provide api_key in settings."
                raise ValueError(
                    msg,
                )

        # Create OpenAI LLM
        llm = OpenAI(
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens_per_step,
            api_key=api_key,
            api_base=settings.base_url,
            timeout=settings.timeout_seconds,
        )

        # Configure global settings
        Settings.llm = llm
        Settings.chunk_size = getattr(settings, "chunk_size", 512)
        Settings.chunk_overlap = getattr(settings, "chunk_overlap", 50)

        return llm

    async def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Perform reasoning using LlamaIndex."""
        start_time = time.time()
        callback = LlamaIndexCallback(self.logger)

        try:
            await self._ensure_client()

            if request.strategy == ReasoningStrategy.RAG_WORKFLOW:
                response = await self._rag_workflow_reasoning(request, callback)
            elif request.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT:
                response = await self._chain_of_thought_reasoning(request, callback)
            elif request.strategy == ReasoningStrategy.REACT:
                response = await self._react_reasoning(request, callback)
            else:
                # Default to RAG workflow (LlamaIndex's strength)
                response = await self._rag_workflow_reasoning(request, callback)

            # Calculate metrics
            total_duration = int((time.time() - start_time) * 1000)
            response.total_duration_ms = total_duration
            response.reasoning_chain.extend(callback.steps)

            if not response.confidence_score:
                response.confidence_score = await calculate_confidence_score(
                    response.reasoning_chain,
                )

            # Add citation information
            settings = self._settings
            if (
                settings
                and getattr(settings, "enable_citation_tracking", False)
                and callback.retrieval_info
            ):
                response.sources_cited = callback.retrieval_info

            return response

        except Exception as e:
            if self.logger is not None:
                self.logger.exception(f"LlamaIndex reasoning failed: {e}")
            return ReasoningResponse(
                final_answer="",
                reasoning_chain=callback.steps,
                strategy_used=request.strategy,
                provider=ReasoningProvider.LLAMAINDEX,
                total_duration_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )

    async def _rag_workflow_reasoning(
        self,
        request: ReasoningRequest,
        callback: LlamaIndexCallback,
    ) -> ReasoningResponse:
        """Perform RAG workflow reasoning using LlamaIndex."""
        try:
            # Get or create index for knowledge base
            if request.context and request.context.knowledge_base:
                index = await self._get_or_create_index(request.context.knowledge_base)
                query_engine = await self._get_or_create_query_engine(
                    request.context.knowledge_base,
                    index,
                )
            else:
                # Create a simple query engine for general reasoning
                llm = await self._ensure_client()
                query_engine = self._create_simple_query_engine(llm)

            # Perform retrieval and reasoning
            callback.on_retrieve_start(request.query)

            # Execute query
            response = query_engine.query(request.query)

            # Extract retrieval information
            if hasattr(response, "source_nodes") and response.source_nodes:
                callback.on_retrieve_end(response.source_nodes)

            callback.on_synthesis_start(request.query)
            final_answer = str(response)
            callback.on_synthesis_end(final_answer)

            return ReasoningResponse(
                final_answer=final_answer,
                reasoning_chain=[],  # Will be populated by callback
                strategy_used=ReasoningStrategy.RAG_WORKFLOW,
                provider=ReasoningProvider.LLAMAINDEX,
                confidence_score=0.9,  # High confidence for RAG
            )

        except Exception as e:
            if self.logger is not None:
                self.logger.exception(f"RAG workflow failed: {e}")
            raise

    async def _chain_of_thought_reasoning(
        self,
        request: ReasoningRequest,
        callback: LlamaIndexCallback,
    ) -> ReasoningResponse:
        """Perform chain-of-thought reasoning using LlamaIndex."""
        llm = await self._ensure_client()

        # Create a step-by-step reasoning prompt
        cot_template = PromptTemplate(
            template="""
You are an expert reasoning assistant. Think through this problem step by step.

Question: {query_str}

Please follow this structured approach:

1. **Problem Understanding**: Clearly state what is being asked
2. **Information Analysis**: Identify key information and constraints
3. **Strategy Selection**: Choose the best approach to solve this problem
4. **Step-by-Step Reasoning**: Work through the problem systematically
5. **Verification**: Check your reasoning for errors
6. **Final Answer**: Provide a clear, concise conclusion

Let's work through this:
""",
        )

        # Create a simple query engine with the custom template
        query_engine = self._create_simple_query_engine(llm, cot_template)

        callback.on_synthesis_start(request.query)
        response = query_engine.query(request.query)
        final_answer = str(response)
        callback.on_synthesis_end(final_answer)

        return ReasoningResponse(
            final_answer=final_answer,
            reasoning_chain=[],
            strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
            provider=ReasoningProvider.LLAMAINDEX,
            confidence_score=0.8,
        )

    async def _react_reasoning(  # type: ignore[override]
        self,
        request: ReasoningRequest,
        callback: LlamaIndexCallback,
    ) -> ReasoningResponse:
        """Perform ReAct reasoning with tools using LlamaIndex."""
        if not request.tools:
            # Fall back to chain of thought if no tools
            return await self._chain_of_thought_reasoning(request, callback)

        llm = await self._ensure_client()

        # Convert tools to LlamaIndex format
        tools = []
        for tool_def in request.tools:

            def tool_func(input_str: str, tool_def: t.Any = tool_def) -> str:
                # Placeholder tool execution
                return f"Tool {tool_def.name} executed with: {input_str}"

            llamaindex_tool = FunctionTool.from_defaults(
                fn=tool_func,
                name=tool_def.name,
                description=tool_def.description,
            )
            tools.append(llamaindex_tool)

        # Create ReAct agent
        settings = self._settings
        verbose = getattr(settings, "verbose", False) if settings else False
        max_calls = getattr(settings, "max_function_calls", 10) if settings else 10

        agent = ReActAgent.from_tools(
            tools=tools,
            llm=llm,
            verbose=verbose,
            max_function_calls=max_calls,
        )

        # Execute agent
        response = agent.chat(request.query)

        return ReasoningResponse(
            final_answer=str(response),
            reasoning_chain=[],
            strategy_used=ReasoningStrategy.REACT,
            provider=ReasoningProvider.LLAMAINDEX,
            confidence_score=0.85,
        )

    async def _get_or_create_index(self, knowledge_base_name: str) -> t.Any:
        """Get existing index or create new one for knowledge base."""
        if knowledge_base_name in self._indices:
            return self._indices[knowledge_base_name]

        try:
            # Try to integrate with vector database adapter
            from acb.adapters import import_adapter

            Vector = import_adapter("vector")
            vector_adapter = depends.get(Vector)

            # Get documents from vector database
            # This is a simplified integration - in practice, you'd want
            # to properly convert vector DB results to LlamaIndex documents
            docs = await self._get_documents_from_vector_db(
                knowledge_base_name,
                vector_adapter,
            )

            if docs:
                # Create index from documents
                index = VectorStoreIndex.from_documents(docs)

                # Persist index if enabled
                settings = self._settings
                if settings and getattr(settings, "persist_index", False):
                    cache_dir = getattr(settings, "index_cache_dir", "./index_cache")
                    index.storage_context.persist(
                        persist_dir=f"{cache_dir}/{knowledge_base_name}",
                    )

                self._indices[knowledge_base_name] = index
                return index

        except Exception as e:
            if self.logger is not None:
                self.logger.warning(f"Failed to integrate with vector DB: {e}")

        # Fallback: create empty index
        index = VectorStoreIndex.from_documents([])
        self._indices[knowledge_base_name] = index
        return index

    async def _get_documents_from_vector_db(
        self,
        collection_name: str,
        vector_adapter: t.Any,
    ) -> list[t.Any]:
        """Get documents from vector database and convert to LlamaIndex format."""
        try:
            # Get all documents from collection (simplified)
            results = await vector_adapter.get_all(
                collection=collection_name,
                limit=1000,
            )

            documents = []
            for result in results:
                doc = Document(
                    text=result.get("text", ""),
                    metadata=result.get("metadata", {}),
                )
                documents.append(doc)

            return documents

        except Exception as e:
            if self.logger is not None:
                self.logger.exception(f"Failed to get documents from vector DB: {e}")
            return []

    async def _get_or_create_query_engine(
        self,
        knowledge_base_name: str,
        index: t.Any,
    ) -> t.Any:
        """Get existing query engine or create new one."""
        if knowledge_base_name in self._query_engines:
            return self._query_engines[knowledge_base_name]

        settings = self._settings
        top_k = getattr(settings, "similarity_top_k", 5) if settings else 5
        response_mode = (
            getattr(settings, "response_mode", "compact") if settings else "compact"
        )
        streaming = getattr(settings, "streaming", False) if settings else False

        # Create retriever
        retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=top_k,
        )

        # Create response synthesizer
        response_synthesizer = get_response_synthesizer(
            response_mode=response_mode,
            streaming=streaming,
        )

        # Create query engine
        query_engine = RetrieverQueryEngine(
            retriever=retriever,
            response_synthesizer=response_synthesizer,
        )

        self._query_engines[knowledge_base_name] = query_engine
        return query_engine

    def _create_simple_query_engine(
        self,
        llm: t.Any,
        template: t.Any | None = None,
    ) -> t.Any:
        """Create a simple query engine for general reasoning."""
        # Create empty index for simple querying
        index = VectorStoreIndex.from_documents([])

        settings = self._settings
        response_mode = (
            getattr(settings, "response_mode", "compact") if settings else "compact"
        )
        streaming = getattr(settings, "streaming", False) if settings else False

        # Create query engine
        query_engine = index.as_query_engine(
            llm=llm,
            response_mode=response_mode,
            streaming=streaming,
        )

        if template:
            query_engine.update_prompts(
                {"response_synthesizer:text_qa_template": template},
            )

        return query_engine

    async def create_chat_engine(
        self,
        session_id: str,
        knowledge_base: str | None = None,
    ) -> t.Any:
        """Create a chat engine for conversational reasoning."""
        if session_id in self._chat_engines:
            return self._chat_engines[session_id]

        llm = await self._ensure_client()

        settings = self._settings
        token_limit = (
            getattr(settings, "chat_memory_token_limit", 3000) if settings else 3000
        )
        streaming = getattr(settings, "streaming", False) if settings else False

        if knowledge_base:
            # Create chat engine with knowledge base
            index = await self._get_or_create_index(knowledge_base)
            chat_engine = index.as_chat_engine(
                llm=llm,
                memory=ChatMemoryBuffer.from_defaults(
                    token_limit=token_limit,
                ),
                streaming=streaming,
            )
        else:
            # Create simple chat engine
            chat_engine = SimpleChatEngine.from_defaults(
                llm=llm,
                memory=ChatMemoryBuffer.from_defaults(
                    token_limit=token_limit,
                ),
            )

        self._chat_engines[session_id] = chat_engine
        return chat_engine

    async def chat(
        self,
        session_id: str,
        message: str,
        knowledge_base: str | None = None,
    ) -> str:
        """Perform conversational reasoning."""
        chat_engine = await self.create_chat_engine(session_id, knowledge_base)
        response = chat_engine.chat(message)
        return str(response)

    async def add_documents_to_index(
        self,
        knowledge_base_name: str,
        documents: list[str],
        metadata: list[dict[str, t.Any]] | None = None,
    ) -> None:
        """Add documents to a knowledge base index."""
        # Convert to LlamaIndex documents
        docs = []
        for i, doc_text in enumerate(documents):
            doc_metadata = metadata[i] if metadata and i < len(metadata) else {}
            doc = Document(text=doc_text, metadata=doc_metadata)
            docs.append(doc)

        # Get or create index
        index = await self._get_or_create_index(knowledge_base_name)

        # Add documents to index
        for doc in docs:
            index.insert(doc)

        # Invalidate cached query engine to reflect new documents
        if knowledge_base_name in self._query_engines:
            del self._query_engines[knowledge_base_name]

    async def _tree_of_thoughts(
        self,
        request: ReasoningRequest,
        num_paths: int,
    ) -> ReasoningResponse:
        """Enhanced tree-of-thoughts using LlamaIndex."""
        await self._ensure_client()

        # Create different reasoning perspectives
        perspectives = [
            "Analyze this systematically using first principles",
            "Consider this from a practical, implementation-focused view",
            "Examine this through a theoretical and abstract lens",
            "Approach this with creative and innovative thinking",
            "Focus on potential risks and failure modes",
        ]

        tasks = []
        for i in range(min(num_paths, len(perspectives))):
            enhanced_query = f"{perspectives[i]}: {request.query}"
            path_request = ReasoningRequest(
                query=enhanced_query,
                strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
                context=request.context,
                max_steps=request.max_steps,
                temperature=request.temperature + (i * 0.1),
                model=request.model,
            )
            tasks.append(self._reason(path_request))

        # Execute paths in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Synthesize results
        valid_results = [
            r for r in results if isinstance(r, ReasoningResponse) and not r.error
        ]
        if not valid_results:
            return ReasoningResponse(
                final_answer="Failed to generate valid reasoning paths",
                reasoning_chain=[],
                strategy_used=ReasoningStrategy.TREE_OF_THOUGHTS,
                provider=ReasoningProvider.LLAMAINDEX,
                error="All reasoning paths failed",
            )

        # Use LlamaIndex to synthesize the final answer
        synthesis_docs = [
            Document(
                text=f"Reasoning Path {i + 1}: {result.final_answer}",
                metadata={"path": i + 1, "confidence": result.confidence_score or 0.0},
            )
            for i, result in enumerate(valid_results)
        ]

        synthesis_index = VectorStoreIndex.from_documents(synthesis_docs)
        synthesis_engine = synthesis_index.as_query_engine(
            response_mode="tree_summarize",
        )

        synthesis_query = f"Based on multiple reasoning paths, provide the best answer to: {request.query}"
        final_response = synthesis_engine.query(synthesis_query)

        # Combine reasoning chains
        combined_chain = []
        for result in valid_results:
            combined_chain.extend(result.reasoning_chain)

        best_confidence = max(
            result.confidence_score or 0.0 for result in valid_results
        )

        return ReasoningResponse(
            final_answer=str(final_response),
            reasoning_chain=combined_chain,
            strategy_used=ReasoningStrategy.TREE_OF_THOUGHTS,
            provider=ReasoningProvider.LLAMAINDEX,
            confidence_score=min(best_confidence + 0.1, 1.0),
        )


ReasoningSettings = LlamaIndexReasoningSettings

depends.set(Reasoning, "llamaindex")

# Export the adapter class
__all__ = [
    "MODULE_METADATA",
    "LlamaIndexReasoningSettings",
    "Reasoning",
    "ReasoningSettings",
]
