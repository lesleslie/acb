import typing as t

from acb.depends import depends
from gcsfs.core import GCSFileSystem
from ._base import StorageBase
from ._base import StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    ...


class Storage(StorageBase):
    client: t.Any = GCSFileSystem


depends.set(Storage, Storage())
