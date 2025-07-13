"""Models Adapter Package.

This package provides model adapters for different frameworks:
- pydantic: Pydantic model adapter for universal query interface
- sqlmodel: SQLModel adapter for universal query interface

Internal modules (prefixed with _):
- _query: Core query interface protocols and classes
- _hybrid: Hybrid query interface supporting multiple styles
- _repository: Repository pattern implementation
- _specification: Specification pattern implementation
- _base: Base classes and protocols
"""

from contextlib import suppress
from typing import Any

from acb.adapters.models._attrs import AttrsModelAdapter
from acb.adapters.models._base import ModelsBase, ModelsBaseSettings
from acb.adapters.models._msgspec import MsgspecModelAdapter
from acb.adapters.models._pydantic import PydanticModelAdapter
from acb.adapters.models._redis_om import RedisOMModelAdapter
from acb.adapters.models._sqlalchemy import SQLAlchemyModelAdapter
from acb.adapters.models._sqlmodel import SQLModelAdapter

__all__ = [
    "ModelsAdapter",
    "ModelsSettings",
    "PydanticModelAdapter",
    "SQLModelAdapter",
    "SQLAlchemyModelAdapter",
]


class ModelsSettings(ModelsBaseSettings): ...


class ModelsAdapter(ModelsBase):
    def __init__(self) -> None:
        super().__init__()
        self._pydantic_adapter: PydanticModelAdapter[Any] | None = None
        self._sqlmodel_adapter: SQLModelAdapter[Any] | None = None
        self._sqlalchemy_adapter: SQLAlchemyModelAdapter[Any] | None = None
        self._redis_om_adapter: RedisOMModelAdapter[Any] | None = None
        self._msgspec_adapter: MsgspecModelAdapter[Any] | None = None
        self._attrs_adapter: AttrsModelAdapter[Any] | None = None

    def _get_pydantic_adapter(self) -> PydanticModelAdapter[Any]:
        if self._pydantic_adapter is None:
            self._pydantic_adapter = PydanticModelAdapter[Any]()
        return self._pydantic_adapter

    def _get_sqlmodel_adapter(self) -> SQLModelAdapter[Any]:
        if self._sqlmodel_adapter is None:
            self._sqlmodel_adapter = SQLModelAdapter[Any]()
        return self._sqlmodel_adapter

    def _get_sqlalchemy_adapter(self) -> SQLAlchemyModelAdapter[Any]:
        if self._sqlalchemy_adapter is None:
            self._sqlalchemy_adapter = SQLAlchemyModelAdapter[Any]()
        return self._sqlalchemy_adapter

    def _get_msgspec_adapter(self) -> MsgspecModelAdapter[Any]:
        if self._msgspec_adapter is None:
            self._msgspec_adapter = MsgspecModelAdapter[Any]()
        return self._msgspec_adapter

    def _get_attrs_adapter(self) -> AttrsModelAdapter[Any]:
        if self._attrs_adapter is None:
            self._attrs_adapter = AttrsModelAdapter[Any]()
        return self._attrs_adapter

    def _get_redis_om_adapter(self) -> RedisOMModelAdapter[Any]:
        if self._redis_om_adapter is None:
            self._redis_om_adapter = RedisOMModelAdapter[Any]()
        return self._redis_om_adapter

    def auto_detect_model_type(self, model_class: type[Any]) -> str:
        with suppress(ImportError):
            from sqlmodel import SQLModel

            if issubclass(model_class, SQLModel):
                return "sqlmodel"
        with suppress(ImportError):
            from sqlalchemy.orm.decl_api import DeclarativeMeta

            if hasattr(model_class, "__table__") or (
                hasattr(model_class, "__mro__")
                and any(
                    isinstance(base, DeclarativeMeta) for base in model_class.__mro__
                )
            ):
                return "sqlalchemy"
        with suppress(ImportError):
            from pydantic import BaseModel

            if issubclass(model_class, BaseModel):
                return "pydantic"
        with suppress(ImportError):
            from redis_om import HashModel

            if issubclass(model_class, HashModel):
                return "redis_om"
        with suppress(ImportError):
            import msgspec

            if issubclass(model_class, msgspec.Struct):
                return "msgspec"
        with suppress(ImportError):
            import attrs

            if attrs.has(model_class):
                return "attrs"

        return "pydantic"

    def get_adapter_for_model(
        self, model_class: type[Any]
    ) -> (
        PydanticModelAdapter[Any]
        | SQLModelAdapter[Any]
        | SQLAlchemyModelAdapter[Any]
        | MsgspecModelAdapter[Any]
        | AttrsModelAdapter[Any]
        | RedisOMModelAdapter[Any]
    ):
        model_type = self.auto_detect_model_type(model_class)

        if model_type == "sqlmodel":
            return self._get_sqlmodel_adapter()
        elif model_type == "sqlalchemy":
            return self._get_sqlalchemy_adapter()
        elif model_type == "pydantic":
            return self._get_pydantic_adapter()
        elif model_type == "redis_om":
            return self._get_redis_om_adapter()
        elif model_type == "msgspec":
            return self._get_msgspec_adapter()
        elif model_type == "attrs":
            return self._get_attrs_adapter()

        return self._get_pydantic_adapter()
