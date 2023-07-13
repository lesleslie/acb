from pydantic import SecretStr
from s3fs import S3FileSystem
from . import StorageBase
from . import StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    access_key_id: SecretStr
    secret_access_key: SecretStr


class Storage(StorageBase):
    client: S3FileSystem = S3FileSystem


storage = Storage()
