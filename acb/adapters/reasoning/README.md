# Reasoning Adapters

The `acb.adapters.reasoning` module provides a unified interface for integrating various AI/ML reasoning frameworks and custom logic engines into your ACB application. These adapters enable your application to perform complex decision-making, problem-solving, and knowledge retrieval tasks using different strategies and providers.

## Core Concepts

### Reasoning Strategies

Reasoning adapters support various strategies to tackle different types of problems:

- **`CHAIN_OF_THOUGHT`**: Step-by-step reasoning to break down complex problems.
- **`TREE_OF_THOUGHTS`**: Explores multiple reasoning paths in parallel to find the best solution.
- **`REACT`**: Combines reasoning with acting (tool usage) to solve problems.
- **`SELF_REFLECTION`**: Allows the reasoning process to evaluate and refine its own steps.
- **`RULE_BASED`**: Executes predefined rules and decision trees.
- **`RAG_WORKFLOW`**: Retrieval-Augmented Generation, integrating external knowledge bases.
- **`FUNCTION_CALLING`**: Utilizes AI models capable of calling external functions/tools.
- **`MULTI_AGENT`**: Orchestrates multiple AI agents to collaborate on a task.

### Reasoning Providers

The module supports different underlying AI/ML frameworks as providers:

- **`LANGCHAIN`**: Leverages the LangChain framework for advanced LLM orchestration.
- **`LLAMAINDEX`**: Focuses on RAG workflows and knowledge base interactions.
- **`CUSTOM`**: A pure Python rule engine for logic-based decision making.
- **`OPENAI_FUNCTIONS`**: Utilizes OpenAI's function calling capabilities for structured interactions.

### Reasoning Capabilities

Adapters declare their supported capabilities, such as:

- `CHAIN_REASONING`, `RAG_WORKFLOWS`, `RULE_ENGINE`, `TOOL_CALLING`, `MEMORY_MANAGEMENT`, `AGENT_WORKFLOWS`, `SELF_REFLECTION`, `PARALLEL_REASONING`, `CONTEXT_PRESERVATION`, `CITATION_TRACKING`.

### Data Structures

- **`ReasoningRequest`**: Encapsulates the input for a reasoning operation, including the query, strategy, context, tools, and various parameters.
- **`ReasoningResponse`**: Contains the output of a reasoning operation, including the final answer, the reasoning chain (steps taken), strategy used, provider, confidence score, and any errors.
- **`ReasoningContext`**: Provides contextual information for a reasoning session, such as session ID, user ID, conversation history, and knowledge base.
- **`ReasoningStep`**: Represents an individual step within a reasoning chain, detailing the input, output, reasoning, confidence, and tools used.
- **`ToolDefinition`**: Describes an external tool or function that the reasoning adapter can call, including its name, description, and parameters.
- **`RAGConfig`**: Configuration specific to Retrieval-Augmented Generation workflows.
- **`ChainConfig`**: Configuration specific to reasoning chains.
- **`DecisionRule` / `DecisionTree`**: Structures for defining and evaluating rule-based logic.

## Base Reasoning Adapter (`ReasoningBase`)

All concrete reasoning adapters inherit from `ReasoningBase`, which provides a common interface and shared functionalities:

- **`reason(request: ReasoningRequest) -> ReasoningResponse`**: The primary method to initiate a reasoning operation.
- **Strategy-specific methods**: `chain_of_thought`, `tree_of_thoughts`, `react_reasoning`, `rag_workflow`, `evaluate_decision_tree`.
- **Tool and Decision Tree Management**: Methods to `register_tool` and `register_decision_tree`.
- **Memory Management**: Methods like `get_memory`, `set_memory`, `clear_memory`.
- **Health Check**: `health_check()` to verify adapter status.
- **Abstract methods**: Concrete adapters must implement `_reason`, `_create_client`, and can override default implementations for strategies like `_tree_of_thoughts`, `_react_reasoning`, `_rag_workflow`, `_evaluate_decision_tree`.

## Reasoning Settings (`ReasoningBaseSettings`)

The `ReasoningBaseSettings` class provides common configuration options for all reasoning adapters, such as:

- `provider`, `api_key`, `base_url`, `model`
- `default_strategy`, `max_reasoning_steps`, `max_tokens`, `temperature`
- `enable_reflection`, `enable_memory`
- `timeout_seconds`, `max_concurrent_operations`, `enable_caching`, `cache_ttl`
- `rag_config`, `chain_config`, `memory_types`, `memory_persistence`, `memory_ttl`
- `enable_tool_calling`, `max_tool_calls_per_step`, `tool_timeout_seconds`
- Integration settings for other adapters: `ai_adapter_name`, `embedding_adapter_name`, `vector_adapter_name`.
- SSL configuration via `SSLConfigMixin`.

