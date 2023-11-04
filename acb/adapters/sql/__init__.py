from acb.adapters import load_adapter
from ._base import SqlModel
from ._base import SqlModels

Sql = load_adapter()

__all__: list[str] = [
    "Sql",
    "SqlModel",
    "SqlModels",
]
