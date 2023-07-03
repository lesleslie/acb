from acb.config import Settings
from acb.config import load_adapter
import typing as t


class StorageBaseSettings(Settings):
    cloud: str
    buckets: t.Optional[dict[str, str]] = None


class StorageBase:
    ...


storage = load_adapter("storage")
