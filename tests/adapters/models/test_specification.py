"""Tests for the Specification Pattern implementation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from acb.adapters.models._query import QueryCondition, QueryOperator, QuerySpec
from acb.adapters.models._specification import (
    CompositeSpecification,
    CustomSpecification,
    FieldSpecification,
    FieldSpecificationBuilder,
    ListSpecification,
    LogicalOperator,
    NotSpecification,
    RangeSpecification,
    Specification,
    SpecificationBuilder,
    SpecificationResult,
    custom_spec,
    field,
    list_spec,
    range_spec,
)


class Product:
    def __init__(
        self,
        id: int,
        name: str,
        price: float,
        category: str,
        in_stock: bool,
        tags: list[str] | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.price = price
        self.category = category
        self.in_stock = in_stock
        self.tags = tags


class MockSpecification(Specification[Product]):
    def __init__(self, satisfied: bool = True) -> None:
        self.satisfied = satisfied

    def is_satisfied_by(self, candidate: Product) -> bool:
        return self.satisfied

    def to_query_spec(self) -> QuerySpec:
        spec = QuerySpec()
        spec.filter.conditions.append(
            QueryCondition("mock", QueryOperator.EQ, self.satisfied)
        )
        return spec


class TestSpecificationResult:
    def test_specification_result_creation(self) -> None:
        result = SpecificationResult(
            satisfied=True, reason="Test passed", context={"test": "value"}
        )
        assert result.satisfied
        assert result.reason == "Test passed"
        assert result.context == {"test": "value"}


class TestFieldSpecification:
    def test_field_equals(self) -> None:
        spec = FieldSpecification("price", QueryOperator.EQ, 100)
        product = Product(1, "Test", 100, "Electronics", True)

        assert spec.is_satisfied_by(product)

        product2 = Product(2, "Test2", 200, "Electronics", True)
        assert not spec.is_satisfied_by(product2)

    def test_field_not_equals(self) -> None:
        spec = FieldSpecification("category", QueryOperator.NE, "Electronics")
        product = Product(1, "Test", 100, "Books", True)

        assert spec.is_satisfied_by(product)

    def test_field_greater_than(self) -> None:
        spec = FieldSpecification("price", QueryOperator.GT, 50)
        product = Product(1, "Test", 100, "Electronics", True)

        assert spec.is_satisfied_by(product)

        product2 = Product(2, "Test2", 30, "Electronics", True)
        assert not spec.is_satisfied_by(product2)

    def test_field_in_list(self) -> None:
        spec = FieldSpecification(
            "category", QueryOperator.IN, ["Electronics", "Books"]
        )
        product = Product(1, "Test", 100, "Electronics", True)

        assert spec.is_satisfied_by(product)

        product2 = Product(2, "Test2", 100, "Clothing", True)
        assert not spec.is_satisfied_by(product2)

    def test_field_is_null(self) -> None:
        spec = FieldSpecification("tags", QueryOperator.IS_NULL, None)
        product = Product(1, "Test", 100, "Electronics", True, None)

        assert spec.is_satisfied_by(product)

    def test_field_is_not_null(self) -> None:
        spec = FieldSpecification("tags", QueryOperator.IS_NOT_NULL, None)
        product = Product(1, "Test", 100, "Electronics", True, ["new"])

        assert spec.is_satisfied_by(product)

    def test_field_like_pattern(self) -> None:
        spec = FieldSpecification("name", QueryOperator.LIKE, "%Test%")
        product = Product(1, "TestProduct", 100, "Electronics", True)

        assert spec.is_satisfied_by(product)

    def test_field_between(self) -> None:
        spec = FieldSpecification("price", QueryOperator.BETWEEN, [50, 150])
        product = Product(1, "Test", 100, "Electronics", True)

        assert spec.is_satisfied_by(product)

        product2 = Product(2, "Test2", 200, "Electronics", True)
        assert not spec.is_satisfied_by(product2)

    def test_field_missing_attribute(self) -> None:
        spec = FieldSpecification("nonexistent", QueryOperator.EQ, "value")
        product = Product(1, "Test", 100, "Electronics", True)

        assert not spec.is_satisfied_by(product)

    def test_to_query_spec(self) -> None:
        spec = FieldSpecification("price", QueryOperator.GT, 50)
        assert len((query_spec := spec.to_query_spec()).filter.conditions) == 1
        assert (condition := query_spec.filter.conditions[0]).field == "price"
        assert condition.operator == QueryOperator.GT
        assert condition.value == 50


class TestCompositeSpecification:
    def test_and_operator(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.GT, 50)
        spec2 = FieldSpecification("in_stock", QueryOperator.EQ, True)
        composite = CompositeSpecification(spec1, spec2, LogicalOperator.AND)

        product = Product(1, "Test", 100, "Electronics", True)
        assert composite.is_satisfied_by(product)

        product2 = Product(2, "Test2", 30, "Electronics", True)
        assert not composite.is_satisfied_by(product2)

    def test_or_operator(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.LT, 50)
        spec2 = FieldSpecification("category", QueryOperator.EQ, "Premium")
        composite = CompositeSpecification(spec1, spec2, LogicalOperator.OR)

        product = Product(1, "Test", 30, "Regular", True)
        assert composite.is_satisfied_by(product)

        product2 = Product(2, "Test2", 200, "Premium", True)
        assert composite.is_satisfied_by(product2)

    def test_invalid_operator(self) -> None:
        spec1 = MockSpecification(True)
        spec2 = MockSpecification(True)
        composite = CompositeSpecification(spec1, spec2, LogicalOperator.NOT)

        product = Product(1, "Test", 100, "Electronics", True)
        with pytest.raises(ValueError, match="Unsupported logical operator"):
            composite.is_satisfied_by(product)

    def test_to_query_spec_and(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.GT, 50)
        spec2 = FieldSpecification("in_stock", QueryOperator.EQ, True)
        composite = CompositeSpecification(spec1, spec2, LogicalOperator.AND)

        assert len((query_spec := composite.to_query_spec()).filter.conditions) == 2
        assert query_spec.filter.logical_operator == "AND"

    def test_to_query_spec_or(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.LT, 50)
        spec2 = FieldSpecification("category", QueryOperator.EQ, "Premium")
        composite = CompositeSpecification(spec1, spec2, LogicalOperator.OR)

        assert len((query_spec := composite.to_query_spec()).filter.conditions) == 2
        assert query_spec.filter.logical_operator == "OR"

    def test_to_query_spec_with_limits(self) -> None:
        spec1 = MockSpecification(True)
        spec1_query = spec1.to_query_spec()
        spec1_query.limit = 10
        spec1_query.offset = 5
        spec1.to_query_spec = lambda: spec1_query

        spec2 = MockSpecification(True)
        spec2_query = spec2.to_query_spec()
        spec2_query.limit = 20
        spec2_query.offset = 10
        spec2.to_query_spec = lambda: spec2_query

        composite = CompositeSpecification(spec1, spec2, LogicalOperator.AND)
        assert (query_spec := composite.to_query_spec()).limit == 10  # min of 10 and 20
        assert query_spec.offset == 10  # max of 5 and 10

    def test_evaluate(self) -> None:
        spec1 = MockSpecification(True)
        spec2 = MockSpecification(False)
        composite = CompositeSpecification(spec1, spec2, LogicalOperator.AND)

        product = Product(1, "Test", 100, "Electronics", True)
        result = composite.evaluate(product)

        assert not result.satisfied
        assert result.reason is not None and "AND" in result.reason
        assert result.context is not None and result.context["operator"] == "and"


class TestNotSpecification:
    def test_not_specification(self) -> None:
        spec = FieldSpecification("in_stock", QueryOperator.EQ, True)
        not_spec = NotSpecification(spec)

        product = Product(1, "Test", 100, "Electronics", False)
        assert not_spec.is_satisfied_by(product)

        product2 = Product(2, "Test2", 100, "Electronics", True)
        assert not not_spec.is_satisfied_by(product2)

    def test_to_query_spec_inverts_conditions(self) -> None:
        spec = FieldSpecification("price", QueryOperator.GT, 50)
        not_spec = NotSpecification(spec)

        assert len((query_spec := not_spec.to_query_spec()).filter.conditions) == 1
        condition = query_spec.filter.conditions[0]
        assert condition.operator == QueryOperator.LTE

    def test_invert_all_operators(self) -> None:
        not_spec = NotSpecification(MockSpecification())

        # Test all operator inversions
        test_cases = [
            (QueryOperator.EQ, QueryOperator.NE),
            (QueryOperator.NE, QueryOperator.EQ),
            (QueryOperator.GT, QueryOperator.LTE),
            (QueryOperator.GTE, QueryOperator.LT),
            (QueryOperator.LT, QueryOperator.GTE),
            (QueryOperator.LTE, QueryOperator.GT),
            (QueryOperator.IN, QueryOperator.NOT_IN),
            (QueryOperator.NOT_IN, QueryOperator.IN),
            (QueryOperator.IS_NULL, QueryOperator.IS_NOT_NULL),
            (QueryOperator.IS_NOT_NULL, QueryOperator.IS_NULL),
        ]

        for original, expected in test_cases:
            condition = QueryCondition("field", original, "value")
            inverted = not_spec._invert_condition(condition)
            assert inverted.operator == expected

    def test_invert_logical_operators(self) -> None:
        spec = MockSpecification()
        spec_query = spec.to_query_spec()
        spec_query.filter.logical_operator = "AND"
        spec.to_query_spec = lambda: spec_query

        not_spec = NotSpecification(spec)
        assert not_spec.to_query_spec().filter.logical_operator == "OR"

    def test_evaluate(self) -> None:
        spec = MockSpecification(True)
        not_spec = NotSpecification(spec)

        product = Product(1, "Test", 100, "Electronics", True)
        result = not_spec.evaluate(product)

        assert not result.satisfied
        assert result.reason is not None and "NOT" in result.reason
        assert result.context is not None and result.context["operator"] == "NOT"


class TestRangeSpecification:
    def test_inclusive_range(self) -> None:
        spec = RangeSpecification("price", 50, 150)

        product1 = Product(1, "Test1", 50, "Electronics", True)
        assert spec.is_satisfied_by(product1)

        product2 = Product(2, "Test2", 150, "Electronics", True)
        assert spec.is_satisfied_by(product2)

        product3 = Product(3, "Test3", 200, "Electronics", True)
        assert not spec.is_satisfied_by(product3)

    def test_exclusive_range(self) -> None:
        spec = RangeSpecification("price", 50, 150, inclusive=False)

        product1 = Product(1, "Test1", 50, "Electronics", True)
        assert not spec.is_satisfied_by(product1)

        product2 = Product(2, "Test2", 100, "Electronics", True)
        assert spec.is_satisfied_by(product2)

    def test_missing_field(self) -> None:
        spec = RangeSpecification("nonexistent", 50, 150)
        product = Product(1, "Test", 100, "Electronics", True)

        assert not spec.is_satisfied_by(product)

    def test_to_query_spec_inclusive(self) -> None:
        spec = RangeSpecification("price", 50, 150)
        assert len((query_spec := spec.to_query_spec()).filter.conditions) == 2
        assert query_spec.filter.logical_operator == "AND"

        conditions = {c.operator: c for c in query_spec.filter.conditions}
        assert conditions[QueryOperator.GTE].value == 50
        assert conditions[QueryOperator.LTE].value == 150

    def test_to_query_spec_exclusive(self) -> None:
        _query_spec = RangeSpecification(
            "price", 50, 150, inclusive=False
        ).to_query_spec()
        conditions = {c.operator: c for c in _query_spec.filter.conditions}
        assert conditions[QueryOperator.GT].value == 50
        assert conditions[QueryOperator.LT].value == 150


class TestListSpecification:
    def test_include_in_list(self) -> None:
        spec = ListSpecification("category", ["Electronics", "Books"])

        product1 = Product(1, "Test1", 100, "Electronics", True)
        assert spec.is_satisfied_by(product1)

        product2 = Product(2, "Test2", 100, "Clothing", True)
        assert not spec.is_satisfied_by(product2)

    def test_exclude_from_list(self) -> None:
        spec = ListSpecification("category", ["Electronics", "Books"], include=False)

        product1 = Product(1, "Test1", 100, "Clothing", True)
        assert spec.is_satisfied_by(product1)

        product2 = Product(2, "Test2", 100, "Electronics", True)
        assert not spec.is_satisfied_by(product2)

    def test_missing_field(self) -> None:
        spec = ListSpecification("nonexistent", ["value"])
        product = Product(1, "Test", 100, "Electronics", True)

        assert not spec.is_satisfied_by(product)

    def test_to_query_spec_include(self) -> None:
        spec = ListSpecification("category", ["Electronics", "Books"])
        assert len((query_spec := spec.to_query_spec()).filter.conditions) == 1
        condition = query_spec.filter.conditions[0]
        assert condition.operator == QueryOperator.IN
        assert condition.value == ["Electronics", "Books"]

    def test_to_query_spec_exclude(self) -> None:
        spec = ListSpecification("category", ["Electronics", "Books"], include=False)
        condition = (_query_spec := spec.to_query_spec()).filter.conditions[0]
        assert condition.operator == QueryOperator.NOT_IN


class TestCustomSpecification:
    def test_custom_predicate(self) -> None:
        def is_expensive_electronic(product: Product) -> bool:
            return product.category == "Electronics" and product.price > 500

        query_spec = QuerySpec()
        query_spec.filter.conditions.extend(
            (
                QueryCondition("category", QueryOperator.EQ, "Electronics"),
                QueryCondition("price", QueryOperator.GT, 500),
            )
        )

        spec = CustomSpecification(
            is_expensive_electronic, query_spec, "ExpensiveElectronic"
        )

        product1 = Product(1, "Test1", 600, "Electronics", True)
        assert spec.is_satisfied_by(product1)

        product2 = Product(2, "Test2", 400, "Electronics", True)
        assert not spec.is_satisfied_by(product2)

    def test_predicate_exception(self) -> None:
        def failing_predicate(product: Product) -> bool:
            raise ValueError("Test error")

        spec = CustomSpecification(failing_predicate, QuerySpec())
        product = Product(1, "Test", 100, "Electronics", True)

        assert not spec.is_satisfied_by(product)

    def test_evaluate(self) -> None:
        def always_true(product: Product) -> bool:
            return True

        spec = CustomSpecification(always_true, QuerySpec(), "AlwaysTrue")
        product = Product(1, "Test", 100, "Electronics", True)

        result = spec.evaluate(product)
        assert result.satisfied
        assert result.reason is not None and "AlwaysTrue" in result.reason

    def test_evaluate_with_exception(self) -> None:
        def failing_predicate(product: Product) -> bool:
            raise ValueError("Test error")

        spec = CustomSpecification(failing_predicate, QuerySpec(), "FailingSpec")
        product = Product(1, "Test", 100, "Electronics", True)

        result = spec.evaluate(product)
        assert not result.satisfied
        assert result.reason is not None and "Test error" in result.reason
        assert (
            result.context is not None
            and result.context["specification"] == "FailingSpec"
        )


class TestSpecificationOperators:
    def test_and_operator_method(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.GT, 50)
        spec2 = FieldSpecification("in_stock", QueryOperator.EQ, True)

        composite = spec1.and_(spec2)
        assert isinstance(composite, CompositeSpecification)
        assert composite.operator == LogicalOperator.AND

    def test_or_operator_method(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.GT, 50)
        spec2 = FieldSpecification("in_stock", QueryOperator.EQ, True)

        composite = spec1.or_(spec2)
        assert isinstance(composite, CompositeSpecification)
        assert composite.operator == LogicalOperator.OR

    def test_not_operator_method(self) -> None:
        spec = FieldSpecification("in_stock", QueryOperator.EQ, True)

        assert isinstance(spec.not_(), NotSpecification)

    def test_dunder_and(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.GT, 50)
        spec2 = FieldSpecification("in_stock", QueryOperator.EQ, True)

        composite = spec1 & spec2
        assert isinstance(composite, CompositeSpecification)
        assert composite.operator == LogicalOperator.AND

    def test_dunder_or(self) -> None:
        spec1 = FieldSpecification("price", QueryOperator.GT, 50)
        spec2 = FieldSpecification("in_stock", QueryOperator.EQ, True)

        composite = spec1 | spec2
        assert isinstance(composite, CompositeSpecification)
        assert composite.operator == LogicalOperator.OR

    def test_dunder_invert(self) -> None:
        spec = FieldSpecification("in_stock", QueryOperator.EQ, True)

        not_spec = ~spec
        assert isinstance(not_spec, NotSpecification)


class TestSpecificationBuilder:
    def test_field_builder(self) -> None:
        builder = SpecificationBuilder.field("price")
        assert isinstance(builder, FieldSpecificationBuilder)

    def test_range_builder(self) -> None:
        spec = SpecificationBuilder.range("price", 50, 150)
        assert isinstance(spec, RangeSpecification)
        assert spec.field == "price"
        assert spec.min_value == 50
        assert spec.max_value == 150

    def test_list_builder(self) -> None:
        spec = SpecificationBuilder.list("category", ["Electronics", "Books"])
        assert isinstance(spec, ListSpecification)
        assert spec.field == "category"
        assert spec.values == ["Electronics", "Books"]

    def test_custom_builder(self) -> None:
        spec = SpecificationBuilder.custom(lambda x: True, QuerySpec(), "Test")
        assert isinstance(spec, CustomSpecification)
        assert spec.name == "Test"


class TestFieldSpecificationBuilder:
    def test_equals(self) -> None:
        spec = FieldSpecificationBuilder("price").equals(100)
        assert spec.field == "price"
        assert spec.operator == QueryOperator.EQ
        assert spec.value == 100

    def test_not_equals(self) -> None:
        spec = FieldSpecificationBuilder("category").not_equals("Electronics")
        assert spec.operator == QueryOperator.NE

    def test_greater_than(self) -> None:
        spec = FieldSpecificationBuilder("price").greater_than(50)
        assert spec.operator == QueryOperator.GT

    def test_greater_than_or_equal(self) -> None:
        spec = FieldSpecificationBuilder("price").greater_than_or_equal(50)
        assert spec.operator == QueryOperator.GTE

    def test_less_than(self) -> None:
        spec = FieldSpecificationBuilder("price").less_than(150)
        assert spec.operator == QueryOperator.LT

    def test_less_than_or_equal(self) -> None:
        spec = FieldSpecificationBuilder("price").less_than_or_equal(150)
        assert spec.operator == QueryOperator.LTE

    def test_in_list(self) -> None:
        spec = FieldSpecificationBuilder("category").in_list(["Electronics", "Books"])
        assert spec.operator == QueryOperator.IN

    def test_not_in_list(self) -> None:
        spec = FieldSpecificationBuilder("category").not_in_list(["Clothing"])
        assert spec.operator == QueryOperator.NOT_IN

    def test_is_null(self) -> None:
        spec = FieldSpecificationBuilder("tags").is_null()
        assert spec.operator == QueryOperator.IS_NULL

    def test_is_not_null(self) -> None:
        spec = FieldSpecificationBuilder("tags").is_not_null()
        assert spec.operator == QueryOperator.IS_NOT_NULL

    def test_like(self) -> None:
        spec = FieldSpecificationBuilder("name").like("%Test%")
        assert spec.operator == QueryOperator.LIKE

    def test_between(self) -> None:
        spec = FieldSpecificationBuilder("price").between(50, 150)
        assert spec.operator == QueryOperator.BETWEEN
        assert spec.value == [50, 150]


class TestHelperFunctions:
    def test_field_function(self) -> None:
        builder = field("price")
        assert isinstance(builder, FieldSpecificationBuilder)

    def test_range_spec_function(self) -> None:
        spec = range_spec("price", 50, 150)
        assert isinstance(spec, RangeSpecification)

    def test_list_spec_function(self) -> None:
        spec = list_spec("category", ["Electronics"])
        assert isinstance(spec, ListSpecification)

    def test_custom_spec_function(self) -> None:
        spec = custom_spec(lambda x: True, QuerySpec())
        assert isinstance(spec, CustomSpecification)


class TestSpecificationEvaluate:
    def test_base_evaluate_success(self) -> None:
        spec = MockSpecification(True)
        product = Product(1, "Test", 100, "Electronics", True)

        result = spec.evaluate(product)
        assert result.satisfied
        assert result.reason is not None and "satisfied" in result.reason
        assert (
            result.context is not None
            and result.context["specification"] == "MockSpecification"
        )

    def test_base_evaluate_failure(self) -> None:
        spec = MockSpecification(False)
        product = Product(1, "Test", 100, "Electronics", True)

        result = spec.evaluate(product)
        assert not result.satisfied
        assert result.reason is not None and "not satisfied" in result.reason

    def test_base_evaluate_exception(self) -> None:
        spec = MockSpecification()
        spec.is_satisfied_by = MagicMock(side_effect=ValueError("Test error"))
        product = Product(1, "Test", 100, "Electronics", True)

        result = spec.evaluate(product)
        assert not result.satisfied
        assert (
            result.reason is not None
            and "Error evaluating specification" in result.reason
        )
        assert result.context is not None and result.context["error"] == "Test error"


class TestComplexSpecifications:
    def test_complex_combination(self) -> None:
        # (price > 50 AND in_stock) OR category = "Premium"
        price_spec = FieldSpecification("price", QueryOperator.GT, 50)
        stock_spec = FieldSpecification("in_stock", QueryOperator.EQ, True)
        category_spec = FieldSpecification("category", QueryOperator.EQ, "Premium")

        complex_spec = (price_spec & stock_spec) | category_spec

        # Should match: high price and in stock
        product1 = Product(1, "Test1", 100, "Regular", True)
        assert complex_spec.is_satisfied_by(product1)

        # Should match: premium category
        product2 = Product(2, "Test2", 30, "Premium", False)
        assert complex_spec.is_satisfied_by(product2)

        # Should not match: low price, out of stock, not premium
        product3 = Product(3, "Test3", 30, "Regular", False)
        assert not complex_spec.is_satisfied_by(product3)

    def test_complex_with_not(self) -> None:
        # NOT (price < 50 OR out_of_stock)
        price_spec = FieldSpecification("price", QueryOperator.LT, 50)
        stock_spec = FieldSpecification("in_stock", QueryOperator.EQ, False)

        complex_spec = ~(price_spec | stock_spec)

        # Should match: high price and in stock
        product1 = Product(1, "Test1", 100, "Regular", True)
        assert complex_spec.is_satisfied_by(product1)

        # Should not match: low price
        product2 = Product(2, "Test2", 30, "Regular", True)
        assert not complex_spec.is_satisfied_by(product2)
