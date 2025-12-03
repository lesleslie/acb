"""Example of refactored Pydantic Model Adapter using ModelAdapterMixin.

This demonstrates how the Pydantic adapter could be simplified by using
the common functionality in ModelAdapterMixin.
"""

from __future__ import annotations

import inspect

from typing import Any, TypeVar, Union, get_args, get_origin

# Import the mixin from base
from ._base import ModelAdapterMixin

# Import pydantic or create fallback
try:
    from pydantic import BaseModel as _PydanticBaseModel

    _pydantic_available = True
except ImportError:
    _pydantic_available = False

    class _FallbackBaseModel:
        pass


_PyDanticBaseModelLocal = (
    _PydanticBaseModel if _pydantic_available else _FallbackBaseModel
)

# Create a type alias that can be used as a type
# Use a different approach to avoid redefinition error
if _pydantic_available:
    BaseModel = _PydanticBaseModel  # type: ignore[no-redef, misc]
else:
    BaseModel = _FallbackBaseModel  # type: ignore[no-redef, misc]
PYDANTIC_AVAILABLE = _pydantic_available

T = TypeVar("T")


class PydanticModelAdapter(ModelAdapterMixin):
    def __init__(self) -> None:
        if not PYDANTIC_AVAILABLE:
            msg = "Pydantic is required for PydanticModelAdapter"
            raise ImportError(msg)

    def create_instance(self, model_class: type[T], **kwargs: Any) -> T:
        """Create an instance of the model class with the given kwargs."""
        return model_class(**kwargs)

    def get_field_value(self, instance: T, field_name: str) -> Any:
        """Get the value of a field from the instance."""
        return getattr(instance, field_name, None)

    def serialize(self, instance: T) -> dict[str, Any]:
        if hasattr(instance, "model_dump"):
            return instance.model_dump()  # type: ignore[no-any-return, attr-defined]
        if hasattr(instance, "dict"):
            return instance.dict()  # type: ignore[no-any-return, attr-defined]
        # Use the mixin's default implementation
        return self._manual_serialize(instance)

    def deserialize(self, data: dict[str, Any]) -> T:
        msg = "Deserialize requires specific model class context"
        raise NotImplementedError(msg)

    def deserialize_to_class(self, model_class: type[T], data: dict[str, Any]) -> T:
        try:
            return model_class(**data)
        except Exception:
            # Use mixin's filter method
            filtered_data = self._filter_data_for_model(model_class, data)
            return model_class(**filtered_data)

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__tablename__"):
            return model_class.__tablename__  # type: ignore[attr-defined, no-any-return]
        # Check for __collection_name__ attribute first
        if hasattr(model_class, "__collection_name__"):
            return model_class.__collection_name__  # type: ignore[attr-defined, no-any-return]

        # Check for modern get_collection_name method (Pydantic v2+ recommended)
        if hasattr(model_class, "get_collection_name") and callable(
            model_class.get_collection_name,
        ):
            return model_class.get_collection_name()  # type: ignore[attr-defined, no-any-return]

        # Legacy support for deprecated Config class (to be removed in Pydantic v3)
        if hasattr(model_class, "Config") and hasattr(
            model_class.Config,  # type: ignore[attr-defined]
            "collection_name",
        ):
            return model_class.Config.collection_name  # type: ignore[attr-defined, no-any-return]

        # Check model_config for collection_name
        if hasattr(model_class, "model_config") and isinstance(
            model_class.model_config,  # type: ignore[attr-defined]
            dict,
        ):
            return str(
                model_class.model_config.get(  # type: ignore[attr-defined]
                    "collection_name",
                    getattr(model_class, "__name__", "unknown").lower(),
                ),
            )  # type: ignore[no-any-return]

        # Use mixin's fallback implementation
        return super().get_entity_name(model_class)  # type: ignore[return-value]

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        field_mapping = {}
        if hasattr(model_class, "model_fields"):
            field_mapping = self._extract_field_mapping_from_fields(
                model_class.model_fields.items(),  # type: ignore[attr-defined]
            )
        elif hasattr(model_class, "__fields__"):
            field_mapping = self._extract_field_mapping_from_fields(
                model_class.__fields__.items(),  # type: ignore[attr-defined]
            )
        elif hasattr(model_class, "__annotations__"):
            # Use mixin's implementation
            field_mapping = super().get_field_mapping(model_class)
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
            # Use mixin's filter method
            filtered_data = self._filter_data_for_model(model_class, data)
            temp_instance = model_class(**filtered_data)
            return self.serialize(temp_instance)

    def get_primary_key_field(self, model_class: type[T]) -> str:
        config_pk = self._get_configured_primary_key(model_class)
        if config_pk:
            return config_pk

        # Use mixin's fallback implementation
        return super().get_primary_key_field(model_class)

    def _get_configured_primary_key(self, model_class: type[T]) -> str | None:
        # Check for modern get_primary_key method (Pydantic v2+ recommended)
        if hasattr(model_class, "get_primary_key") and callable(
            model_class.get_primary_key,
        ):
            return model_class.get_primary_key()  # type: ignore[attr-defined, no-any-return]

        # Legacy support for deprecated Config class (to be removed in Pydantic v3)
        if hasattr(model_class, "Config") and hasattr(
            model_class.Config,  # type: ignore[attr-defined]
            "primary_key",
        ):
            return model_class.Config.primary_key  # type: ignore[attr-defined, no-any-return]

        # Check model_config for primary_key
        if hasattr(model_class, "model_config") and isinstance(
            model_class.model_config,  # type: ignore[attr-defined]
            dict,
        ):
            return model_class.model_config.get("primary_key")  # type: ignore[attr-defined, no-any-return]

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
                    return str(field_name)  # type: ignore[no-any-return]

        return "id"  # type: ignore[return-value]

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        if hasattr(model_class, "model_fields"):
            field_info = model_class.model_fields.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                return self._unwrap_optional_type(field_info.annotation)  # type: ignore[no-any-return]
        elif hasattr(model_class, "__fields__"):
            field_info = model_class.__fields__.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                field_type = getattr(
                    field_info,
                    "annotation",
                    getattr(field_info, "type_", Any),
                )
                return self._unwrap_optional_type(field_type)  # type: ignore[no-any-return]
        elif hasattr(model_class, "__annotations__"):
            # Use mixin's implementation
            return super().get_field_type(model_class, field_name)
        return Any  # type: ignore[return-value, no-any-return]

    def _unwrap_optional_type(self, field_type: Any) -> type:
        origin = get_origin(field_type)
        if origin is Union or (
            hasattr(field_type, "__class__")
            and field_type.__class__.__name__ == "UnionType"
        ):
            args = get_args(field_type)
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return non_none_args[0]  # type: ignore[return-value, no-any-return]
        return field_type  # type: ignore[return-value, no-any-return]

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
    ) -> type[BaseModel] | None:  # type: ignore[name-defined]
        field_type = self.get_field_type(model_class, field_name)

        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]) and issubclass(args[0], BaseModel):
                    return args[0]  # type: ignore[no-any-return]

        if inspect.isclass(field_type) and issubclass(field_type, BaseModel):
            return field_type  # type: ignore[no-any-return]

        return None
