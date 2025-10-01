"""Custom rule engine reasoning adapter for logic-based decision making."""

import re
import time
import typing as t
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

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
from acb.logger import Logger

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

    def __init__(self, settings: CustomReasoningSettings, logger: Logger) -> None:
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

    def evaluate_rule(
        self,
        rule: EnhancedRule,
        data: dict[str, t.Any],
    ) -> RuleEvaluationResult:
        """Evaluate a single rule against data."""
        start_time = time.time()

        try:
            # Check cache first
            cache_key = f"{rule.name}_{hash(str(sorted(data.items())))}"
            if cache_key in self.rule_cache:
                cached_result = self.rule_cache[cache_key]
                if self.settings.log_rule_evaluations:
                    self.logger.debug(
                        f"Rule {rule.name} returned cached result: {cached_result.matched}",
                    )
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
            condition_results = []
            explanations = []

            for condition in rule.conditions:
                result, explanation = self._evaluate_condition(condition, data)
                condition_results.append((result, condition.weight))
                explanations.append(
                    f"  {condition.field} {condition.operator.value} {condition.value}: {result}",
                )

                if self.settings.debug_mode:
                    self.logger.debug(f"Condition evaluation: {explanation}")

            # Calculate overall confidence
            if not condition_results:
                confidence = 0.0
                matched = False
            else:
                weighted_sum = sum(
                    result * weight for result, weight in condition_results
                )
                total_weight = sum(weight for _, weight in condition_results)
                confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
                matched = confidence >= self.settings.confidence_threshold

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

            # Cache result
            if len(self.rule_cache) < self.settings.rule_cache_size:
                self.rule_cache[cache_key] = result

            # Update stats
            if rule.name not in self.execution_stats:
                self.execution_stats[rule.name] = []
            self.execution_stats[rule.name].append(result.execution_time_ms)

            if self.settings.log_rule_evaluations:
                self.logger.debug(
                    f"Rule {rule.name} evaluation: {matched} (confidence: {confidence:.2f})",
                )

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
            if condition.operator == RuleOperator.EQUALS:
                result = field_value == condition.value
            elif condition.operator == RuleOperator.NOT_EQUALS:
                result = field_value != condition.value
            elif condition.operator == RuleOperator.GREATER_THAN:
                result = float(field_value) > float(condition.value)
            elif condition.operator == RuleOperator.LESS_THAN:
                result = float(field_value) < float(condition.value)
            elif condition.operator == RuleOperator.GREATER_EQUAL:
                result = float(field_value) >= float(condition.value)
            elif condition.operator == RuleOperator.LESS_EQUAL:
                result = float(field_value) <= float(condition.value)
            elif condition.operator == RuleOperator.CONTAINS:
                result = str(condition.value).lower() in str(field_value).lower()
            elif condition.operator == RuleOperator.NOT_CONTAINS:
                result = str(condition.value).lower() not in str(field_value).lower()
            elif condition.operator == RuleOperator.STARTS_WITH:
                result = (
                    str(field_value).lower().startswith(str(condition.value).lower())
                )
            elif condition.operator == RuleOperator.ENDS_WITH:
                result = str(field_value).lower().endswith(str(condition.value).lower())
            elif condition.operator == RuleOperator.REGEX_MATCH:
                result = bool(
                    re.search(str(condition.value), str(field_value)),
                )  # REGEX OK: rule condition evaluation
            elif condition.operator == RuleOperator.IN:
                result = field_value in condition.value
            elif condition.operator == RuleOperator.NOT_IN:
                result = field_value not in condition.value
            else:
                result = False

            explanation = f"{condition.field}({field_value}) {condition.operator.value} {condition.value} = {result}"
            return result, explanation

        except Exception as e:
            explanation = f"Error evaluating {condition.field}: {e}"
            return False, explanation

    def _get_field_value(self, field_path: str, data: dict[str, t.Any]) -> t.Any:
        """Get field value supporting dot notation for nested fields."""
        try:
            value = data
            for key in field_path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)
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
        reasoning_chain = []

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
            if self._settings.enable_explanation:
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

    async def _extract_input_data(self, request: ReasoningRequest) -> dict[str, t.Any]:
        """Extract structured data from reasoning request."""
        data = {
            "query": request.query,
            "query_length": len(request.query),
            "has_context": request.context is not None,
            "max_steps": request.max_steps,
            "temperature": request.temperature,
        }

        if request.context:
            data.update(
                {
                    "session_id": request.context.session_id,
                    "user_id": request.context.user_id,
                    "has_conversation_history": bool(
                        request.context.conversation_history,
                    ),
                    "has_knowledge_base": bool(request.context.knowledge_base),
                    "has_retrieved_contexts": bool(request.context.retrieved_contexts),
                },
            )

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

    async def _extract_entities_from_text(self, text: str) -> dict[str, t.Any]:
        """Extract entities from text using simple patterns."""
        entities = {}

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
            for q in ["what", "how", "why", "when", "where", "who", "which"]
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
        data: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        """Execute rule actions."""
        results = {"executed_actions": [], "final_result": ""}

        for action in actions:
            try:
                if action.action_type == ActionType.RETURN_VALUE:
                    value = action.parameters.get("value", "")
                    results["final_result"] = str(value)
                    results["executed_actions"].append(f"Returned value: {value}")

                elif action.action_type == ActionType.SET_VARIABLE:
                    var_name = action.parameters.get("variable")
                    var_value = action.parameters.get("value")
                    data[var_name] = var_value
                    results["executed_actions"].append(f"Set {var_name} = {var_value}")

                elif action.action_type == ActionType.LOG_MESSAGE:
                    message = action.parameters.get("message", "")
                    self.logger.info(f"Rule action log: {message}")
                    results["executed_actions"].append(f"Logged: {message}")

                elif action.action_type == ActionType.RAISE_ALERT:
                    alert_message = action.parameters.get("message", "Alert triggered")
                    self.logger.warning(f"Rule alert: {alert_message}")
                    results["executed_actions"].append(f"Alert: {alert_message}")

                else:
                    results["executed_actions"].append(
                        f"Unknown action type: {action.action_type}",
                    )

            except Exception as e:
                self.logger.exception(
                    f"Error executing action {action.action_type}: {e}"
                )
                results["executed_actions"].append(
                    f"Error in {action.action_type}: {e}",
                )

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

    async def get_rule_statistics(self) -> dict[str, t.Any]:
        """Get execution statistics for all rules."""
        engine = await self._ensure_client()
        return engine.get_rule_statistics()


# Export the adapter class
__all__ = ["MODULE_METADATA", "CustomReasoningSettings", "Reasoning"]
