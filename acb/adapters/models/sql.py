from importlib import import_module

from sqlmodel import SQLModel

from acb import pkg_path
from acb.adapters.models._base import ModelsBase
from acb.adapters.models._base import ModelsBaseSettings
from acb.depends import depends


class ModelsSettings(ModelsBaseSettings):
    ...


class Models(ModelsBase):
    async def init(self) -> None:
        models = import_module(".".join((pkg_path / "models.py").parts[:-2]))
        for model in [
            getattr(models, m) for m in dir(models) if isinstance(m, SQLModel)
        ]:
            setattr(self, model.__name__, model)


depends.set(Models, Models())
