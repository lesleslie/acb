from __future__ import annotations

import inspect

import typing as t
from typing import Any, TypeVar, get_args, get_origin

from acb.config import AdapterBase, Settings

__all__ = [
    "ModelAdapterMixin",
    "ModelsBase",
    "ModelsBaseSettings",
    "ModelsProtocol",
    "T",
]


class ModelsBaseSettings(Settings):
    sqlmodel: bool = True
    sqlalchemy: bool = True
    pydantic: bool = True
    redis_om: bool = False
    msgspec: bool = True
    attrs: bool = False


class ModelsProtocol(t.Protocol):
    sql: t.Any
    nosql: t.Any

    class SqlModels:
        def __getattr__(self, name: str) -> t.Any: ...

    class NosqlModels:
        def __getattr__(self, name: str) -> t.Any: ...


class ModelsBase(AdapterBase):
    class SqlModels:
        def __getattr__(self, name: str) -> t.Any: ...

    sql = SqlModels()

    class NosqlModels:
        def __getattr__(self, name: str) -> t.Any: ...

    nosql = NosqlModels()


# ============================================================================
# Model Adapter Base Class and Mixins
# ============================================================================

T = TypeVar("T")


class ModelAdapterMixin:
    """Provides common functionality for model adapters across different libraries.

    This mixin implements shared methods that are common across all model adapters,
    reducing code duplication while allowing each adapter to implement library-specific
    behavior for core operations like serialization and type introspection.
    """

    def _serialize_value(self, value: Any) -> Any:
        """Recursively serialize a value, handling nested models and collections."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}

        # Try to serialize nested model objects
        if hasattr(value, "__dict__") or hasattr(value, "__slots__"):
            return self._serialize_model_object(value)

        return value

    def _serialize_model_object(self, value: Any) -> Any:
        """Serialize a model object by checking for common serialization patterns."""
        # Try to get a dict representation by checking common patterns
        try:
            if hasattr(value, "model_dump"):
                return value.model_dump()
            if hasattr(value, "dict"):
                return value.dict()
            if hasattr(value, "__dict__"):
                return value.__dict__
            # Fallback to basic representation
            return str(value)
        except Exception:
            return str(value)

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        """Default manual serialization for when library-specific serialization isn't available."""
        result = {}
        # Look for common attributes across model types
        for attr_name in dir(instance):
            if not attr_name.startswith("_") and not callable(
                getattr(instance, attr_name, None),
            ):
                try:
                    value = getattr(instance, attr_name)
                    result[attr_name] = self._serialize_value(value)
                except (AttributeError, TypeError, ValueError):
                    continue
        return result

    def _filter_data_for_model(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Filter data to only include fields that exist in the model class."""
        # Common approach: if model has annotations, use those
        if hasattr(model_class, "__annotations__"):
            model_fields = set(model_class.__annotations__.keys())
            return {k: v for k, v in data.items() if k in model_fields}

        # Fallback: return data as-is
        return data

    def get_entity_name(self, model_class: type[T]) -> str:
        """Get the entity name for the model class with standard fallbacks."""
        if hasattr(model_class, "__tablename__"):
            return str(model_class.__tablename__)  # type: ignore[attr-defined]
        if hasattr(model_class, "__collection_name__"):
            return str(model_class.__collection_name__)  # type: ignore[attr-defined]

        # Fallback to class name
        return str(getattr(model_class, "__name__", "unknown").lower())

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        """Get field mapping based on annotations if available."""
        field_mapping = {}
        if hasattr(model_class, "__annotations__"):
            field_mapping = {name: name for name in model_class.__annotations__}
        return field_mapping

    def validate_data(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate data by attempting to create and serialize an instance."""
        from contextlib import suppress

        with suppress(Exception):
            # Try to create a temporary instance using the adapter's method
            if hasattr(self, "deserialize_to_class"):
                temp_instance = self.deserialize_to_class(model_class, data)  # type: ignore[attr-defined]
                if hasattr(self, "serialize"):
                    return self.serialize(temp_instance)  # type: ignore[attr-defined]

        # Fallback: filter data and return
        return self._filter_data_for_model(model_class, data)

    def get_primary_key_field(self, model_class: type[T]) -> str:
        """Get the primary key field with standard fallbacks."""
        common_pk_names = ["id", "pk", "primary_key", "_id"]

        # Check annotations first
        if hasattr(model_class, "__annotations__"):
            for field_name in model_class.__annotations__:
                if field_name in common_pk_names:
                    return field_name

        # Fallback to default
        return "id"

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        """Get the field type with standard fallback."""
        if hasattr(model_class, "__annotations__"):
            annotation = model_class.__annotations__.get(field_name, Any)
            return annotation if annotation is not Any else type(Any)

        return Any  # type: ignore[return-value]

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        """Check if a field is a relationship field."""
        field_type = self.get_field_type(model_class, field_name)
        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]):
                    # This is a simplified check - actual implementation would depend on the specific adapter
                    return True
        return False

    def get_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type | None:
        """Get the nested model class if the field is a relationship."""
        field_type = self.get_field_type(model_class, field_name)

        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]):
                    return args[0]

        if inspect.isclass(field_type):
            return field_type

        return None
