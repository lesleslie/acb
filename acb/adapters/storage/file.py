import typing as t
from functools import cached_property

from acb.depends import depends
from fsspec.asyn import AsyncFileSystem
from fsspec.implementations.dirfs import DirFileSystem
from ._base import StorageBase
from ._base import StorageBaseSettings


class StorageSettings(StorageBaseSettings): ...


class Storage(StorageBase):
    file_system: t.Any = DirFileSystem

    @cached_property
    def client(self) -> AsyncFileSystem:
        return self.file_system(path=self.config.storage.local_path, asynchronous=True)


depends.set(Storage)
