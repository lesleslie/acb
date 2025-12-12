"""Models Adapter Package.

This package provides simple model adapters for different frameworks:
- pydantic: Pydantic model adapter
- sqlmodel: SQLModel adapter
- sqlalchemy: SQLAlchemy adapter
- attrs: Attrs model adapter
- msgspec: Msgspec model adapter
- redis_om: Redis OM adapter

Clean architecture focusing on basic model operations with Services layer available for complex enterprise features.
"""

import warnings
from functools import lru_cache

from contextlib import suppress
from typing import Any

from acb.adapters.models._attrs import AttrsModelAdapter
from acb.adapters.models._base import ModelsBase, ModelsBaseSettings
from acb.adapters.models._msgspec import MsgspecModelAdapter
from acb.adapters.models._pydantic import PydanticModelAdapter

# Suppress Pydantic deprecation warnings from redis_om
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="redis_om")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")
    from acb.adapters.models._redis_om import RedisOMModelAdapter

from acb.adapters.models._hybrid import ACBQuery

# Import query interface components
from acb.adapters.models._query import (
    DatabaseAdapter,
    ModelAdapter,
    QueryRegistry,
    registry,
)
from acb.adapters.models._sqlalchemy import SQLAlchemyModelAdapter
from acb.adapters.models._sqlmodel import SQLModelAdapter

__all__ = [
    # Query interface exports
    "ACBQuery",
    "DatabaseAdapter",
    "ModelAdapter",
    # Base classes and mixins
    "ModelAdapterMixin",
    "ModelsAdapter",
    "ModelsSettings",
    "PydanticModelAdapter",
    "QueryRegistry",
    "SQLAlchemyModelAdapter",
    "SQLModelAdapter",
    "registry",
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
            self._pydantic_adapter = PydanticModelAdapter[Any]()  # type: ignore[no-untyped-call]
        return self._pydantic_adapter

    def _get_sqlmodel_adapter(self) -> SQLModelAdapter[Any]:
        if self._sqlmodel_adapter is None:
            self._sqlmodel_adapter = SQLModelAdapter[Any]()  # type: ignore[no-untyped-call]
        return self._sqlmodel_adapter

    def _get_sqlalchemy_adapter(self) -> SQLAlchemyModelAdapter[Any]:
        if self._sqlalchemy_adapter is None:
            self._sqlalchemy_adapter = SQLAlchemyModelAdapter[Any]()  # type: ignore[no-untyped-call]
        return self._sqlalchemy_adapter

    def _get_msgspec_adapter(self) -> MsgspecModelAdapter[Any]:
        if self._msgspec_adapter is None:
            self._msgspec_adapter = MsgspecModelAdapter[Any]()  # type: ignore[no-untyped-call]
        return self._msgspec_adapter

    def _get_attrs_adapter(self) -> AttrsModelAdapter[Any]:
        if self._attrs_adapter is None:
            self._attrs_adapter = AttrsModelAdapter[Any]()  # type: ignore[no-untyped-call]
        return self._attrs_adapter

    def _get_redis_om_adapter(self) -> RedisOMModelAdapter[Any]:
        if self._redis_om_adapter is None:
            self._redis_om_adapter = RedisOMModelAdapter[Any]()  # type: ignore[no-untyped-call]
        return self._redis_om_adapter

    def auto_detect_model_type(self, model_class: type[Any]) -> str:
        """Auto-detect model type with performance optimization.

        Uses cached detection to avoid repeated imports and type checking.
        """
        return _cached_auto_detect_model_type(model_class)

    def _detect_model_type_uncached(self, model_class: type[Any]) -> str:
        """Uncached model type detection for internal use."""
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
                from redis_om import HashModel  # type: ignore[import-not-found]

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
        self,
        model_class: type[Any],
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
        if model_type == "sqlalchemy":
            return self._get_sqlalchemy_adapter()
        if model_type == "pydantic":
            return self._get_pydantic_adapter()
        if model_type == "redis_om":
            return self._get_redis_om_adapter()
        if model_type == "msgspec":
            return self._get_msgspec_adapter()
        if model_type == "attrs":
            return self._get_attrs_adapter()

        return self._get_pydantic_adapter()


# Cache for model type detection using model class ID as key
@lru_cache(maxsize=512)
def _cached_auto_detect_model_type(model_class: type[Any]) -> str:
    """Cached model type detection to avoid repeated imports.

    This function caches the result of model type detection to avoid
    repeated expensive imports and subclass checks.

    Args:
        model_class: The model class to detect type for

    Returns:
        The detected model type as string
    """
    # Create a temporary instance to access the detection method
    # Note: This is a performance optimization that trades a small
    # instantiation cost for much faster subsequent lookups
    temp_adapter = ModelsAdapter()  # type: ignore[no-untyped-call]
    return temp_adapter._detect_model_type_uncached(model_class)
