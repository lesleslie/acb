from gcsfs.core import GCSFileSystem
from . import StorageBase
from . import StorageBaseSettings
import typing as t


class StorageSettings(StorageBaseSettings):
    ...


class Storage(StorageBase):
    client: t.Any = GCSFileSystem


storage = Storage()
