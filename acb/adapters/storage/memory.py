import typing as t

from fsspec.implementations.memory import MemoryFileSystem
from acb.depends import depends
from ._base import StorageBase, StorageBaseSettings


class StorageSettings(StorageBaseSettings): ...


class Storage(StorageBase):
    file_system: t.Any = MemoryFileSystem


depends.set(Storage)
