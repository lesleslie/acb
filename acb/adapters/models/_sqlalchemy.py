"""SQLAlchemy Model Adapter for Universal Query Interface.

This module implements the ModelAdapter protocol for SQLAlchemy models,
allowing the universal query interface to work with SQLAlchemy declarative classes.
"""

import inspect
from contextlib import suppress
from typing import Any, TypeVar, get_args, get_origin

from acb.adapters.models._query import ModelAdapter

try:
    from sqlalchemy import inspect as sqlalchemy_inspect
    from sqlalchemy.orm import DeclarativeBase, declarative_base
    from sqlalchemy.orm.decl_api import DeclarativeMeta as SQLAlchemyDeclarativeMeta

    _sqlalchemy_available = True
    DeclarativeMeta = SQLAlchemyDeclarativeMeta  # type: ignore[misc]

    try:
        _Base = DeclarativeBase
    except (ImportError, AttributeError):
        _Base = declarative_base()

    SQLAlchemyBase = _Base  # type: ignore[assignment]

except ImportError:
    _sqlalchemy_available = False
    sqlalchemy_inspect = None  # type: ignore[assignment]

    class SQLAlchemyBase:  # type: ignore[misc]
        pass

    class DeclarativeMeta:  # type: ignore[misc]
        pass


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
        result = {}
        try:
            if sqlalchemy_inspect is not None:
                mapper = sqlalchemy_inspect(instance.__class__)
                for column in mapper.columns:
                    if hasattr(instance, column.name):
                        value = getattr(instance, column.name)
                        result[column.name] = self._serialize_value(value)
            else:
                result = self._manual_serialize(instance)
        except Exception:
            result = self._manual_serialize(instance)

        return result

    def _manual_serialize(self, instance: T) -> dict[str, Any]:
        result = {}
        if hasattr(instance, "__table__"):
            for column in instance.__table__.columns:  # type: ignore[attr-defined]
                if hasattr(instance, column.name):
                    value = getattr(instance, column.name)
                    result[column.name] = self._serialize_value(value)
        else:
            for attr_name in dir(instance):
                if not attr_name.startswith(
                    ("_", "metadata", "registry")
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
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        else:
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

        valid_columns = {column.name for column in model_class.__table__.columns}  # type: ignore[attr-defined]
        return {k: v for k, v in data.items() if k in valid_columns}

    def get_entity_name(self, model_class: type[T]) -> str:
        if hasattr(model_class, "__tablename__"):
            return model_class.__tablename__  # type: ignore[attr-defined]
        if hasattr(model_class, "__table__") and hasattr(model_class.__table__, "name"):  # type: ignore[attr-defined]
            return model_class.__table__.name  # type: ignore[attr-defined]

        return model_class.__name__.lower()

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]:
        field_mapping = {}
        if hasattr(model_class, "__table__"):
            for column in model_class.__table__.columns:  # type: ignore[attr-defined]
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
            for column in model_class.__table__.columns:  # type: ignore[attr-defined]
                if column.primary_key:
                    return column.name
        if hasattr(model_class, "__annotations__"):
            for field_name in model_class.__annotations__:
                if field_name in ("id", "pk", "primary_key", "_id"):
                    return field_name

        return "id"

    def get_field_type(self, model_class: type[T], field_name: str) -> type:
        if hasattr(model_class, "__table__"):
            for column in model_class.__table__.columns:  # type: ignore[attr-defined]
                if column.name == field_name:
                    try:
                        return column.type.python_type
                    except Exception:
                        return Any  # type: ignore[return-value]
        if hasattr(model_class, "__annotations__"):
            return model_class.__annotations__.get(field_name, Any)  # type: ignore[return-value]

        return Any  # type: ignore[return-value]

    def is_relationship_field(self, model_class: type[T], field_name: str) -> bool:
        if not SQLALCHEMY_AVAILABLE or sqlalchemy_inspect is None:
            return False
        try:
            mapper = sqlalchemy_inspect(model_class)
            return field_name in mapper.relationships
        except Exception:
            field_type = self.get_field_type(model_class, field_name)
            if hasattr(field_type, "__origin__"):
                origin = get_origin(field_type)
                if origin is list:
                    args = get_args(field_type)
                    if args and inspect.isclass(args[0]):
                        return self._is_sqlalchemy_model(args[0])

            return bool(
                inspect.isclass(field_type) and self._is_sqlalchemy_model(field_type)
            )

    def get_nested_model_class(
        self,
        model_class: type[T],
        field_name: str,
    ) -> type | None:
        if not SQLALCHEMY_AVAILABLE or sqlalchemy_inspect is None:
            return None

        with suppress(AttributeError, TypeError, ValueError):
            mapper = sqlalchemy_inspect(model_class)
            if field_name in mapper.relationships:
                relationship = mapper.relationships[field_name]
                return relationship.mapper.class_

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
                if isinstance(base, DeclarativeMeta):
                    return True

        return False
