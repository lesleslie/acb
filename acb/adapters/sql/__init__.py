from _model import SqlModel
from acb import load_adapter

__all__: list[str] = ["Sql", "SqlModel"]

Sql = load_adapter()
