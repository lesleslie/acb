import typing as t
from contextvars import ContextVar
from importlib import import_module
from inspect import isclass

from acb import base_path
from acb.adapters import get_installed_adapters
from acb.depends import depends
from aiopath import AsyncPath
from sqlmodel import SQLModel
from ._base import ModelsBase
from ._base import ModelsBaseSettings

imported_models: ContextVar[list[t.Any]] = ContextVar("imported_models", default=[])

base_models_paths = [AsyncPath(base_path / p) for p in ("models", "models.py")]


class ModelsSettings(ModelsBaseSettings): ...


class Models(ModelsBase):
    async def import_models(self, path: AsyncPath) -> None:
        depth = -2
        if "adapters" in path.parts:
            depth = -5
        module_path = ".".join(path.parts[depth:]).removesuffix(".py")
        module = import_module(module_path)
        _imported_models = []
        for name, model in {
            n: m
            for n, m in vars(module).items()
            if isclass(m)
            and issubclass(m, SQLModel)
            and hasattr(m, "__table__")
            and n not in imported_models.get()
        }.items():
            setattr(self.sql, name, model)
            _imported_models.append(name)
            self.logger.debug(f"{name} model imported")
        imported_models.get().extend(_imported_models)

    async def init(self) -> None:
        SQLModel.metadata.clear()
        self.logger.info("Importing models...")
        adapter_paths = []
        for adapter in get_installed_adapters():
            model_paths = [
                p
                async for p in adapter.path.parent.iterdir()
                if p.name.startswith("_models")
            ]
            adapter_paths.extend(model_paths)
        for path in [p for p in adapter_paths + base_models_paths if await p.exists()]:
            if await path.is_dir():
                for _path in [
                    s
                    async for s in path.iterdir()
                    if s.suffix == ".py"
                    and await s.is_file()
                    and not s.stem.startswith("_")
                ]:
                    await self.import_models(_path)
            elif await path.is_file():
                await self.import_models(path)
        self.logger.info(f"{len(imported_models.get())} models imported")


depends.set(Models)
