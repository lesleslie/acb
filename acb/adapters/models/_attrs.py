"""attrs Model Adapter for Universal Query Interface.

This module implements the ModelAdapter protocol for attrs models,
allowing the universal query interface to work with attrs-decorated classes.
"""

from __future__ import annotations

import inspect
from typing import Any, Protocol, TypeVar, get_args, get_origin

T = TypeVar("T")


class ModelAdapter(Protocol[T]):
    """Protocol for model adapters with simplified interface."""

    def create_instance(self, model_class: type[T], **kwargs: Any) -> T: ...

    def serialize(self, instance: T) -> dict[str, Any]: ...

    def get_field_value(self, instance: T, field_name: str) -> Any: ...

    def get_field_type(self, model_class: type[T], field_name: str) -> type: ...


# Import attrs or create fallback
_attrs_lib: Any
try:
    import attrs

    _attrs_available = True
    _attrs_lib = attrs
except ImportError:

    class _FallbackAttrsLib:
        @staticmethod
        def has(model_class: type) -> bool:
            return False

        @staticmethod
        def fields(model_class: type) -> Any:
            return []

        @staticmethod
        def asdict(instance: Any) -> dict[str, Any]:
            return {}

    _attrs_available = False
    _attrs_lib = _FallbackAttrsLib()

attrs_lib = _attrs_lib

ATTRS_AVAILABLE = _attrs_available


