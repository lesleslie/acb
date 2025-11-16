"""msgspec Model Adapter for Universal Query Interface.

This module implements the ModelAdapter protocol for msgspec models,
allowing the universal query interface to work with msgspec Struct classes.
"""

from __future__ import annotations

import inspect

import typing as t
from typing import Any, TypeVar, get_args, get_origin

from acb.adapters.models._attrs import ModelAdapter

try:
    import msgspec as _msgspec_module

    _msgspec_available = True
except ImportError:
    _msgspec_available = False

    class _FallbackMsgspec:
        class Struct:
            pass


msgspec = _msgspec_module if _msgspec_available else _FallbackMsgspec


MSGSPEC_AVAILABLE = _msgspec_available

T = TypeVar("T", bound="_msgspec_module.Struct")


class MsgspecModelAdapter(ModelAdapter[T]):
    def __init__(self) -> None:
        if not MSGSPEC_AVAILABLE:
            msg = "msgspec is required for MsgspecModelAdapter"
            raise ImportError(msg)

    def serialize(self, instance: T) -> dict[str, Any]:
        if MSGSPEC_AVAILABLE:
            return msgspec.to_builtins(instance)  # type: ignore[attr-defined, no-any-return, union-attr]
        return self._manual_serialize(instance)

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        result = {}
        if hasattr(instance, "__struct_fields__"):
            for field_name in instance.__struct_fields__:  # type: ignore  # type: ignore[attr-defined]
                if hasattr(instance, field_name):
                    value = getattr(instance, field_name)
                    result[field_name] = self._serialize_value(value)
        else:
            for attr_name in dir(instance):
                if not attr_name.startswith("_") and not callable(
                    getattr(instance, attr_name),
                ):
                    value = getattr(instance, attr_name)
                    result[attr_name] = self._serialize_value(value)
        return result

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, msgspec.Struct):
            return self.serialize(value)
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        return value

    def deserialize(self, data: dict[str, Any]) -> T:
        msg = "Deserialize requires specific model class context"
        raise NotImplementedError(msg)

    def deserialize_to_class(self, model_class: type[T], data: dict[str, Any]) -> T:
        if MSGSPEC_AVAILABLE and msgspec is not None:
            try:
                return msgspec.convert(data, model_class)  # type: ignore[attr-defined, union-attr, redundant-cast]
            except Exception:
                filtered_data = self._filter_data_for_model(model_class, data)
                return model_class(**filtered_data)
        else:
            filtered_data = self._filter_data_for_model(model_class, data)
            return model_class(**filtered_data)

    def _filter_data_for_model(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if hasattr(model_class, "__struct_fields__"):
            model_fields = set(model_class.__struct_fields__)  # type: ignore[attr-defined]
            return {k: v for k, v in data.items() if k in model_fields}
        return data

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__tablename__"):
            return model_class.__tablename__  # type: ignore  # type: ignore[attr-defined]
        if hasattr(model_class, "__collection_name__"):
            return model_class.__collection_name__  # type: ignore  # type: ignore[attr-defined]
        return model_class.__name__.lower()

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        field_mapping: dict[str, str] = {}
        if hasattr(model_class, "__struct_fields__"):
            field_mapping = {name: name for name in model_class.__struct_fields__}
        elif hasattr(model_class, "__annotations__"):
            field_mapping = {name: name for name in model_class.__annotations__}
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
            return self.serialize(temp_instance)

    def get_primary_key_field(self, model_class: type[T]) -> str:
        common_pk_names = ["id", "pk", "primary_key", "_id"]
        if hasattr(model_class, "__struct_fields__"):
            for field_name in model_class.__struct_fields__:  # type: ignore  # type: ignore[attr-defined]
                if field_name in common_pk_names:
                    return field_name
        elif hasattr(model_class, "__annotations__"):
            for field_name in model_class.__annotations__:
                if field_name in common_pk_names:
                    return field_name
        return "id"

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        if hasattr(model_class, "__annotations__"):
            annotation = model_class.__annotations__.get(field_name, Any)
            return t.cast("type", annotation)  # type: ignore[no-any-return]
        return Any  # type: ignore[return-value]

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        field_type = self.get_field_type(model_class, field_name)
        if hasattr(field_type, "__origin__"):
            origin = get_origin(t.cast("t.Any", field_type))
            if origin is list:
                args = get_args(t.cast("t.Any", field_type))
                if (
                    args
                    and inspect.isclass(args[0])
                    and issubclass(args[0], msgspec.Struct)
                ):
                    return True
        return bool(
            inspect.isclass(field_type) and issubclass(field_type, msgspec.Struct),
        )

    def get_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type[t.Any] | None:  # type: ignore[valid-type]
        field_type = self.get_field_type(model_class, field_name)

        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if (
                    args
                    and inspect.isclass(args[0])
                    and issubclass(args[0], msgspec.Struct)
                ):
                    return args[0]

        if inspect.isclass(field_type) and issubclass(field_type, msgspec.Struct):
            return field_type

        return None
