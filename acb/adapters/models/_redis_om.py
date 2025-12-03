"""Redis-OM Model Adapter for Universal Query Interface.

This module implements the ModelAdapter protocol for Redis-OM models,
allowing the universal query interface to work with Redis-OM HashModel classes.
"""

from __future__ import annotations

import inspect
import warnings

from typing import Any, TypeVar, get_args, get_origin

from acb.adapters.models._attrs import ModelAdapter

try:
    # Suppress Pydantic deprecation warnings from redis_om
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            module="redis_om",
        )
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            module="pydantic",
        )
        from redis_om import HashModel

    _redis_om_available = True
except ImportError:
    _redis_om_available = False

    class _FallbackHashModel:
        pass


HashModel = HashModel if _redis_om_available else _FallbackHashModel


REDIS_OM_AVAILABLE = _redis_om_available

T = TypeVar("T", bound="HashModel")


class RedisOMModelAdapter(ModelAdapter[T]):
    def __init__(self) -> None:
        if not REDIS_OM_AVAILABLE:
            msg = "redis-om is required for RedisOMModelAdapter"
            raise ImportError(msg)

    def serialize(self, instance: T) -> dict[str, Any]:
        if hasattr(instance, "model_dump") and callable(
            instance.model_dump,
        ):
            return instance.model_dump()  # type: ignore  # type: ignore[no-any-return]
        if hasattr(instance, "dict") and callable(instance.dict):
            return instance.dict()  # type: ignore  # type: ignore[no-any-return]
        return self._manual_serialize(instance)

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        fields = getattr(instance, "model_fields", None) or getattr(
            instance,
            "__fields__",
            None,
        )
        if fields:
            return self._serialize_from_fields(instance, fields)
        return self._serialize_from_dir(instance)

    def _serialize_from_fields(self, instance: T, fields: Any) -> dict[str, Any]:
        result = {}
        field_names = fields.keys() if hasattr(fields, "keys") else fields
        for field_name in field_names:
            if hasattr(instance, field_name):
                value = getattr(instance, field_name)
                result[field_name] = self._serialize_value(value)
        return result

    def _serialize_from_dir(self, instance: T) -> dict[str, Any]:
        result = {}
        for attr_name in dir(instance):
            if not attr_name.startswith("_") and not callable(
                getattr(instance, attr_name),
            ):
                value = getattr(instance, attr_name)
                result[attr_name] = self._serialize_value(value)
        return result

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, HashModel):
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
        try:
            return model_class(**data)
        except Exception:
            filtered_data = self._filter_data_for_model(model_class, data)
            return model_class(**filtered_data)

    def _filter_data_for_model(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if hasattr(model_class, "__fields__"):
            model_fields = set(model_class.__fields__.keys())
        elif hasattr(model_class, "model_fields"):
            model_fields = set(model_class.model_fields.keys())
        else:
            return data

        return {k: v for k, v in data.items() if k in model_fields}

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "Meta"):
            meta = model_class.Meta  # type: ignore[attr-defined]
            if hasattr(meta, "model_key_prefix"):
                return meta.model_key_prefix  # type: ignore  # type: ignore[no-any-return]
            if hasattr(meta, "global_key_prefix"):
                return meta.global_key_prefix  # type: ignore  # type: ignore[no-any-return]
        if hasattr(model_class, "__collection_name__"):
            return model_class.__collection_name__  # type: ignore[attr-defined, no-any-return]
        return model_class.__name__.lower()  # type: ignore  # type: ignore[no-any-return]

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        field_mapping = {}
        if hasattr(model_class, "model_fields"):
            for field_name, field_info in model_class.model_fields.items():  # type: ignore  # type: ignore[attr-defined]
                alias = field_name
                if hasattr(field_info, "alias") and field_info.alias:
                    alias = field_info.alias
                field_mapping[field_name] = alias
        elif hasattr(model_class, "__fields__"):
            for field_name, field_info in model_class.__fields__.items():  # type: ignore  # type: ignore[attr-defined]
                alias = field_name
                if hasattr(field_info, "alias") and field_info.alias:
                    alias = field_info.alias
                field_mapping[field_name] = alias
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
        fields = getattr(model_class, "model_fields", None) or getattr(
            model_class,
            "__fields__",
            None,
        )
        if fields:
            for field_name, field_info in fields.items():
                if hasattr(field_info, "primary_key") and field_info.primary_key:
                    return field_name  # type: ignore  # type: ignore[no-any-return]
            common_pk_names = ["pk", "id", "primary_key", "_id"]
            for field_name in fields:
                if field_name in common_pk_names:
                    return field_name  # type: ignore  # type: ignore[no-any-return]

        return "pk"  # type: ignore  # type: ignore[no-any-return]

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        if hasattr(model_class, "model_fields"):
            field_info = model_class.model_fields.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                return field_info.annotation  # type: ignore  # type: ignore[no-any-return]
        elif hasattr(model_class, "__fields__"):
            field_info = model_class.__fields__.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                return getattr(field_info, "type_", Any)  # type: ignore[no-any-return,arg-type]
        elif hasattr(model_class, "__annotations__"):
            return model_class.__annotations__.get(field_name, Any)  # type: ignore  # type: ignore[no-any-return]

        return Any  # type: ignore[return-value]

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        field_type = self.get_field_type(model_class, field_name)
        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]) and issubclass(args[0], HashModel):
                    return True

        return bool(inspect.isclass(field_type) and issubclass(field_type, HashModel))

    def get_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type[HashModel] | None:
        field_type = self.get_field_type(model_class, field_name)

        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]) and issubclass(args[0], HashModel):
                    return args[0]

        if inspect.isclass(field_type) and issubclass(field_type, HashModel):
            return field_type

        return None
