import typing as t

from acb.depends import depends
from adlfs import AzureBlobFileSystem
from pydantic import SecretStr
from ._base import StorageBase
from ._base import StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    connection_string: SecretStr


class Storage(StorageBase):
    file_system: t.Any = AzureBlobFileSystem


depends.set(Storage)
