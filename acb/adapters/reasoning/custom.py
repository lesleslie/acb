"""Custom rule engine reasoning adapter for logic-based decision making."""

import re
import time
from enum import Enum

import typing as t
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
    from acb.logger import Logger as LoggerType
else:
    LoggerType: t.Any = t.Any  # type: ignore[assignment,no-redef]

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Custom Rule Engine Reasoning",
    category="reasoning",
    provider="custom",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Team",
    created_date=datetime.now().isoformat(),
    last_modified=datetime.now().isoformat(),
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.METRICS,
        AdapterCapability.LOGGING,
        AdapterCapability.CACHING,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=[],  # No external dependencies
    description="Custom rule engine for logic-based reasoning and decision trees with pure Python implementation",
    settings_class="CustomReasoningSettings",
    config_example={
        "enable_fuzzy_matching": True,
        "confidence_threshold": 0.8,
        "max_rule_depth": 10,
        "enable_explanation": True,
    },
)


class RuleOperator(str, Enum):
    """Supported rule operators."""

    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX_MATCH = "regex_match"
    IN = "in"
    NOT_IN = "not_in"
    AND = "and"
    OR = "or"
    NOT = "not"


class ActionType(str, Enum):
    """Types of actions that can be taken."""

    RETURN_VALUE = "return_value"
    SET_VARIABLE = "set_variable"
    CALL_FUNCTION = "call_function"
    TRIGGER_RULE = "trigger_rule"
    LOG_MESSAGE = "log_message"
    RAISE_ALERT = "raise_alert"


@dataclass
class RuleCondition:
    """Individual condition within a rule."""

    field: str
    operator: RuleOperator
    value: t.Any
    weight: float = 1.0


@dataclass
class RuleAction:
    """Action to be taken when rule is triggered."""

    action_type: ActionType
    parameters: dict[str, t.Any]
    confidence: float = 1.0


@dataclass
class EnhancedRule:
    """Enhanced rule with multiple conditions and actions."""

    name: str
    conditions: list[RuleCondition]
    actions: list[RuleAction]
    priority: int = 0
    description: str = ""
    metadata: dict[str, t.Any] | None = None
    enabled: bool = True


@dataclass
class RuleEvaluationResult:
    """Result of rule evaluation."""

    rule_name: str
    matched: bool
    confidence: float
    triggered_actions: list[RuleAction]
    explanation: str = ""
    execution_time_ms: float = 0.0


class CustomReasoningSettings(ReasoningBaseSettings):
    """Settings for custom rule engine reasoning adapter."""

    # Rule engine settings
    enable_fuzzy_matching: bool = True
    confidence_threshold: float = 0.8
    max_rule_depth: int = 10
    enable_explanation: bool = True

    # Performance settings
    rule_cache_size: int = 1000
    enable_rule_optimization: bool = True

    # Debugging settings
    debug_mode: bool = False
    log_rule_evaluations: bool = False

    # Advanced features
    enable_rule_learning: bool = False
    learning_threshold: int = 100


