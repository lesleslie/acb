"""LangChain reasoning adapter for advanced AI reasoning workflows."""

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

# Conditional imports for LangChain
try:
    from langchain.agents import (  # type: ignore[import-not-found,attr-defined]
        AgentExecutor,
        initialize_agent,
    )
    from langchain.agents.agent_types import AgentType  # type: ignore[import-not-found]
    from langchain.callbacks import (  # type: ignore[import-not-found]
        AsyncCallbackHandler,
    )
    from langchain.chains import (  # type: ignore[import-not-found]
        ConversationChain,
        LLMChain,
    )
    from langchain.chains.conversation.memory import (  # type: ignore[import-not-found]
        ConversationBufferMemory,
        ConversationSummaryMemory,
    )
    from langchain.llms.base import LLM  # type: ignore[import-not-found]
    from langchain.prompts import PromptTemplate  # type: ignore[import-not-found]
    from langchain.tools import Tool  # type: ignore[import-not-found,attr-defined]
    from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

    # Mock classes for type hints
    class LLM:  # type: ignore[no-redef]
        pass

    class AsyncCallbackHandler:  # type: ignore[no-redef]
        pass

    class AgentExecutor:  # type: ignore[no-redef]
        pass

    class ConversationChain:  # type: ignore[no-redef]
        pass


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="LangChain Reasoning",
    category="reasoning",
    provider="langchain",
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
    ],
    required_packages=[
        "langchain>=0.1.0",
        "langchain-openai>=0.1.0",
        "langchain-community>=0.0.20",
        "openai>=1.0.0",
    ],
    description="Advanced reasoning capabilities using LangChain framework with chain-of-thought, agents, and tool integration",
    settings_class="LangChainReasoningSettings",
    config_example={
        "api_key": "your-openai-api-key",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_reasoning_steps": 10,
        "enable_reflection": True,
        "agent_type": "react",
    },
)


class LangChainReasoningSettings(ReasoningBaseSettings):
    """Settings for LangChain reasoning adapter."""

    # LangChain specific settings
    agent_type: str = (
        "react"  # react, zero-shot-react-description, conversational-react-description
    )
    memory_type: str = "buffer"  # buffer, summary, token_buffer
    max_memory_tokens: int = 2000
    verbose: bool = False

    # Chain settings
    chain_type: str = "conversation"  # conversation, llm, sequential
    prompt_template: str | None = None

    # Tool settings
    tool_return_direct: bool = False
    max_execution_time: int = 300

    # Streaming settings
    enable_streaming: bool = False
    stream_callback_timeout: float = 1.0


class LangChainCallback(AsyncCallbackHandler):  # type: ignore[misc]
    """Async callback handler for LangChain operations."""

    def __init__(self, logger: LoggerType | None) -> None:
        self.logger = logger
        self.steps: list[ReasoningStep] = []
        self.current_step: ReasoningStep | None = None
        self.step_counter = 0

    async def on_chain_start(
        self,
        serialized: dict[str, t.Any],
        inputs: dict[str, t.Any],
        **kwargs: t.Any,
    ) -> None:
        """Called when a chain starts running."""
        self.step_counter += 1
        self.current_step = ReasoningStep(
            step_id=f"step_{self.step_counter}",
            description=f"Chain started: {serialized.get('name', 'Unknown')}",
            input_data=inputs,
        )
        if self.logger is not None:
            self.logger.debug(f"Chain started: {serialized.get('name', 'Unknown')}")

    async def on_chain_end(self, outputs: dict[str, t.Any], **kwargs: t.Any) -> None:
        """Called when a chain ends running."""
        if self.current_step:
            self.current_step.output_data = outputs
            self.steps.append(self.current_step)
            self.current_step = None
        if self.logger is not None:
            self.logger.debug(f"Chain ended with outputs: {list(outputs.keys())}")

    async def on_chain_error(self, error: Exception, **kwargs: t.Any) -> None:
        """Called when a chain errors."""
        if self.current_step:
            self.current_step.error = str(error)
            self.steps.append(self.current_step)
            self.current_step = None
        if self.logger is not None:
            self.logger.error(f"Chain error: {error}")

    async def on_tool_start(
        self,
        serialized: dict[str, t.Any],
        input_str: str,
        **kwargs: t.Any,
    ) -> None:
        """Called when a tool starts running."""
        tool_name = serialized.get("name", "Unknown Tool")
        if self.logger is not None:
            self.logger.debug(
                f"Tool started: {tool_name} with input: {input_str[:100]}..."
            )

    async def on_tool_end(self, output: str, **kwargs: t.Any) -> None:
        """Called when a tool ends running."""
        if self.logger is not None:
            self.logger.debug(f"Tool ended with output: {output[:100]}")

    async def on_tool_error(self, error: Exception, **kwargs: t.Any) -> None:
        """Called when a tool errors."""
        if self.logger is not None:
            self.logger.error(f"Tool error: {error}")

    async def on_agent_action(self: t.Any, action: t.Any, **kwargs: t.Any) -> None:
        """Called when an agent takes an action."""
        if self.logger is not None:
            self.logger.debug(f"Agent action: {action.tool} - {action.tool_input}")

    async def on_agent_finish(self: t.Any, finish: t.Any, **kwargs: t.Any) -> None:
        """Called when an agent finishes."""
        if self.logger is not None:
            self.logger.debug(f"Agent finished: {finish.return_values}")


