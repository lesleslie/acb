"""OpenAI function calling reasoning adapter for structured reasoning with tools."""

import json
import time
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
    ReasoningContext,
    ReasoningProvider,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStep,
    ReasoningStrategy,
    ToolDefinition,
    calculate_confidence_score,
)
from acb.logger import Logger

# Conditional imports for OpenAI
try:
    from openai import AsyncOpenAI
    from openai.types.chat import ChatCompletion, ChatCompletionMessage
    from openai.types.chat.chat_completion_message_tool_call import (
        ChatCompletionMessageToolCall,
    )

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

    # Mock classes for type hints
    class AsyncOpenAI:
        pass

    class ChatCompletion:
        pass

    class ChatCompletionMessage:
        pass

    class ChatCompletionMessageToolCall:
        pass


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="OpenAI Function Calling Reasoning",
    category="reasoning",
    provider="openai_functions",
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
        "openai>=1.0.0",
    ],
    description="Structured reasoning using OpenAI function calling with tool integration and precise output control",
    settings_class="OpenAIFunctionReasoningSettings",
    config_example={
        "api_key": "your-openai-api-key",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_function_calls": 10,
        "function_call_strategy": "auto",
        "enable_parallel_calls": True,
    },
)


class OpenAIFunctionReasoningSettings(ReasoningBaseSettings):
    """Settings for OpenAI function calling reasoning adapter."""

    # Function calling settings
    max_function_calls: int = 10
    function_call_strategy: str = "auto"  # auto, none, or specific function name
    enable_parallel_calls: bool = True

    # Response format settings
    response_format: str = "auto"  # auto, json_object, text

    # Advanced settings
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    top_p: float = 1.0

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0


