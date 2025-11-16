"""SQLAlchemy Model Adapter for Universal Query Interface.

This module implements the ModelAdapter protocol for SQLAlchemy models,
allowing the universal query interface to work with SQLAlchemy declarative classes.
"""

import inspect

import typing as t
from contextlib import suppress
from typing import Any, TypeVar, get_args, get_origin

from acb.adapters.models._attrs import ModelAdapter

# Conditional imports for SQLAlchemy with proper fallbacks
_sqlalchemy_available = False
sqlalchemy_inspect = None
_Base = None
SQLAlchemyBase = None
DeclarativeMeta = None

try:
    from sqlalchemy import inspect as sqlalchemy_inspect
    from sqlalchemy.orm import DeclarativeBase, declarative_base
    from sqlalchemy.orm.decl_api import DeclarativeMeta as SQLAlchemyDeclarativeMeta

    _sqlalchemy_available = True

    # Handle DeclarativeMeta
    DeclarativeMeta = SQLAlchemyDeclarativeMeta

    # Handle _Base with fallback
    try:
        _Base = DeclarativeBase
    except (ImportError, AttributeError):
        _Base = declarative_base()

    # Handle SQLAlchemyBase
    SQLAlchemyBase = _Base

except ImportError:
    _sqlalchemy_available = False
    sqlalchemy_inspect = None

    class FallbackSQLAlchemyBase:
        pass

    class FallbackDeclarativeMeta:
        pass

    # Assign fallbacks
    SQLAlchemyBase = FallbackSQLAlchemyBase  # type: ignore[assignment]
    DeclarativeMeta = FallbackDeclarativeMeta  # type: ignore[assignment]
    _Base = FallbackSQLAlchemyBase  # type: ignore[assignment]


SQLALCHEMY_AVAILABLE = _sqlalchemy_available

T = TypeVar("T")


