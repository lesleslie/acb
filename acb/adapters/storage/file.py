import typing as t
from functools import cached_property

from fsspec.asyn import AsyncFileSystem
from fsspec.implementations.asyn_wrapper import AsyncFileSystemWrapper
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.local import LocalFileSystem
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings


class StorageSettings(StorageBaseSettings): ...


class Storage(StorageBase):
    file_system: t.Any = DirFileSystem

    @cached_property
    def client(self) -> AsyncFileSystem:
        fs = LocalFileSystem(auto_mkdir=True, asynchronous=False)
        dirfs = self.file_system(path=str(self.config.storage.local_path), fs=fs)
        return AsyncFileSystemWrapper(dirfs)


depends.set(Storage)