class Reasoning(ReasoningBase):
    """LangChain-based reasoning adapter."""

    def __init__(
        self,
        settings: LangChainReasoningSettings | None = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings or LangChainReasoningSettings()
        self._llm: LLM | None = None
        self._agents: dict[str, AgentExecutor] = {}
        self._chains: dict[str, ConversationChain] = {}
        self._memories: dict[str, t.Any] = {}

        if not LANGCHAIN_AVAILABLE:
            msg = (
                "LangChain is not installed. Please install with: "
                "pip install 'acb[reasoning]' or pip install langchain langchain-openai"
            )
            raise ImportError(
                msg,
            )

    async def _create_client(self) -> LLM:
        """Create LangChain LLM client."""
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

        # Create ChatOpenAI instance for better chat capabilities
        return ChatOpenAI(  # type: ignore[call-arg]
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens_per_step,
            openai_api_key=api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            streaming=getattr(settings, "enable_streaming", False),
        )

    async def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Perform reasoning using LangChain."""
        start_time = time.time()
        callback = LangChainCallback(self.logger)

        try:
            llm = await self._ensure_client()

            if request.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT:
                response = await self._chain_of_thought_reasoning(
                    request,
                    llm,
                    callback,
                )
            elif request.strategy == ReasoningStrategy.REACT:
                response = await self._react_reasoning(request, llm, callback)
            elif request.strategy == ReasoningStrategy.RAG_WORKFLOW:
                response = await self._rag_workflow_reasoning(request, llm, callback)
            elif request.strategy == ReasoningStrategy.RULE_BASED:
                response = await self._rule_based_reasoning(request, llm, callback)
            else:
                # Default to chain of thought
                response = await self._chain_of_thought_reasoning(
                    request,
                    llm,
                    callback,
                )

            # Calculate metrics
            total_duration = int((time.time() - start_time) * 1000)
            response.total_duration_ms = total_duration
            response.reasoning_chain.extend(callback.steps)

            if not response.confidence_score:
                response.confidence_score = await calculate_confidence_score(
                    response.reasoning_chain,
                )

            # Update memory if enabled
            if request.enable_memory and request.context:
                await self._update_memory(
                    request.context.session_id,
                    request.query,
                    response.final_answer,
                )

            return response

        except Exception as e:
            if self.logger is not None:
                self.logger.exception(f"Reasoning failed: {e}")
            return ReasoningResponse(
                final_answer="",
                reasoning_chain=callback.steps,
                strategy_used=request.strategy,
                provider=ReasoningProvider.LANGCHAIN,
                total_duration_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )

    async def _chain_of_thought_reasoning(
        self,
        request: ReasoningRequest,
        llm: LLM,
        callback: LangChainCallback,
    ) -> ReasoningResponse:
        """Perform chain-of-thought reasoning."""
        # Create prompt template for chain of thought
        prompt_template = (
            request.custom_instructions
            or """
You are an expert reasoning assistant. Think through this problem step by step.

Question: {question}

Let's work through this systematically:

1. First, understand what is being asked
2. Identify the key information and constraints
3. Break down the problem into smaller parts
4. Reason through each part carefully
5. Synthesize your findings into a final answer

Please show your reasoning clearly at each step.

Reasoning:
"""
        )

        prompt = PromptTemplate(template=prompt_template, input_variables=["question"])

        # Create chain
        settings = self._settings
        verbose = getattr(settings, "verbose", False) if settings else False

        chain = LLMChain(
            llm=llm,
            prompt=prompt,
            verbose=verbose,
            callbacks=[callback],
        )

        # Execute reasoning
        result = await chain.arun(question=request.query)

        return ReasoningResponse(
            final_answer=result,
            reasoning_chain=[],  # Will be populated by callback
            strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
            provider=ReasoningProvider.LANGCHAIN,
            confidence_score=0.8,  # Default confidence
        )

    async def _react_reasoning(  # type: ignore[override]
        self,
        request: ReasoningRequest,
        llm: LLM,
        callback: LangChainCallback,
    ) -> ReasoningResponse:
        """Perform ReAct reasoning with tools."""
        if not request.tools:
            # Fall back to chain of thought if no tools provided
            return await self._chain_of_thought_reasoning(request, llm, callback)

        # Convert tools to LangChain format
        langchain_tools = []
        for tool_def in request.tools:

            def tool_func(input_str: str, tool_def: t.Any = tool_def) -> str:
                # This is a placeholder - in practice, you'd implement actual tool execution
                return f"Tool {tool_def.name} executed with input: {input_str}"

            settings = self._settings
            return_direct = (
                getattr(settings, "tool_return_direct", False) if settings else False
            )

            langchain_tool = Tool(
                name=tool_def.name,
                description=tool_def.description,
                func=tool_func,
                return_direct=return_direct,
            )
            langchain_tools.append(langchain_tool)

        # Create ReAct agent
        settings = self._settings
        verbose = getattr(settings, "verbose", False) if settings else False

        agent = initialize_agent(
            tools=langchain_tools,
            llm=llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=verbose,
            max_iterations=request.max_steps,
            callbacks=[callback],
        )

        # Execute agent
        result = await agent.arun(request.query)

        return ReasoningResponse(
            final_answer=result,
            reasoning_chain=[],  # Will be populated by callback
            strategy_used=ReasoningStrategy.REACT,
            provider=ReasoningProvider.LANGCHAIN,
            confidence_score=0.85,  # Higher confidence with tools
        )

    async def _rag_workflow_reasoning(
        self,
        request: ReasoningRequest,
        llm: LLM,
        callback: LangChainCallback,
    ) -> ReasoningResponse:
        """Perform RAG workflow reasoning."""
        try:
            # Retrieve relevant contexts
            contexts = []
            if request.context and request.context.retrieved_contexts:
                contexts = request.context.retrieved_contexts
            # Attempt to retrieve contexts
            elif request.context and request.context.knowledge_base:
                contexts = await self._retrieve_contexts(
                    request.query,
                    request.context.knowledge_base,
                )

            # Create RAG prompt with retrieved contexts
            context_text = "\n\n".join(
                [
                    f"Source {i + 1}: {ctx.get('content', '')}"
                    for i, ctx in enumerate(contexts)
                ],
            )

            rag_prompt_template = f"""
Based on the following context information, please answer the question.

Context:
{context_text}

Question: {{question}}

Please provide a comprehensive answer based on the context provided. If the context doesn't contain enough information to fully answer the question, please indicate what additional information would be needed.

Answer:
"""

            prompt = PromptTemplate(
                template=rag_prompt_template,
                input_variables=["question"],
            )

            # Create chain
            settings = self._settings
            verbose = getattr(settings, "verbose", False) if settings else False

            chain = LLMChain(
                llm=llm,
                prompt=prompt,
                verbose=verbose,
                callbacks=[callback],
            )

            # Execute reasoning
            result = await chain.arun(question=request.query)

            # Extract sources for citation tracking
            sources_cited = [
                {
                    "content": ctx.get("content", "")[:200] + "...",
                    "metadata": ctx.get("metadata", {}),
                    "score": ctx.get("score", 0.0),
                }
                for ctx in contexts
            ]

            return ReasoningResponse(
                final_answer=result,
                reasoning_chain=[],  # Will be populated by callback
                strategy_used=ReasoningStrategy.RAG_WORKFLOW,
                provider=ReasoningProvider.LANGCHAIN,
                confidence_score=0.9,  # High confidence with retrieved context
                sources_cited=sources_cited,
            )

        except Exception as e:
            if self.logger is not None:
                self.logger.exception(f"RAG workflow failed: {e}")
            # Fall back to regular reasoning
            return await self._chain_of_thought_reasoning(request, llm, callback)

    async def _rule_based_reasoning(
        self,
        request: ReasoningRequest,
        llm: LLM,
        callback: LangChainCallback,
    ) -> ReasoningResponse:
        """Perform rule-based reasoning."""
        # This would typically involve decision tree evaluation
        # For now, we'll use LLM to simulate rule-based reasoning

        rule_prompt_template = """
You are a rule-based reasoning system. Analyze the given input and apply logical rules to determine the appropriate response.

Input: {input}

Please follow these steps:
1. Identify the relevant rules that apply to this input
2. Evaluate each rule systematically
3. Determine which rule(s) are triggered
4. Apply the appropriate actions based on the triggered rules
5. Provide the final decision

Rules-based Analysis:
"""

        prompt = PromptTemplate(
            template=rule_prompt_template,
            input_variables=["input"],
        )

        # Create chain
        settings = self._settings
        verbose = getattr(settings, "verbose", False) if settings else False

        chain = LLMChain(
            llm=llm,
            prompt=prompt,
            verbose=verbose,
            callbacks=[callback],
        )

        # Execute reasoning
        result = await chain.arun(input=request.query)

        return ReasoningResponse(
            final_answer=result,
            reasoning_chain=[],  # Will be populated by callback
            strategy_used=ReasoningStrategy.RULE_BASED,
            provider=ReasoningProvider.LANGCHAIN,
            confidence_score=0.75,  # Moderate confidence for rule-based
        )

    async def _update_memory(self, session_id: str, query: str, response: str) -> None:
        """Update conversation memory."""
        if session_id not in self._memories:
            settings = self._settings
            memory_type = (
                getattr(settings, "memory_type", "buffer") if settings else "buffer"
            )

            if memory_type == "summary":
                llm = await self._ensure_client()
                self._memories[session_id] = ConversationSummaryMemory(llm=llm)
            else:
                self._memories[session_id] = ConversationBufferMemory()

        memory = self._memories[session_id]

        # Add conversation to memory
        memory.save_context({"input": query}, {"output": response})

    async def _get_memory_context(self, session_id: str) -> str:
        """Get memory context for session."""
        if session_id not in self._memories:
            return ""

        memory = self._memories[session_id]
        return memory.buffer if hasattr(memory, "buffer") else str(memory)

    async def _tree_of_thoughts(
        self,
        request: ReasoningRequest,
        num_paths: int,
    ) -> ReasoningResponse:
        """Enhanced tree-of-thoughts implementation using LangChain."""
        llm = await self._ensure_client()

        # Create different reasoning paths with varied prompts
        path_prompts = [
            "Approach this problem analytically and systematically:",
            "Think about this creatively and consider alternative perspectives:",
            "Focus on the practical implications and real-world constraints:",
            "Consider the theoretical foundations and abstract principles:",
            "Examine this from multiple stakeholder viewpoints:",
        ]

        tasks = []
        for i in range(min(num_paths, len(path_prompts))):
            path_request = ReasoningRequest(
                query=f"{path_prompts[i]} {request.query}",
                strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
                context=request.context,
                max_steps=request.max_steps,
                temperature=request.temperature + (i * 0.1),
                model=request.model,
            )
            tasks.append(self._reason(path_request))

        # Execute paths in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Select best path and combine insights
        valid_results = [
            r for r in results if isinstance(r, ReasoningResponse) and not r.error
        ]
        if not valid_results:
            return ReasoningResponse(
                final_answer="Failed to generate valid reasoning paths",
                reasoning_chain=[],
                strategy_used=ReasoningStrategy.TREE_OF_THOUGHTS,
                provider=ReasoningProvider.LANGCHAIN,
                error="All reasoning paths failed",
            )

        # Combine insights from all paths
        combined_insights = "\n\n".join(
            [
                f"Path {i + 1} Analysis: {result.final_answer}"
                for i, result in enumerate(valid_results)
            ],
        )

        # Synthesize final answer
        synthesis_prompt = f"""
Based on the following multiple reasoning paths, provide a comprehensive and well-reasoned final answer:

{combined_insights}

Original Question: {request.query}

Please synthesize the insights from all paths and provide the best possible answer:
"""

        settings = self._settings
        verbose = getattr(settings, "verbose", False) if settings else False

        synthesis_chain = LLMChain(
            llm=llm,
            prompt=PromptTemplate(template=synthesis_prompt, input_variables=[]),
            verbose=verbose,
        )

        final_answer = await synthesis_chain.arun()

        # Combine reasoning chains from all paths
        combined_chain = []
        for result in valid_results:
            combined_chain.extend(result.reasoning_chain)

        best_confidence = max(
            result.confidence_score or 0.0 for result in valid_results
        )

        return ReasoningResponse(
            final_answer=final_answer,
            reasoning_chain=combined_chain,
            strategy_used=ReasoningStrategy.TREE_OF_THOUGHTS,
            provider=ReasoningProvider.LANGCHAIN,
            confidence_score=min(
                best_confidence + 0.1,
                1.0,
            ),  # Boost confidence for synthesis
        )


ReasoningSettings = LangChainReasoningSettings

depends.set(Reasoning, "langchain")


# Export the adapter class
__all__ = [
    "MODULE_METADATA",
    "LangChainReasoningSettings",
    "Reasoning",
    "ReasoningSettings",
]
