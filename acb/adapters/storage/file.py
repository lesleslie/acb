import typing as t
from functools import cached_property

from fsspec.asyn import AsyncFileSystem
from fsspec.implementations.dirfs import DirFileSystem
from acb.depends import depends
from ._base import StorageBase, StorageBaseSettings


class StorageSettings(StorageBaseSettings): ...


class Storage(StorageBase):
    file_system: t.Any = DirFileSystem

    @cached_property
    def client(self) -> AsyncFileSystem:
        return self.file_system(path=self.config.storage.local_path, asynchronous=True)


depends.set(Storage)
