import typing as t

from acb.config import AdapterBase, Settings


class NosqlBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["models"]


class NosqlBase(AdapterBase): ...
