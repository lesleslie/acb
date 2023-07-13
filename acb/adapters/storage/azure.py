from adlfs import AzureBlobFileSystem
from pydantic import SecretStr
from . import StorageBase
from . import StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    connection_string: SecretStr


class Storage(StorageBase):
    client: AzureBlobFileSystem = AzureBlobFileSystem


storage = Storage()
