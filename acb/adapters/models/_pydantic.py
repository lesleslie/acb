"""Pydantic Model Adapter for Universal Query Interface.

This module implements the ModelAdapter protocol for Pydantic models,
allowing the universal query interface to work with Pydantic classes.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from typing import Any, TypeVar, Union, get_args, get_origin

from acb.adapters.models._query import ModelAdapter

try:
    from pydantic import BaseModel as PydanticBaseModel

    BaseModel = PydanticBaseModel  # type: ignore[misc]
    _pydantic_available = True
except ImportError:
    _pydantic_available = False

    class BaseModel:  # type: ignore[misc]
        pass


PYDANTIC_AVAILABLE = _pydantic_available

T = TypeVar("T", bound=BaseModel)


class PydanticModelAdapter(ModelAdapter[T]):
    def __init__(self) -> None:
        if not PYDANTIC_AVAILABLE:
            msg = "Pydantic is required for PydanticModelAdapter"
            raise ImportError(msg)

    def serialize(self, instance: T) -> dict[str, Any]:
        if hasattr(instance, "model_dump"):
            return instance.model_dump()  # type: ignore[attr-defined]
        if hasattr(instance, "dict"):
            return instance.dict()  # type: ignore[attr-defined]
        return self._manual_serialize(instance)

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        if hasattr(instance, "model_fields"):
            return self._serialize_fields(instance, instance.model_fields.keys())  # type: ignore[attr-defined]
        elif hasattr(instance, "__fields__"):
            return self._serialize_fields(instance, instance.__fields__.keys())  # type: ignore[attr-defined]

        return self._serialize_all_attributes(instance)

    def _serialize_fields(
        self, instance: T, field_names: Sequence[str]
    ) -> dict[str, Any]:
        result = {}
        for field_name in field_names:
            if hasattr(instance, field_name):
                value = getattr(instance, field_name)
                result[field_name] = self._serialize_value(value)
        return result

    def _serialize_all_attributes(self, instance: T) -> dict[str, Any]:
        result = {}
        for attr_name in dir(instance):
            if not attr_name.startswith("_") and not callable(
                getattr(instance, attr_name)
            ):
                value = getattr(instance, attr_name)
                result[attr_name] = self._serialize_value(value)
        return result

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return self.serialize(value)  # type: ignore[arg-type]
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
            model_fields = set(model_class.__fields__.keys())  # type: ignore[attr-defined]
        elif hasattr(model_class, "model_fields"):
            model_fields = set(model_class.model_fields.keys())  # type: ignore[attr-defined]
        else:
            return data

        return {k: v for k, v in data.items() if k in model_fields}

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__tablename__"):
            return model_class.__tablename__  # type: ignore[attr-defined]
        if hasattr(model_class, "__collection_name__"):
            return model_class.__collection_name__  # type: ignore[attr-defined]
        if hasattr(model_class, "Config") and hasattr(
            model_class.Config,  # type: ignore[attr-defined]
            "collection_name",
        ):
            return model_class.Config.collection_name  # type: ignore[attr-defined]
        if hasattr(model_class, "model_config") and isinstance(
            model_class.model_config,  # type: ignore[attr-defined]
            dict,
        ):
            return model_class.model_config.get(  # type: ignore[attr-defined]
                "collection_name",
                model_class.__name__.lower(),
            )
        return model_class.__name__.lower()

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        field_mapping = {}
        if hasattr(model_class, "model_fields"):
            field_mapping = self._extract_field_mapping_from_fields(
                model_class.model_fields.items()  # type: ignore[attr-defined]
            )
        elif hasattr(model_class, "__fields__"):
            field_mapping = self._extract_field_mapping_from_fields(
                model_class.__fields__.items()  # type: ignore[attr-defined]
            )
        elif hasattr(model_class, "__annotations__"):
            field_mapping = {name: name for name in model_class.__annotations__}

        return field_mapping

    def _extract_field_mapping_from_fields(self, field_items: Any) -> dict[str, str]:
        return {
            field_name: (
                field_info.alias
                if hasattr(field_info, "alias") and field_info.alias
                else field_name
            )
            for field_name, field_info in field_items
        }

    def validate_data(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            temp_instance = model_class(**data)
            return self.serialize(temp_instance)
        except Exception:
            filtered_data = self._filter_data_for_model(model_class, data)
            temp_instance = model_class(**filtered_data)
            return self.serialize(temp_instance)

    def get_primary_key_field(self, model_class: type[T]) -> str:
        config_pk = self._get_configured_primary_key(model_class)
        if config_pk:
            return config_pk

        return self._find_common_primary_key_field(model_class)

    def _get_configured_primary_key(self, model_class: type[T]) -> str | None:
        if hasattr(model_class, "Config") and hasattr(
            model_class.Config,  # type: ignore[attr-defined]
            "primary_key",
        ):
            return model_class.Config.primary_key  # type: ignore[attr-defined]
        if hasattr(model_class, "model_config") and isinstance(
            model_class.model_config,  # type: ignore[attr-defined]
            dict,
        ):
            return model_class.model_config.get("primary_key")  # type: ignore[attr-defined]

        return None

    def _find_common_primary_key_field(self, model_class: type[T]) -> str:
        common_pk_names = ["id", "pk", "primary_key", "_id"]
        fields = None
        if hasattr(model_class, "model_fields"):
            fields = model_class.model_fields  # type: ignore[attr-defined]
        elif hasattr(model_class, "__fields__"):
            fields = model_class.__fields__  # type: ignore[attr-defined]
        if fields:
            for field_name in fields:
                if field_name in common_pk_names:
                    return field_name

        return "id"

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        if hasattr(model_class, "model_fields"):
            field_info = model_class.model_fields.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                return self._unwrap_optional_type(field_info.annotation)
        elif hasattr(model_class, "__fields__"):
            field_info = model_class.__fields__.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                field_type = getattr(
                    field_info, "annotation", getattr(field_info, "type_", Any)
                )
                return self._unwrap_optional_type(field_type)
        elif hasattr(model_class, "__annotations__"):
            field_type = model_class.__annotations__.get(field_name, Any)
            return self._unwrap_optional_type(field_type)

        return Any  # type: ignore[return-value]

    def _unwrap_optional_type(self, field_type: Any) -> type:
        origin = get_origin(field_type)
        if origin is Union:
            args = get_args(field_type)
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return non_none_args[0]
        elif (
            hasattr(field_type, "__class__")
            and field_type.__class__.__name__ == "UnionType"
        ):
            args = get_args(field_type)
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return non_none_args[0]
        return field_type

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        field_type = self.get_field_type(model_class, field_name)
        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]) and issubclass(args[0], BaseModel):
                    return True
        return bool(inspect.isclass(field_type) and issubclass(field_type, BaseModel))

    def get_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type[BaseModel] | None:
        field_type = self.get_field_type(model_class, field_name)

        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]) and issubclass(args[0], BaseModel):
                    return args[0]

        if inspect.isclass(field_type) and issubclass(field_type, BaseModel):
            return field_type

        return None
