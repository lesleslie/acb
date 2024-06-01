import typing as t

from pydantic import SecretStr
from s3fs import S3FileSystem
from acb.config import depends
from ._base import StorageBase, StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    access_key_id: SecretStr
    secret_access_key: SecretStr


class Storage(StorageBase):
    file_system: t.Any = S3FileSystem


depends.set(Storage)
