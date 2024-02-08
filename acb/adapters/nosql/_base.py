from acb.config import Settings
import typing as t
from acb.adapters import AdapterBase


class NosqlBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["models"]


class NosqlBase(AdapterBase): ...
