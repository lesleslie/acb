import typing as t

from adlfs import AzureBlobFileSystem
from pydantic import SecretStr
from acb.depends import depends
from ._base import StorageBase, StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    connection_string: SecretStr


class Storage(StorageBase):
    file_system: t.Any = AzureBlobFileSystem


depends.set(Storage)
