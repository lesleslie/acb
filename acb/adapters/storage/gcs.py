from gcsfs.core import GCSFileSystem
from . import StorageBase
from . import StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    ...


class Storage(StorageBase):
    client: GCSFileSystem = GCSFileSystem


storage = Storage()
