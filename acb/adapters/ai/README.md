> **ACB Documentation**: [Main](<../../../README.md>) | [Core Systems](<../../README.md>) | [Actions](<../../actions/README.md>) | [Adapters](<../README.md>) | [AI](<./README.md>)

# AI Adapter

The AI adapter unifies access to hosted, edge, and hybrid AI models inside ACB.
It wraps prompt orchestration, streaming responses, usage accounting, and
provider selection behind a consistent interface so that business logic stays
portable across vendors and deployment topologies.

## Table of Contents

- [Overview](<#overview>)
- [Core Components](<#core-components>)
- [Deployment Strategies](<#deployment-strategies>)
- [Requests, Responses, and Streaming](<#requests-responses-and-streaming>)
- [Settings & Configuration](<#settings--configuration>)
- [Built-in Implementations](<#built-in-implementations>)
- [Usage Examples](<#usage-examples>)
- [Hybrid Routing Example](<#hybrid-routing-example>)
- [Best Practices](<#best-practices>)
- [Related Adapters](<#related-adapters>)

## Installation

```bash
# Install with AI support
uv add --group ai

# Or include it with other dependencies
uv add --group ai --group cache --group embedding
```

## Overview

The adapter exposes the `AIBase` interface with helpers for token estimation,
cost tracking, function calling, and prompt templating. Dependency injection is
used to assemble provider-specific clients at runtime while keeping TLS,
credential loading, and metrics consistent with the rest of the framework.

## Core Components

- `ModelCapability` and `ModelProvider` enumerate supported model behaviors and
  vendors (OpenAI, Anthropic, Bedrock, Vertex, Hugging Face, Ollama, and more).
- `ModelInfo` describes context length, memory footprint, latency targets, and
  streaming support so schedulers can pick the right model automatically.
- `AIRequest` holds prompts, multimodal payloads, function definitions, and
  routing hints (quality, latency, memory budgets).
- `AIResponse` returns chosen model metadata, tokens consumed, function call
  payloads, and cost calculations.
- `PromptTemplate` standardizes reusable prompt fragments with versioning and
  required variables.

## Deployment Strategies

`DeploymentStrategy` coordinates how work is routed:

- `CLOUD`: Fully hosted APIs such as OpenAI, Anthropic, Vertex AI.
- `EDGE`: On-device or on-premise runtimes tuned for low latency or data
  residency (Ollama, Liquid AI edge builds).
- `HYBRID`: Mixes both, falling back based on latency, quality, or budget.

Hybrid deployments can specify a preferred strategy per request while allowing
automatic fallback if constraints are violated.

## Requests, Responses, and Streaming

- Streaming responses are surfaced via `StreamingResponse`, an async iterator
  that accumulates the final text while yielding chunks in real time.
- `estimate_tokens()` and `calculate_cost()` make it easy to enforce quotas
  before dispatching a request.
- `validate_request()` ensures prompts and function definitions meet provider
  constraints before the network call happens.

## Settings & Configuration

`AIBaseSettings` centralizes runtime knobs:

- Model defaults (`default_model`, `max_tokens`, `temperature`) and hybrid
  routing constraints (`max_latency_ms`, `min_quality_score`).
- Credential management (`api_key`, `base_url`, `organization`, `api_version`)
  with TLS ready via `SSLConfigMixin`.
- Connection pooling, retries, and timeout controls aligned with adapter
  conventions.

Configuration is usually sourced from `settings/adapters.yaml` and injected via
`depends.get()` or service constructors.

Example configuration:

```yaml
# settings/adapters.yaml
ai: cloud  # Options: cloud, edge, hybrid

# Optional: Provider-specific settings
# settings/ai.yaml (if needed)
ai:
  default_model: "gpt-4"
  max_tokens: 4096
  temperature: 0.7
  api_key: "${AI_API_KEY}"  # Use environment variable
  deployment_strategy: "CLOUD"  # or "EDGE" or "HYBRID"
```

## Built-in Implementations

| Module | Description | Ideal Use Cases |
| ------ | ----------- | --------------- |
| `cloud` | Connects to hosted APIs (OpenAI, Anthropic, Bedrock, Vertex). | Production-grade scalability, turnkey compliance. |
| `edge` | Serves local/edge runtimes (Ollama, Liquid AI edge). | Low latency, air-gapped deployments, data sovereignty. |
| `hybrid` | Routes between cloud and edge based on policy. | Cost/performance balancing, progressive rollout strategies. |

Each implementation inherits `AIBase` so switching providers requires only
configuration changes.

## Usage Examples

```python
from acb.adapters import import_adapter
from acb.adapters.ai import AIRequest
from acb.depends import depends

AI = import_adapter("ai")


async def summarize() -> None:
    ai_client = await depends.get(AI)
    request = AIRequest(
        prompt="Summarize the deployment checklist.",
        model="gpt-4",
        temperature=0.2,
        stream=True,
    )
    response = await ai_client.generate(request)
    print(response.content)
```

To stream results:

```python
async def stream_summary() -> None:
    ai_client = await depends.get(AI)
    request = AIRequest(prompt="Stream the highlights.", stream=True)
    async with ai_client.stream(request) as stream:
        async for chunk in stream:
            print(chunk, end="", flush=True)
```

## Hybrid Routing Example

```python
from acb.adapters.ai import DeploymentStrategy


async def route_with_constraints(prompt: str) -> str:
    ai_client = await depends.get(AI)
    request = AIRequest(
        prompt=prompt,
        preferred_strategy=DeploymentStrategy.EDGE,
        max_latency_ms=1500,
        min_quality_score=0.85,
    )
    response = await ai_client.generate(request)
    return response.content
```

In this example the adapter attempts to satisfy the request on an edge runtime,
falling back to cloud providers if latency or quality thresholds cannot be met.

## Best Practices

- Prefer prompt templates for multi-team reuse and version control.
- Set `preferred_strategy` when compliance or latency constraints must be
  respected; allow fallback for resilience when possible.
- Capture `tokens_used` and `cost` to feed billing dashboards or guardrails.
- Use structured logging for request/response metadata while filtering prompts
  to avoid leaking sensitive context.
- When running at the edge, enable model caching and prefetching to minimize
  cold starts.

## Related Adapters

- [Embedding](<../embedding/README.md>)
- [Reasoning](<../reasoning/README.md>)
- [Vector](<../vector/README.md>)