class SQLAlchemyModelAdapter(ModelAdapter[T]):
    def __init__(self) -> None:
        if not SQLALCHEMY_AVAILABLE:
            msg = "SQLAlchemy is required for SQLAlchemyModelAdapter"
            raise ImportError(msg)

    def serialize(self, instance: T) -> dict[str, Any]:
        if not SQLALCHEMY_AVAILABLE:
            return {}

        try:
            return self._attempt_sqlalchemy_serialization(instance)
        except Exception:
            return self._manual_serialize(instance)

    def _attempt_sqlalchemy_serialization(self, instance: T) -> dict[str, Any]:
        result = {}
        if sqlalchemy_inspect is not None:
            mapper = sqlalchemy_inspect(instance.__class__)
            if mapper is not None:
                for column in mapper.columns:  # type: ignore[union-attr]
                    if hasattr(instance, column.name):
                        value = getattr(instance, column.name)
                        result[column.name] = self._serialize_value(value)
        else:
            result = self._manual_serialize(instance)
        return result

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        result = {}
        if hasattr(instance, "__table__"):
            for column in instance.__table__.columns:  # type: ignore  # type: ignore[attr-defined]
                if hasattr(instance, column.name):
                    value = getattr(instance, column.name)
                    result[column.name] = self._serialize_value(value)
        else:
            for attr_name in dir(instance):
                if not attr_name.startswith(
                    ("_", "metadata", "registry"),
                ) and not callable(getattr(instance, attr_name)):
                    try:
                        value = getattr(instance, attr_name)
                        result[attr_name] = self._serialize_value(value)
                    except (AttributeError, TypeError, ValueError):
                        continue

        return result

    def _serialize_value(self, value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "__table__") or (
            hasattr(value, "__class__") and self._is_sqlalchemy_model(value.__class__)
        ):
            return self.serialize(value)
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        try:
            if hasattr(value, "python_type"):
                return value
            return value
        except Exception:
            return str(value)

    def deserialize(self, data: dict[str, Any]) -> T:
        msg = "Deserialize requires specific model class context"
        raise NotImplementedError(msg)

    def deserialize_to_class(self, model_class: type[T], data: dict[str, Any]) -> T:
        try:
            filtered_data = self._filter_data_for_model(model_class, data)
            return model_class(**filtered_data)
        except Exception:
            return model_class(**data)

    def _filter_data_for_model(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if not hasattr(model_class, "__table__"):
            return data

        valid_columns = {column.name for column in model_class.__table__.columns}  # type: ignore  # type: ignore[attr-defined]
        return {k: v for k, v in data.items() if k in valid_columns}

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__tablename__"):
            return model_class.__tablename__  # type: ignore  # type: ignore[attr-defined]
        if hasattr(model_class, "__table__") and hasattr(model_class.__table__, "name"):  # type: ignore  # type: ignore[attr-defined]
            return model_class.__table__.name  # type: ignore  # type: ignore[attr-defined]

        return model_class.__name__.lower()  # type: ignore[attr-defined, no-any-return]

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        field_mapping = {}
        if hasattr(model_class, "__table__"):
            for column in model_class.__table__.columns:  # type: ignore  # type: ignore[attr-defined]
                field_mapping[column.name] = column.name
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
            return self._filter_data_for_model(model_class, data)

    def get_primary_key_field(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__table__"):
            for column in model_class.__table__.columns:  # type: ignore  # type: ignore[attr-defined]
                if column.primary_key:
                    return str(column.name)
        if hasattr(model_class, "__annotations__"):
            for field_name in model_class.__annotations__:
                if field_name in ("id", "pk", "primary_key", "_id"):
                    return field_name  # type: ignore[no-any-return]

        return "id"

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        if hasattr(model_class, "__table__"):
            for column in model_class.__table__.columns:  # type: ignore  # type: ignore[attr-defined]
                if column.name == field_name:
                    try:
                        return t.cast("type", column.type.python_type)  # type: ignore[no-any-return, return-value]
                    except Exception:
                        return Any  # type: ignore[return-value]
        if hasattr(model_class, "__annotations__"):
            annotation = model_class.__annotations__.get(field_name, Any)
            return t.cast("type", annotation)  # type: ignore[no-any-return, return-value]

        return Any  # type: ignore[return-value]

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        if not SQLALCHEMY_AVAILABLE or sqlalchemy_inspect is None:
            return False

        # Try direct inspection first
        with suppress(Exception):
            mapper = sqlalchemy_inspect(model_class)
            if mapper is not None and hasattr(mapper, "relationships"):
                return field_name in mapper.relationships

        # Fall back to field type analysis
        return self._analyze_field_type_for_relationship(model_class, field_name)

    def _analyze_field_type_for_relationship(
        self,
        model_class: type[T],
        field_name: str,
    ) -> bool:
        field_type = self.get_field_type(model_class, field_name)
        if hasattr(field_type, "__origin__"):
            origin = get_origin(field_type)
            if origin is list:
                args = get_args(field_type)
                if args and inspect.isclass(args[0]):
                    return self._is_sqlalchemy_model(args[0])

        return bool(
            inspect.isclass(field_type) and self._is_sqlalchemy_model(field_type),
        )

    def get_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type | None:
        if not SQLALCHEMY_AVAILABLE or sqlalchemy_inspect is None:
            return None

        # Try direct inspection first
        direct_result = self._inspect_nested_model_class(model_class, field_name)
        if direct_result is not None:
            return direct_result

        # Fall back to field type analysis
        return self._analyze_field_type_for_nested_model(model_class, field_name)

    def _inspect_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type | None:
        if sqlalchemy_inspect is None:
            return None

        with suppress(AttributeError, TypeError, ValueError):
            mapper = sqlalchemy_inspect(model_class)
            if mapper is not None and hasattr(mapper, "relationships"):
                if field_name in mapper.relationships:
                    relationship = mapper.relationships[field_name]
                    if hasattr(relationship, "mapper") and hasattr(
                        relationship.mapper,
                        "class_",
                    ):
                        return t.cast("type", relationship.mapper.class_)  # type: ignore[no-any-return, return-value]
        return None

    def _analyze_field_type_for_nested_model(
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
                    and self._is_sqlalchemy_model(args[0])
                ):
                    return args[0]

        if inspect.isclass(field_type) and self._is_sqlalchemy_model(field_type):
            return field_type

        return None

    def _is_sqlalchemy_model(self, model_class: type) -> bool:
        if not SQLALCHEMY_AVAILABLE:
            return False
        if hasattr(model_class, "__table__"):
            return True
        if hasattr(model_class, "__mro__"):
            for base in model_class.__mro__:
                if isinstance(base, t.cast("type", DeclarativeMeta)):  # type: ignore[arg-type]
                    return True

        return False