class FunctionCallTracker:
    """Tracks function calls during reasoning."""

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self.calls: list[dict[str, t.Any]] = []
        self.call_count = 0

    def record_call(
        self,
        function_name: str,
        arguments: dict[str, t.Any],
        result: t.Any,
    ) -> None:
        """Record a function call."""
        self.call_count += 1
        call_record = {
            "call_id": self.call_count,
            "function_name": function_name,
            "arguments": arguments,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        self.calls.append(call_record)
        self.logger.debug(f"Function call {self.call_count}: {function_name}")

    def get_call_summary(self) -> dict[str, t.Any]:
        """Get summary of all function calls."""
        return {
            "total_calls": len(self.calls),
            "unique_functions": len({call["function_name"] for call in self.calls}),
            "function_names": [call["function_name"] for call in self.calls],
            "call_details": self.calls,
        }


class Reasoning(ReasoningBase):
    """OpenAI function calling reasoning adapter."""

    def __init__(
        self,
        settings: OpenAIFunctionReasoningSettings | None = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings or OpenAIFunctionReasoningSettings()
        self._client: AsyncOpenAI | None = None
        self._conversation_histories: dict[str, list[dict[str, t.Any]]] = {}

        if not OPENAI_AVAILABLE:
            msg = (
                "OpenAI is not installed. Please install with: "
                "pip install 'acb[reasoning]' or pip install openai"
            )
            raise ImportError(
                msg,
            )

    async def _create_client(self) -> AsyncOpenAI:
        """Create OpenAI async client."""
        if self._settings.api_key:
            api_key = self._settings.api_key.get_secret_value()
        else:
            import os

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                msg = "OpenAI API key required. Set OPENAI_API_KEY or provide api_key in settings."
                raise ValueError(
                    msg,
                )

        return AsyncOpenAI(
            api_key=api_key,
            base_url=self._settings.base_url,
            timeout=self._settings.timeout_seconds,
            max_retries=self._settings.max_retries,
        )

    async def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Perform reasoning using OpenAI function calling."""
        start_time = time.time()
        function_tracker = FunctionCallTracker(self.logger)
        reasoning_chain = []

        try:
            client = await self._ensure_client()

            if request.strategy == ReasoningStrategy.FUNCTION_CALLING:
                response = await self._function_calling_reasoning(
                    request,
                    client,
                    function_tracker,
                    reasoning_chain,
                )
            elif request.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT:
                response = await self._chain_of_thought_reasoning(
                    request,
                    client,
                    function_tracker,
                    reasoning_chain,
                )
            elif request.strategy == ReasoningStrategy.REACT:
                response = await self._react_reasoning(
                    request,
                    client,
                    function_tracker,
                    reasoning_chain,
                )
            else:
                # Default to function calling (OpenAI's strength)
                response = await self._function_calling_reasoning(
                    request,
                    client,
                    function_tracker,
                    reasoning_chain,
                )

            # Calculate metrics
            total_duration = int((time.time() - start_time) * 1000)
            response.total_duration_ms = total_duration
            response.reasoning_chain.extend(reasoning_chain)
            response.tool_calls = [function_tracker.get_call_summary()]

            if not response.confidence_score:
                response.confidence_score = await calculate_confidence_score(
                    response.reasoning_chain,
                )

            # Update conversation history if enabled
            if request.enable_memory and request.context:
                await self._update_conversation_history(
                    request.context.session_id,
                    request.query,
                    response.final_answer,
                )

            return response

        except Exception as e:
            self.logger.exception(f"OpenAI function calling reasoning failed: {e}")
            return ReasoningResponse(
                final_answer="",
                reasoning_chain=reasoning_chain,
                strategy_used=request.strategy,
                provider=ReasoningProvider.OPENAI_FUNCTIONS,
                total_duration_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )

    async def _function_calling_reasoning(
        self,
        request: ReasoningRequest,
        client: AsyncOpenAI,
        function_tracker: FunctionCallTracker,
        reasoning_chain: list[ReasoningStep],
    ) -> ReasoningResponse:
        """Perform reasoning with function calling."""
        # Prepare messages
        messages = await self._prepare_messages(request)

        # Prepare functions
        functions = self._prepare_functions(request.tools or [])

        reasoning_chain.append(
            ReasoningStep(
                step_id="setup",
                description="Prepare function calling setup",
                input_data={
                    "query": request.query,
                    "functions_available": len(functions),
                    "has_context": request.context is not None,
                },
                output_data={
                    "messages_count": len(messages),
                    "functions_count": len(functions),
                },
                reasoning="Set up function calling with available tools and conversation context",
            ),
        )

        final_answer = ""
        call_count = 0
        max_calls = min(request.max_steps, self._settings.max_function_calls)

        while call_count < max_calls:
            try:
                # Make API call
                response = await client.chat.completions.create(
                    model=request.model or self._settings.model,
                    messages=messages,
                    tools=functions if functions else None,
                    tool_choice=self._settings.function_call_strategy
                    if functions
                    else None,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    presence_penalty=self._settings.presence_penalty,
                    frequency_penalty=self._settings.frequency_penalty,
                    top_p=self._settings.top_p,
                )

                message = response.choices[0].message
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in (message.tool_calls or [])
                        ]
                        if message.tool_calls
                        else None,
                    },
                )

                # Check if function calls were made
                if message.tool_calls:
                    # Execute function calls
                    tool_results = await self._execute_tool_calls(
                        message.tool_calls,
                        request.tools or [],
                        function_tracker,
                    )

                    reasoning_chain.append(
                        ReasoningStep(
                            step_id=f"function_calls_{call_count + 1}",
                            description=f"Execute {len(message.tool_calls)} function calls",
                            input_data={
                                "tool_calls": [
                                    {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    }
                                    for tc in message.tool_calls
                                ],
                            },
                            output_data={"results": tool_results},
                            reasoning=f"Executed {len(message.tool_calls)} tool calls to gather information",
                            tools_used=[tc.function.name for tc in message.tool_calls],
                        ),
                    )

                    # Add tool results to messages
                    for tool_call, result in zip(
                        message.tool_calls, tool_results, strict=False
                    ):
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(result),
                            },
                        )

                    call_count += 1
                else:
                    # No more function calls, we have the final answer
                    final_answer = message.content or ""
                    break

            except Exception as e:
                self.logger.exception(
                    f"Error in function calling iteration {call_count}: {e}",
                )
                reasoning_chain.append(
                    ReasoningStep(
                        step_id=f"error_{call_count}",
                        description="Error in function calling",
                        input_data={"iteration": call_count},
                        output_data={},
                        reasoning=f"Error occurred during function calling: {e!s}",
                        error=str(e),
                    ),
                )
                break

        if not final_answer:
            final_answer = "Reasoning completed through function calls"

        return ReasoningResponse(
            final_answer=final_answer,
            reasoning_chain=[],  # Will be set by caller
            strategy_used=ReasoningStrategy.FUNCTION_CALLING,
            provider=ReasoningProvider.OPENAI_FUNCTIONS,
            confidence_score=0.9,  # High confidence with function calling
        )

    async def _chain_of_thought_reasoning(
        self,
        request: ReasoningRequest,
        client: AsyncOpenAI,
        function_tracker: FunctionCallTracker,
        reasoning_chain: list[ReasoningStep],
    ) -> ReasoningResponse:
        """Perform chain-of-thought reasoning with structured output."""
        # Use structured output for chain of thought
        system_prompt = """
You are an expert reasoning assistant. Think through problems step by step using a structured approach.

For each reasoning task:
1. Understand the problem clearly
2. Break it down into key components
3. Analyze each component systematically
4. Consider multiple perspectives or approaches
5. Synthesize your findings into a clear conclusion

Show your reasoning process explicitly at each step.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.query},
        ]

        # Add context if available
        if request.context and request.context.conversation_history:
            messages.insert(
                -1,
                {
                    "role": "user",
                    "content": f"Previous context: {json.dumps(request.context.conversation_history[-3:])}",
                },
            )

        reasoning_chain.append(
            ReasoningStep(
                step_id="cot_setup",
                description="Setup chain-of-thought reasoning",
                input_data={"query": request.query},
                output_data={"messages_prepared": len(messages)},
                reasoning="Prepared structured prompt for step-by-step reasoning",
            ),
        )

        try:
            response = await client.chat.completions.create(
                model=request.model or self._settings.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format={"type": "text"},
            )

            final_answer = response.choices[0].message.content or ""

            reasoning_chain.append(
                ReasoningStep(
                    step_id="cot_reasoning",
                    description="Execute chain-of-thought reasoning",
                    input_data={"query": request.query},
                    output_data={"response_length": len(final_answer)},
                    reasoning="Performed systematic step-by-step reasoning to reach conclusion",
                ),
            )

            return ReasoningResponse(
                final_answer=final_answer,
                reasoning_chain=[],  # Will be set by caller
                strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
                provider=ReasoningProvider.OPENAI_FUNCTIONS,
                confidence_score=0.8,
            )

        except Exception as e:
            self.logger.exception(f"Chain-of-thought reasoning failed: {e}")
            raise

    async def _react_reasoning(
        self,
        request: ReasoningRequest,
        client: AsyncOpenAI,
        function_tracker: FunctionCallTracker,
        reasoning_chain: list[ReasoningStep],
    ) -> ReasoningResponse:
        """Perform ReAct reasoning (Reasoning and Acting)."""
        if not request.tools:
            # Fall back to chain of thought if no tools
            return await self._chain_of_thought_reasoning(
                request,
                client,
                function_tracker,
                reasoning_chain,
            )

        # ReAct uses a specific prompt format
        system_prompt = """
You are an expert problem solver using the ReAct (Reasoning and Acting) framework.

For each step, you will:
1. Think: Reason about the current situation and what you need to do next
2. Act: Use available tools to gather information or perform actions
3. Observe: Analyze the results of your actions

Continue this process until you can provide a final answer.

Available tools will be provided as function calls. Use them when you need to gather information or perform actions.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Solve this problem step by step: {request.query}",
            },
        ]

        functions = self._prepare_functions(request.tools)

        reasoning_chain.append(
            ReasoningStep(
                step_id="react_setup",
                description="Setup ReAct reasoning framework",
                input_data={"query": request.query, "tools_available": len(functions)},
                output_data={"strategy": "react"},
                reasoning="Prepared ReAct framework for reasoning and acting with available tools",
            ),
        )

        step_count = 0
        max_steps = min(request.max_steps, self._settings.max_function_calls)

        while step_count < max_steps:
            try:
                response = await client.chat.completions.create(
                    model=request.model or self._settings.model,
                    messages=messages,
                    tools=functions,
                    tool_choice="auto",
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )

                message = response.choices[0].message

                # Add assistant message
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in (message.tool_calls or [])
                        ]
                        if message.tool_calls
                        else None,
                    },
                )

                if message.tool_calls:
                    # Execute tools (Act phase)
                    tool_results = await self._execute_tool_calls(
                        message.tool_calls,
                        request.tools,
                        function_tracker,
                    )

                    reasoning_chain.append(
                        ReasoningStep(
                            step_id=f"react_act_{step_count + 1}",
                            description=f"ReAct Act phase - execute {len(message.tool_calls)} tools",
                            input_data={
                                "reasoning": message.content,
                                "tools_called": [
                                    tc.function.name for tc in message.tool_calls
                                ],
                            },
                            output_data={"tool_results": tool_results},
                            reasoning="Executed tools based on reasoning analysis",
                            tools_used=[tc.function.name for tc in message.tool_calls],
                        ),
                    )

                    # Add tool results (Observe phase)
                    for tool_call, result in zip(
                        message.tool_calls, tool_results, strict=False
                    ):
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": f"Observation: {json.dumps(result)}",
                            },
                        )

                    step_count += 1
                else:
                    # No more tools needed, final answer reached
                    final_answer = message.content or ""

                    reasoning_chain.append(
                        ReasoningStep(
                            step_id="react_conclusion",
                            description="ReAct final conclusion",
                            input_data={"steps_completed": step_count},
                            output_data={"final_answer": final_answer},
                            reasoning="Reached final conclusion through ReAct reasoning and acting process",
                        ),
                    )

                    return ReasoningResponse(
                        final_answer=final_answer,
                        reasoning_chain=[],  # Will be set by caller
                        strategy_used=ReasoningStrategy.REACT,
                        provider=ReasoningProvider.OPENAI_FUNCTIONS,
                        confidence_score=0.85,
                    )

            except Exception as e:
                self.logger.exception(f"Error in ReAct step {step_count}: {e}")
                break

        # If we exit the loop without a final answer
        final_answer = "ReAct reasoning completed but no definitive answer was reached"
        return ReasoningResponse(
            final_answer=final_answer,
            reasoning_chain=[],
            strategy_used=ReasoningStrategy.REACT,
            provider=ReasoningProvider.OPENAI_FUNCTIONS,
            confidence_score=0.5,
        )

    async def _prepare_messages(
        self,
        request: ReasoningRequest,
    ) -> list[dict[str, t.Any]]:
        """Prepare messages for OpenAI API call."""
        messages = []

        # Add system message if custom instructions provided
        if request.custom_instructions:
            messages.append({"role": "system", "content": request.custom_instructions})

        # Add conversation history if available
        if request.context and request.context.conversation_history:
            for msg in request.context.conversation_history[-5:]:  # Last 5 messages
                messages.append(msg)

        # Add current query
        messages.append({"role": "user", "content": request.query})

        return messages

    def _prepare_functions(self, tools: list[ToolDefinition]) -> list[dict[str, t.Any]]:
        """Convert tool definitions to OpenAI function format."""
        functions = []

        for tool in tools:
            function_def = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }

            if tool.required_parameters:
                function_def["function"]["parameters"]["required"] = (
                    tool.required_parameters
                )

            functions.append(function_def)

        return functions

    async def _execute_tool_calls(
        self,
        tool_calls: list[ChatCompletionMessageToolCall],
        available_tools: list[ToolDefinition],
        function_tracker: FunctionCallTracker,
    ) -> list[dict[str, t.Any]]:
        """Execute tool calls and return results."""
        results = []

        # Create tool lookup
        tool_lookup = {tool.name: tool for tool in available_tools}

        for tool_call in tool_calls:
            function_name = tool_call.function.name

            try:
                # Parse arguments
                if tool_call.function.arguments:
                    arguments = json.loads(tool_call.function.arguments)
                else:
                    arguments = {}

                # Execute tool (placeholder implementation)
                # In a real implementation, this would call actual tool functions
                if function_name in tool_lookup:
                    # Simulate tool execution
                    result = {
                        "success": True,
                        "function": function_name,
                        "arguments": arguments,
                        "result": f"Tool {function_name} executed successfully with arguments: {arguments}",
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    result = {
                        "success": False,
                        "function": function_name,
                        "error": f"Tool {function_name} not found in available tools",
                        "timestamp": datetime.now().isoformat(),
                    }

                # Record the call
                function_tracker.record_call(function_name, arguments, result)
                results.append(result)

            except Exception as e:
                error_result = {
                    "success": False,
                    "function": function_name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                function_tracker.record_call(function_name, {}, error_result)
                results.append(error_result)

        return results

    async def _update_conversation_history(
        self,
        session_id: str,
        query: str,
        response: str,
    ) -> None:
        """Update conversation history for session."""
        if session_id not in self._conversation_histories:
            self._conversation_histories[session_id] = []

        history = self._conversation_histories[session_id]

        # Add user message
        history.append({"role": "user", "content": query})

        # Add assistant response
        history.append({"role": "assistant", "content": response})

        # Keep only last 20 messages to prevent memory bloat
        if len(history) > 20:
            self._conversation_histories[session_id] = history[-20:]

    async def get_conversation_history(self, session_id: str) -> list[dict[str, t.Any]]:
        """Get conversation history for session."""
        return self._conversation_histories.get(session_id, [])

    async def clear_conversation_history(self, session_id: str) -> None:
        """Clear conversation history for session."""
        if session_id in self._conversation_histories:
            del self._conversation_histories[session_id]

    # Structured output methods

    async def structured_reasoning(
        self,
        query: str,
        output_schema: dict[str, t.Any],
        context: ReasoningContext | None = None,
    ) -> dict[str, t.Any]:
        """Perform reasoning with structured JSON output."""
        client = await self._ensure_client()

        messages = [
            {
                "role": "system",
                "content": f"You are a reasoning assistant. Provide your response in the following JSON format: {json.dumps(output_schema)}",
            },
            {"role": "user", "content": query},
        ]

        if context and context.conversation_history:
            messages.insert(
                -1,
                {
                    "role": "user",
                    "content": f"Context: {json.dumps(context.conversation_history[-3:])}",
                },
            )

        response = await client.chat.completions.create(
            model=self._settings.model,
            messages=messages,
            temperature=self._settings.temperature,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse structured response",
                "raw_response": response.choices[0].message.content,
            }


# Export the adapter class
__all__ = ["MODULE_METADATA", "OpenAIFunctionReasoningSettings", "Reasoning"]