Each concrete adapter may extend `ReasoningBaseSettings` with its own specific settings.

## Available Reasoning Adapter Implementations

### Custom Rule Engine Reasoning (`acb.adapters.reasoning.custom`)

- **Provider**: `custom`
- **Description**: A pure Python rule engine for logic-based decision making. It allows defining rules with conditions and actions, supporting various operators and nested field evaluation.
- **Strengths**: Lightweight, no external dependencies, highly customizable for specific business logic.
- **Key Settings (`CustomReasoningSettings`)**: `enable_fuzzy_matching`, `confidence_threshold`, `max_rule_depth`, `enable_explanation`, `rule_cache_size`.
- **Installation**: No external packages required.

### LangChain Reasoning (`acb.adapters.reasoning.langchain`)

- **Provider**: `langchain`
- **Description**: Integrates the powerful LangChain framework for advanced LLM orchestration, supporting agents, chains, and memory management.
- **Strengths**: Flexible, extensive ecosystem, good for complex multi-step reasoning and agentic workflows.
- **Key Settings (`LangChainReasoningSettings`)**: `agent_type`, `memory_type`, `max_memory_tokens`, `verbose`, `chain_type`, `prompt_template`, `tool_return_direct`, `enable_streaming`.
- **Installation**: `uv add acb --group reasoning`.

### LlamaIndex Reasoning (`acb.adapters.reasoning.llamaindex`)

- **Provider**: `llamaindex`
- **Description**: Focuses on Retrieval-Augmented Generation (RAG) workflows, enabling efficient interaction with knowledge bases and document indexing.
- **Strengths**: Excellent for querying large datasets, context retrieval, and citation tracking.
- **Key Settings (`LlamaIndexReasoningSettings`)**: `chunk_size`, `chunk_overlap`, `similarity_top_k`, `response_mode`, `streaming`, `chat_memory_token_limit`, `max_function_calls`, `enable_citation_tracking`, `persist_index`.
- **Installation**: `uv add acb --group reasoning`.

### OpenAI Function Calling Reasoning (`acb.adapters.reasoning.openai_functions`)

- **Provider**: `openai_functions`
- **Description**: Leverages OpenAI's native function calling capabilities for structured reasoning, tool integration, and precise output control.
- **Strengths**: Direct integration with OpenAI models, robust tool execution, structured JSON output.
- **Key Settings (`OpenAIFunctionReasoningSettings`)**: `max_function_calls`, `function_call_strategy`, `enable_parallel_calls`, `response_format`, `presence_penalty`, `frequency_penalty`, `top_p`, `max_retries`.
- **Installation**: `uv add acb --group reasoning`.

## Usage

To use a reasoning adapter, you typically:

1. **Configure the adapter**: Specify the desired provider and its settings in your application's configuration (e.g., `adapters.yaml`).
1. **Import the adapter**: Use `from acb.adapters import import_adapter` to get the adapter class.
1. **Get an instance**: Retrieve the adapter instance using `depends.get(AdapterClass)`.
1. **Make a reasoning request**: Call the `reason()` method with a `ReasoningRequest` object, or use one of the strategy-specific helper methods.

**Example (Conceptual):**

```python
import asyncio
from acb.adapters import import_adapter
from acb.adapters.reasoning._base import (
    ReasoningRequest,
    ReasoningStrategy,
    ReasoningContext,
)
from acb.depends import depends


async def main():
    # 1. Configure (e.g., in adapters.yaml or programmatically)
    #    reasoning:
    #      provider: langchain
    #      model: gpt-4
    #      api_key: YOUR_API_KEY

    # 2. Import the adapter class
    ReasoningAdapter = import_adapter("reasoning")

    # 3. Get an instance (dependency injected)
    reasoner = depends.get(ReasoningAdapter)

    # 4. Make a reasoning request
    request = ReasoningRequest(
        query="What is the capital of France and what is its population?",
        strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        context=ReasoningContext(session_id="user_123"),
        enable_memory=True,
    )

    response = await reasoner.reason(request)

    print(f"Final Answer: {response.final_answer}")
    print(f"Strategy Used: {response.strategy_used}")
    print(f"Confidence Score: {response.confidence_score}")
    for step in response.reasoning_chain:
        print(f"  Step {step.step_id}: {step.description} - {step.reasoning}")


if __name__ == "__main__":
    asyncio.run(main())
```
