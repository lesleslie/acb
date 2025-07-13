"""SQLModel Adapter for Universal Query Interface.

This module implements the ModelAdapter protocol for SQLModel models,
allowing the universal query interface to work with SQLModel classes.
"""

from __future__ import annotations

import inspect
from typing import Any, TypeVar, get_args, get_origin

from acb.adapters.models._base import ModelsBaseSettings
from acb.adapters.models._query import ModelAdapter

try:
    from sqlmodel import SQLModel as SQLModelBase

    SQLModel = SQLModelBase  # type: ignore[misc]
    _sqlmodel_available = True
except ImportError:
    _sqlmodel_available = False

    class SQLModel:  # type: ignore[misc]
        pass


SQLMODEL_AVAILABLE = _sqlmodel_available

T = TypeVar("T", bound=SQLModel)


class SQLModelAdapter(ModelAdapter[T]):
    def __init__(self) -> None:
        if not SQLMODEL_AVAILABLE:
            msg = "SQLModel is required for SQLModelAdapter"
            raise ImportError(msg)

    def serialize(self, instance: T) -> dict[str, Any]:
        if hasattr(instance, "model_dump"):
            return instance.model_dump()  # type: ignore[attr-defined]
        if hasattr(instance, "dict"):
            return instance.dict()  # type: ignore[attr-defined]
        return self._manual_serialize(instance)

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        result = {}
        if hasattr(instance, "__fields__"):
            for field_name in instance.__fields__:  # type: ignore[attr-defined]
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
        if isinstance(value, SQLModel):
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
            model_fields = set(model_class.model_fields.keys())  # type: ignore[attr-defined]
        elif hasattr(model_class, "model_fields"):
            model_fields = set(model_class.model_fields.keys())  # type: ignore[attr-defined]
        else:
            return data

        return {k: v for k, v in data.items() if k in model_fields}

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__tablename__"):
            return model_class.__tablename__  # type: ignore[attr-defined]
        if hasattr(model_class, "__table__") and hasattr(
            model_class.__table__,  # type: ignore[attr-defined]
            "name",
        ):
            return model_class.__table__.name  # type: ignore[attr-defined]
        return model_class.__name__.lower()

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        if hasattr(model_class, "model_fields"):
            return self._extract_field_mapping_from_fields(
                model_class.model_fields.items()  # type: ignore[attr-defined]
            )
        elif hasattr(model_class, "__fields__"):
            return self._extract_field_mapping_from_fields(
                model_class.__fields__.items()  # type: ignore[attr-defined]
            )
        elif hasattr(model_class, "__annotations__"):
            return {name: name for name in model_class.__annotations__}

        return {}

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
        table_pk = self._get_table_primary_key(model_class)
        if table_pk:
            return table_pk

        return self._find_common_primary_key_field(model_class)

    def _get_table_primary_key(self, model_class: type[T]) -> str | None:
        if hasattr(model_class, "__table__"):
            for column in model_class.__table__.columns:  # type: ignore[attr-defined]
                if column.primary_key:
                    return column.name
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
        if hasattr(model_class, "__fields__"):
            field_info = model_class.__fields__.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                return field_info.type_
        elif hasattr(model_class, "model_fields"):
            field_info = model_class.model_fields.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                return field_info.annotation
        elif hasattr(model_class, "__annotations__"):
            return model_class.__annotations__.get(field_name, Any)  # type: ignore[return-value]

        return Any  # type: ignore[return-value]

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        if hasattr(model_class, "__table__"):
            if hasattr(model_class.__table__.columns, field_name):  # type: ignore[attr-defined]
                column = getattr(model_class.__table__.columns, field_name)  # type: ignore[attr-defined]
                return bool(column.foreign_keys)
        field_type = self.get_field_type(model_class, field_name)
        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and issubclass(args[0], SQLModel):
                    return True
        return bool(inspect.isclass(field_type) and issubclass(field_type, SQLModel))


class ModelsSettings(ModelsBaseSettings): ...
