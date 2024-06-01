import typing as t

from acb.adapters import AdapterBase
from acb.config import Settings


class NosqlBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["models"]


class NosqlBase(AdapterBase): ...
