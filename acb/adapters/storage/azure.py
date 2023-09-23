from adlfs import AzureBlobFileSystem
from pydantic import SecretStr
from . import StorageBase
from . import StorageBaseSettings
import typing as t


class StorageSettings(StorageBaseSettings):
    connection_string: SecretStr


class Storage(StorageBase):
    client: t.Any = AzureBlobFileSystem


storage = Storage()