class AttrsModelAdapter(ModelAdapter[T]):
    def __init__(self) -> None:
        if not ATTRS_AVAILABLE:
            msg = "attrs is required for AttrsModelAdapter"
            raise ImportError(msg)

    def serialize(self, instance: T) -> dict[str, Any]:
        if ATTRS_AVAILABLE and attrs_lib.has(instance.__class__):
            return attrs_lib.asdict(instance)  # type: ignore[arg-type,no-any-return]
        return self._manual_serialize(instance)

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if ATTRS_AVAILABLE and attrs_lib.has(instance.__class__):
            for field in attrs_lib.fields(instance.__class__):
                if hasattr(instance, field.name):
                    value = getattr(instance, field.name)
                    result[field.name] = self._serialize_value(value)
        else:
            for attr_name in dir(instance):
                if not attr_name.startswith("_") and not callable(
                    getattr(instance, attr_name)
                ):
                    value = getattr(instance, attr_name)
                    result[attr_name] = self._serialize_value(value)
        return result  # type: ignore  # type: ignore[no-any-return]

    def _serialize_value(self, value: Any) -> Any:
        if ATTRS_AVAILABLE and attrs_lib.has(value.__class__):
            return self.serialize(value)
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        return value  # type: ignore  # type: ignore[no-any-return]

    def deserialize(self, data: dict[str, Any]) -> T:
        msg = "Deserialize requires specific model class context"
        raise NotImplementedError(msg)

    def deserialize_to_class(self, model_class: type[T], data: dict[str, Any]) -> T:
        try:
            return model_class(**data)
        except Exception:
            filtered_data = self._filter_data_for_model(model_class, data)
            return model_class(**filtered_data)  # type: ignore  # type: ignore[no-any-return]

    def _filter_data_for_model(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if ATTRS_AVAILABLE and attrs_lib.has(model_class):
            model_fields = {field.name for field in attrs_lib.fields(model_class)}
            return {k: v for k, v in data.items() if k in model_fields}
        elif hasattr(model_class, "__annotations__"):
            model_fields = set(model_class.__annotations__.keys())
            return {k: v for k, v in data.items() if k in model_fields}
        return data

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__tablename__"):
            return str(model_class.__tablename__)  # type: ignore  # type: ignore[attr-defined]
        if hasattr(model_class, "__collection_name__"):
            return str(model_class.__collection_name__)  # type: ignore  # type: ignore[attr-defined]
        if ATTRS_AVAILABLE and attrs_lib.has(model_class):
            for field in attrs_lib.fields(model_class):  # type: ignore[arg-type]
                if hasattr(field, "metadata") and "table_name" in field.metadata:
                    return str(field.metadata["table_name"])

        return getattr(model_class, "__name__", "unknown").lower()

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        field_mapping = {}
        if ATTRS_AVAILABLE and attrs_lib.has(model_class):
            for field in attrs_lib.fields(model_class):  # type: ignore[arg-type]
                alias = field.name
                if hasattr(field, "metadata") and "alias" in field.metadata:
                    alias = str(field.metadata["alias"])
                field_mapping[field.name] = alias
        elif hasattr(model_class, "__annotations__"):
            annotations = getattr(model_class, "__annotations__", {})
            field_mapping = {name: name for name in annotations}

        return field_mapping

    def validate_data(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            temp_instance = self.deserialize_to_class(model_class, data)
            return self.serialize(temp_instance)
        except Exception:
            filtered_data = self._filter_data_for_model(model_class, data)
            temp_instance = self.deserialize_to_class(model_class, filtered_data)
            return self.serialize(temp_instance)  # type: ignore  # type: ignore[no-any-return]

    def get_primary_key_field(self, model_class: type[T]) -> str:
        if ATTRS_AVAILABLE and attrs_lib.has(model_class):
            return self._get_attrs_primary_key(model_class)
        if hasattr(model_class, "__annotations__"):
            return self._get_annotation_primary_key(model_class)
        return "id"

    def _get_attrs_primary_key(self, model_class: type[T]) -> str:
        common_pk_names = ("id", "pk", "primary_key", "_id")
        for field in attrs_lib.fields(model_class):  # type: ignore[arg-type]
            if hasattr(field, "metadata") and field.metadata.get("primary_key"):
                return str(field.name)
            if field.name in common_pk_names:
                return str(field.name)
        return "id"

    def _get_annotation_primary_key(self, model_class: type[T]) -> str:
        common_pk_names = ("id", "pk", "primary_key", "_id")
        annotations = getattr(model_class, "__annotations__", {})
        for field_name in annotations:
            if field_name in common_pk_names:
                return str(field_name)
        return "id"

    def get_field_names(self, model_class: type[T]) -> list[str]:
        if ATTRS_AVAILABLE and attrs_lib.has(model_class):
            return [field.name for field in attrs_lib.fields(model_class)]  # type: ignore[no-any-return,arg-type]
        return self._get_field_names_from_annotations(model_class)

    def _get_field_names_from_annotations(self, model_class: type[T]) -> list[str]:
        if hasattr(model_class, "__annotations__"):
            annotations = getattr(model_class, "__annotations__", {})
            return list(annotations.keys())
        return []

    def get_field_types(self, model_class: type[T]) -> dict[str, type]:
        if ATTRS_AVAILABLE and attrs_lib.has(model_class):
            field_dict: dict[str, type] = {}
            for field in attrs_lib.fields(model_class):  # type: ignore[arg-type]
                field_type: type = field.type if field.type is not None else Any  # type: ignore[assignment]
                field_dict[field.name] = field_type  # type: ignore  # type: ignore[no-any-return]
            return field_dict
        return self._get_field_types_from_annotations(model_class)

    def _get_field_types_from_annotations(
        self, model_class: type[T]
    ) -> dict[str, type]:
        if hasattr(model_class, "__annotations__"):
            annotations = getattr(model_class, "__annotations__", {})
            return dict(annotations)  # type: ignore[return-value]
        return {}

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        if ATTRS_AVAILABLE and attrs_lib.has(model_class):
            for field in attrs_lib.fields(model_class):  # type: ignore[arg-type]
                if field.name == field_name:
                    field_type = field.type or Any
                    return field_type  # type: ignore[no-any-return,return-value]
        if hasattr(model_class, "__annotations__"):
            annotations = getattr(model_class, "__annotations__", {})
            annotation_type = annotations.get(field_name, Any)
            return annotation_type  # type: ignore  # type: ignore[no-any-return]

        return Any  # type: ignore  # type: ignore[no-any-return]

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        field_type = self.get_field_type(model_class, field_name)
        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]):
                    return ATTRS_AVAILABLE and attrs_lib.has(args[0])

        return bool(
            inspect.isclass(field_type)
            and ATTRS_AVAILABLE
            and attrs_lib.has(field_type)
        )

    def get_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type | None:
        field_type = self.get_field_type(model_class, field_name)

        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if (
                    args
                    and inspect.isclass(args[0])
                    and ATTRS_AVAILABLE
                    and attrs_lib.has(args[0])
                ):
                    return args[0]  # type: ignore[no-any-return,return-value]

        if (
            inspect.isclass(field_type)
            and ATTRS_AVAILABLE
            and attrs_lib.has(field_type)
        ):
            return field_type  # type: ignore[return-value,no-any-return]

        return None
