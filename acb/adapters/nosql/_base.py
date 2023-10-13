from acb.config import Settings
import typing as t


class NosqlBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["models"]


class NosqlBase:
    ...
