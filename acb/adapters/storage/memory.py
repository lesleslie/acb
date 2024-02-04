import typing as t

from acb.depends import depends
from fsspec.implementations.memory import MemoryFileSystem
from ._base import StorageBase
from ._base import StorageBaseSettings


class StorageSettings(StorageBaseSettings): ...


class Storage(StorageBase):
    file_system: t.Any = MemoryFileSystem


depends.set(Storage)