class RuleEngine:
    """Core rule engine for evaluating complex rules."""

    def __init__(self, settings: CustomReasoningSettings, logger: t.Any) -> None:
        self.settings = settings
        self.logger = logger
        self.rules: dict[str, EnhancedRule] = {}
        self.rule_cache: dict[str, RuleEvaluationResult] = {}
        self.execution_stats: dict[str, list[float]] = {}

    def add_rule(self, rule: EnhancedRule) -> None:
        """Add a rule to the engine."""
        self.rules[rule.name] = rule
        self.logger.debug(f"Added rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> None:
        """Remove a rule from the engine."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            self.logger.debug(f"Removed rule: {rule_name}")

    def _check_evaluation_cache(
        self,
        rule: EnhancedRule,
        data: dict[str, t.Any],
    ) -> RuleEvaluationResult | None:
        """Check cache for existing evaluation result."""
        cache_key = f"{rule.name}_{hash(str(sorted(data.items())))}"
        cached_result = self.rule_cache.get(cache_key)

        if cached_result and self.settings.log_rule_evaluations:
            self.logger.debug(
                f"Rule {rule.name} returned cached result: {cached_result.matched}",
            )

        return cached_result

    def _evaluate_conditions(
        self,
        rule: EnhancedRule,
        data: dict[str, t.Any],
    ) -> tuple[list[tuple[bool, float]], list[str]]:
        """Evaluate all conditions and collect results with explanations."""
        condition_results: list[tuple[bool, float]] = []
        explanations: list[str] = []

        for condition in rule.conditions:
            result, explanation = self._evaluate_condition(condition, data)
            condition_results.append((result, condition.weight))
            explanations.append(
                f"  {condition.field} {condition.operator.value} {condition.value}: {result}",
            )

            if self.settings.debug_mode:
                self.logger.debug(f"Condition evaluation: {explanation}")

        return condition_results, explanations

    def _calculate_weighted_confidence(
        self,
        condition_results: list[tuple[bool, float]],
    ) -> tuple[float, bool]:
        """Calculate weighted confidence score and match status."""
        if not condition_results:
            return 0.0, False

        weighted_sum = sum(result * weight for result, weight in condition_results)
        total_weight = sum(weight for _, weight in condition_results)
        # Type guard: Ensure total_weight is non-zero before division
        confidence: float = (weighted_sum / total_weight) if total_weight > 0.0 else 0.0  # type: ignore[misc]
        matched = confidence >= self.settings.confidence_threshold

        return confidence, matched

    def _store_evaluation_result(
        self,
        rule: EnhancedRule,
        data: dict[str, t.Any],
        result: RuleEvaluationResult,
    ) -> None:
        """Store evaluation result in cache and update statistics."""
        # Cache result
        if len(self.rule_cache) < self.settings.rule_cache_size:
            cache_key = f"{rule.name}_{hash(str(sorted(data.items())))}"
            self.rule_cache[cache_key] = result

        # Update stats
        if rule.name not in self.execution_stats:
            self.execution_stats[rule.name] = []
        self.execution_stats[rule.name].append(result.execution_time_ms)

        if self.settings.log_rule_evaluations:
            self.logger.debug(
                f"Rule {rule.name} evaluation: {result.matched} (confidence: {result.confidence:.2f})",
            )

    def evaluate_rule(
        self,
        rule: EnhancedRule,
        data: dict[str, t.Any],
    ) -> RuleEvaluationResult:
        """Evaluate a single rule against data."""
        start_time = time.time()

        try:
            # Check cache first
            cached_result = self._check_evaluation_cache(rule, data)
            if cached_result:
                return cached_result

            if not rule.enabled:
                return RuleEvaluationResult(
                    rule_name=rule.name,
                    matched=False,
                    confidence=0.0,
                    triggered_actions=[],
                    explanation="Rule is disabled",
                )

            # Evaluate all conditions
            condition_results, explanations = self._evaluate_conditions(rule, data)

            # Calculate overall confidence
            confidence, matched = self._calculate_weighted_confidence(condition_results)

            # Determine triggered actions
            triggered_actions = rule.actions if matched else []

            # Create explanation
            explanation = f"Rule '{rule.name}' evaluation:\n" + "\n".join(explanations)
            explanation += f"\nOverall confidence: {confidence:.2f}, Matched: {matched}"

            result = RuleEvaluationResult(
                rule_name=rule.name,
                matched=matched,
                confidence=confidence,
                triggered_actions=triggered_actions,
                explanation=explanation,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

            # Store result in cache and stats
            self._store_evaluation_result(rule, data, result)

            return result

        except Exception as e:
            self.logger.exception(f"Error evaluating rule {rule.name}: {e}")
            return RuleEvaluationResult(
                rule_name=rule.name,
                matched=False,
                confidence=0.0,
                triggered_actions=[],
                explanation=f"Error: {e!s}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _evaluate_condition(
        self,
        condition: RuleCondition,
        data: dict[str, t.Any],
    ) -> tuple[bool, str]:
        """Evaluate a single condition."""
        field_value = self._get_field_value(condition.field, data)

        try:
            result = self._apply_operator(condition, field_value)
            explanation = f"{condition.field}({field_value}) {condition.operator.value} {condition.value} = {result}"
            return result, explanation

        except Exception as e:
            explanation = f"Error evaluating {condition.field}: {e}"
            return False, explanation

    def _apply_operator(self, condition: RuleCondition, field_value: t.Any) -> bool:
        """Apply the operator specified in the condition to the field value."""
        if condition.operator == RuleOperator.EQUALS:
            return self._eval_equals(field_value, condition.value)
        elif condition.operator == RuleOperator.NOT_EQUALS:
            return self._eval_not_equals(field_value, condition.value)
        elif condition.operator == RuleOperator.GREATER_THAN:
            return self._eval_greater_than(field_value, condition.value)
        elif condition.operator == RuleOperator.LESS_THAN:
            return self._eval_less_than(field_value, condition.value)
        elif condition.operator == RuleOperator.GREATER_EQUAL:
            return self._eval_greater_equal(field_value, condition.value)
        elif condition.operator == RuleOperator.LESS_EQUAL:
            return self._eval_less_equal(field_value, condition.value)
        elif condition.operator == RuleOperator.CONTAINS:
            return self._eval_contains(field_value, condition.value)
        elif condition.operator == RuleOperator.NOT_CONTAINS:
            return self._eval_not_contains(field_value, condition.value)
        elif condition.operator == RuleOperator.STARTS_WITH:
            return self._eval_starts_with(field_value, condition.value)
        elif condition.operator == RuleOperator.ENDS_WITH:
            return self._eval_ends_with(field_value, condition.value)
        elif condition.operator == RuleOperator.REGEX_MATCH:
            return self._eval_regex_match(field_value, condition.value)
        elif condition.operator == RuleOperator.IN:
            return self._eval_in(field_value, condition.value)
        elif condition.operator == RuleOperator.NOT_IN:
            return self._eval_not_in(field_value, condition.value)
        else:
            return False

    def _eval_equals(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return field_value == condition_value

    def _eval_not_equals(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return field_value != condition_value

    def _eval_greater_than(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return float(field_value) > float(condition_value)

    def _eval_less_than(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return float(field_value) < float(condition_value)

    def _eval_greater_equal(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return float(field_value) >= float(condition_value)

    def _eval_less_equal(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return float(field_value) <= float(condition_value)

    def _eval_contains(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return str(condition_value).lower() in str(field_value).lower()

    def _eval_not_contains(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return str(condition_value).lower() not in str(field_value).lower()

    def _eval_starts_with(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return str(field_value).lower().startswith(str(condition_value).lower())

    def _eval_ends_with(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return str(field_value).lower().endswith(str(condition_value).lower())

    def _eval_regex_match(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return bool(
            re.search(str(condition_value), str(field_value)),
        )  # REGEX OK: rule condition evaluation

    def _eval_in(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return field_value in condition_value

    def _eval_not_in(self, field_value: t.Any, condition_value: t.Any) -> bool:
        return field_value not in condition_value

    def _get_field_value(self, field_path: str, data: dict[str, t.Any]) -> t.Any:
        """Get field value supporting dot notation for nested fields."""
        try:
            value = data
            for key in field_path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)  # type: ignore[assignment]
                elif hasattr(value, key):
                    value = getattr(value, key)
                else:
                    return None
            return value
        except Exception:
            return None

    def evaluate_all_rules(self, data: dict[str, t.Any]) -> list[RuleEvaluationResult]:
        """Evaluate all rules against data."""
        results = []

        # Sort rules by priority (highest first)
        sorted_rules = sorted(
            self.rules.values(),
            key=lambda r: r.priority,
            reverse=True,
        )

        for rule in sorted_rules:
            result = self.evaluate_rule(rule, data)
            results.append(result)

        return results

    def get_rule_statistics(self) -> dict[str, t.Any]:
        """Get execution statistics for all rules."""
        stats = {}
        for rule_name, times in self.execution_stats.items():
            if times:
                stats[rule_name] = {
                    "total_executions": len(times),
                    "avg_time_ms": sum(times) / len(times),
                    "max_time_ms": max(times),
                    "min_time_ms": min(times),
                }
        return stats


class Reasoning(ReasoningBase):
    """Custom rule engine reasoning adapter."""

    def __init__(
        self,
        settings: CustomReasoningSettings | None = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings or CustomReasoningSettings()
        self._rule_engine = RuleEngine(self._settings, self.logger)
        self._workflow_cache: dict[str, list[ReasoningStep]] = {}

    async def _create_client(self) -> RuleEngine:
        """Create rule engine client."""
        return self._rule_engine

    async def _reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Perform reasoning using custom rule engine."""
        start_time = time.time()
        reasoning_chain: list[Any] = []

        try:
            engine = await self._ensure_client()

            if request.strategy == ReasoningStrategy.RULE_BASED:
                response = await self._rule_based_reasoning(
                    request,
                    engine,
                    reasoning_chain,
                )
            elif request.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT:
                response = await self._chain_of_thought_reasoning(
                    request,
                    engine,
                    reasoning_chain,
                )
            else:
                # Default to rule-based reasoning
                response = await self._rule_based_reasoning(
                    request,
                    engine,
                    reasoning_chain,
                )

            # Calculate metrics
            total_duration = int((time.time() - start_time) * 1000)
            response.total_duration_ms = total_duration
            response.reasoning_chain.extend(reasoning_chain)

            if not response.confidence_score:
                response.confidence_score = await calculate_confidence_score(
                    response.reasoning_chain,
                )

            return response

        except Exception as e:
            if self.logger is not None:
                self.logger.exception(f"Custom reasoning failed: {e}")
            return ReasoningResponse(
                final_answer="",
                reasoning_chain=reasoning_chain,
                strategy_used=request.strategy,
                provider=ReasoningProvider.CUSTOM,
                total_duration_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )

    async def _rule_based_reasoning(
        self,
        request: ReasoningRequest,
        engine: RuleEngine,
        reasoning_chain: list[ReasoningStep],
    ) -> ReasoningResponse:
        """Perform rule-based reasoning."""
        # Extract data from query and context
        input_data = await self._extract_input_data(request)

        # Add reasoning step for data extraction
        reasoning_chain.append(
            ReasoningStep(
                step_id="data_extraction",
                description="Extract input data for rule evaluation",
                input_data={"query": request.query},
                output_data={"extracted_data": input_data},
                reasoning="Parsed query and context to extract structured data for rule evaluation",
            ),
        )

        # Evaluate all rules
        rule_results = engine.evaluate_all_rules(input_data)

        # Add reasoning step for rule evaluation
        reasoning_chain.append(
            ReasoningStep(
                step_id="rule_evaluation",
                description="Evaluate rules against input data",
                input_data=input_data,
                output_data={
                    "evaluated_rules": len(rule_results),
                    "matched_rules": [r.rule_name for r in rule_results if r.matched],
                },
                reasoning=f"Evaluated {len(rule_results)} rules, {len([r for r in rule_results if r.matched])} matched",
            ),
        )

        # Find best matching rule
        matched_rules = [r for r in rule_results if r.matched]
        if matched_rules:
            best_rule = max(matched_rules, key=lambda r: r.confidence)

            # Execute actions
            action_results = await self._execute_actions(
                best_rule.triggered_actions,
                input_data,
            )

            reasoning_chain.append(
                ReasoningStep(
                    step_id="action_execution",
                    description=f"Execute actions for rule: {best_rule.rule_name}",
                    input_data={
                        "rule": best_rule.rule_name,
                        "actions": len(best_rule.triggered_actions),
                    },
                    output_data=action_results,
                    reasoning=f"Executed {len(best_rule.triggered_actions)} actions from best matching rule",
                    confidence=best_rule.confidence,
                ),
            )

            final_answer = action_results.get(
                "final_result",
                f"Rule '{best_rule.rule_name}' matched",
            )
            confidence = best_rule.confidence

            # Include explanation if enabled
            settings = self._settings
            if settings and getattr(settings, "enable_explanation", False):
                final_answer += f"\n\nExplanation:\n{best_rule.explanation}"
        else:
            final_answer = "No matching rules found for the given input"
            confidence = 0.0

            reasoning_chain.append(
                ReasoningStep(
                    step_id="no_match",
                    description="No rules matched the input data",
                    input_data=input_data,
                    output_data={"matched_rules": 0},
                    reasoning="No rules met the confidence threshold for the given input",
                    confidence=0.0,
                ),
            )

        return ReasoningResponse(
            final_answer=final_answer,
            reasoning_chain=[],  # Will be set by caller
            strategy_used=ReasoningStrategy.RULE_BASED,
            provider=ReasoningProvider.CUSTOM,
            confidence_score=confidence,
        )

    async def _chain_of_thought_reasoning(
        self,
        request: ReasoningRequest,
        engine: RuleEngine,
        reasoning_chain: list[ReasoningStep],
    ) -> ReasoningResponse:
        """Perform chain-of-thought reasoning using rules."""
        # Break down the query into steps
        steps = await self._decompose_query(request.query)

        reasoning_chain.append(
            ReasoningStep(
                step_id="query_decomposition",
                description="Decompose query into reasoning steps",
                input_data={"query": request.query},
                output_data={"steps": steps},
                reasoning=f"Broke down complex query into {len(steps)} manageable steps",
            ),
        )

        final_answer = ""
        overall_confidence = 0.0

        # Process each step
        for i, step in enumerate(steps):
            step_input = await self._extract_input_data_from_text(step)

            # Evaluate rules for this step
            rule_results = engine.evaluate_all_rules(step_input)
            matched_rules = [r for r in rule_results if r.matched]

            if matched_rules:
                best_rule = max(matched_rules, key=lambda r: r.confidence)
                action_results = await self._execute_actions(
                    best_rule.triggered_actions,
                    step_input,
                )
                step_result = action_results.get(
                    "final_result",
                    f"Step {i + 1} completed",
                )
                step_confidence = best_rule.confidence
            else:
                step_result = f"Step {i + 1}: No applicable rules found"
                step_confidence = 0.0

            reasoning_chain.append(
                ReasoningStep(
                    step_id=f"step_{i + 1}",
                    description=f"Process step {i + 1}: {step}",
                    input_data={"step_text": step, "step_data": step_input},
                    output_data={"result": step_result},
                    reasoning=f"Applied rule-based reasoning to step {i + 1}",
                    confidence=step_confidence,
                ),
            )

            final_answer += f"Step {i + 1}: {step_result}\n"
            overall_confidence += step_confidence

        # Calculate average confidence
        overall_confidence = overall_confidence / len(steps) if steps else 0.0

        reasoning_chain.append(
            ReasoningStep(
                step_id="synthesis",
                description="Synthesize results from all steps",
                input_data={"steps_completed": len(steps)},
                output_data={"final_answer": final_answer},
                reasoning="Combined results from all reasoning steps into final answer",
                confidence=overall_confidence,
            ),
        )

        return ReasoningResponse(
            final_answer=final_answer.strip(),
            reasoning_chain=[],  # Will be set by caller
            strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT,
            provider=ReasoningProvider.CUSTOM,
            confidence_score=overall_confidence,
        )

    async def _extract_input_data(self, request: ReasoningRequest) -> dict[str, Any]:
        """Extract structured data from reasoning request."""
        data: dict[str, Any] = {
            "query": request.query,
            "query_length": len(request.query),
            "has_context": request.context is not None,
            "max_steps": request.max_steps,
            "temperature": request.temperature,
        }

        if request.context:
            context_data = {
                "session_id": request.context.session_id,
                "user_id": request.context.user_id,
                "has_conversation_history": bool(
                    request.context.conversation_history,
                ),
                "has_knowledge_base": bool(request.context.knowledge_base),
                "has_retrieved_contexts": bool(request.context.retrieved_contexts),
            }
            data.update(context_data)

        # Try to extract entities from query
        data.update(await self._extract_entities_from_text(request.query))

        return data

    async def _extract_input_data_from_text(self, text: str) -> dict[str, t.Any]:
        """Extract structured data from text."""
        data = {
            "text": text,
            "text_length": len(text),
            "word_count": len(text.split()),
        }

        # Add extracted entities
        data.update(await self._extract_entities_from_text(text))

        return data

    async def _extract_entities_from_text(self, text: str) -> dict[str, Any]:
        """Extract entities from text using simple patterns."""
        entities: dict[str, Any] = {}

        # Extract numbers
        numbers = re.findall(
            r"\b\d+(?:\.\d+)?\b",
            text,
        )  # REGEX OK: number extraction for entity parsing
        if numbers:
            entities["numbers"] = [float(n) for n in numbers]
            entities["has_numbers"] = True
        else:
            entities["has_numbers"] = False

        # Extract URLs
        urls = re.findall(  # REGEX OK: URL extraction for entity parsing
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            text,
        )
        entities["urls"] = urls
        entities["has_urls"] = bool(urls)

        # Extract email addresses
        emails = re.findall(  # REGEX OK: email extraction for entity parsing
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            text,
        )
        entities["emails"] = emails
        entities["has_emails"] = bool(emails)

        # Extract question indicators
        entities["is_question"] = "?" in text or any(
            text.lower().startswith(q)
            for q in ("what", "how", "why", "when", "where", "who", "which")
        )

        # Extract sentiment indicators (simple)
        positive_words = [
            "good",
            "great",
            "excellent",
            "amazing",
            "wonderful",
            "fantastic",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "horrible",
            "disappointing",
            "poor",
        ]

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        entities["sentiment_positive"] = positive_count
        entities["sentiment_negative"] = negative_count
        entities["sentiment_neutral"] = positive_count == negative_count

        return entities

    async def _decompose_query(self, query: str) -> list[str]:
        """Decompose a complex query into reasoning steps."""
        # Simple heuristic-based decomposition
        steps = []

        # Split on common conjunctions
        parts = re.split(  # REGEX OK: query decomposition for reasoning steps
            r"\b(?:and|then|after|next|also|furthermore|moreover)\b",
            query,
            flags=re.IGNORECASE,
        )

        for part in parts:
            part = part.strip()
            if part:
                steps.append(part)

        # If no splitting occurred, create default steps
        if len(steps) <= 1:
            steps = [
                f"Understand the question: {query}",
                f"Identify key information in: {query}",
                f"Apply relevant rules to: {query}",
                f"Synthesize final answer for: {query}",
            ]

        return steps

    async def _execute_actions(
        self,
        actions: list[RuleAction],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute rule actions."""
        results: dict[str, Any] = {"executed_actions": [], "final_result": ""}
        executed: list[str] = []

        def _log_info(message: str) -> None:
            if self.logger is not None:
                self.logger.info(message)

        def _log_warning(message: str) -> None:
            if self.logger is not None:
                self.logger.warning(message)

        def _handle_return_value(action: RuleAction) -> str:
            value = action.parameters.get("value", "")
            results["final_result"] = str(value)
            return f"Returned value: {value}"

        def _handle_set_variable(action: RuleAction) -> str:
            var_name = action.parameters.get("variable")
            var_value = action.parameters.get("value")
            if var_name is not None:
                data[var_name] = var_value
            return f"Set {var_name} = {var_value}"

        def _handle_log_message(action: RuleAction) -> str:
            message = action.parameters.get("message", "")
            _log_info(f"Rule action log: {message}")
            return f"Logged: {message}"

        def _handle_raise_alert(action: RuleAction) -> str:
            alert_message = action.parameters.get("message", "Alert triggered")
            _log_warning(f"Rule alert: {alert_message}")
            return f"Alert: {alert_message}"

        handlers = {
            ActionType.RETURN_VALUE: _handle_return_value,
            ActionType.SET_VARIABLE: _handle_set_variable,
            ActionType.LOG_MESSAGE: _handle_log_message,
            ActionType.RAISE_ALERT: _handle_raise_alert,
        }

        for action in actions:
            handler = handlers.get(action.action_type)
            try:
                if handler is None:
                    executed.append(f"Unknown action type: {action.action_type}")
                else:
                    executed.append(handler(action))
            except Exception as e:
                if self.logger is not None:
                    self.logger.exception(
                        f"Error executing action {action.action_type}: {e}",
                    )
                executed.append(f"Error in {action.action_type}: {e}")

        results["executed_actions"] = executed
        return results

    # Additional methods for rule management

    async def add_rule(
        self,
        name: str,
        conditions: list[dict[str, t.Any]],
        actions: list[dict[str, t.Any]],
        priority: int = 0,
        description: str = "",
    ) -> None:
        """Add a new rule to the engine."""
        # Convert dictionaries to typed objects
        typed_conditions = [
            RuleCondition(
                field=c["field"],
                operator=RuleOperator(c["operator"]),
                value=c["value"],
                weight=c.get("weight", 1.0),
            )
            for c in conditions
        ]

        typed_actions = [
            RuleAction(
                action_type=ActionType(a["action_type"]),
                parameters=a["parameters"],
                confidence=a.get("confidence", 1.0),
            )
            for a in actions
        ]

        rule = EnhancedRule(
            name=name,
            conditions=typed_conditions,
            actions=typed_actions,
            priority=priority,
            description=description,
        )

        engine = await self._ensure_client()
        engine.add_rule(rule)

    async def remove_rule(self, rule_name: str) -> None:
        """Remove a rule from the engine."""
        engine = await self._ensure_client()
        engine.remove_rule(rule_name)

    async def get_rule_statistics(self) -> dict[str, Any]:
        """Get execution statistics for all rules."""
        engine = await self._ensure_client()
        stats = engine.get_rule_statistics()
        return dict(stats)


ReasoningSettings = CustomReasoningSettings

depends.set(Reasoning, "custom")

# Export the adapter class
__all__ = [
    "MODULE_METADATA",
    "CustomReasoningSettings",
    "Reasoning",
    "ReasoningSettings",
]
