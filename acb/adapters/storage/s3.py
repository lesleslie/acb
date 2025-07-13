import typing as t
from uuid import UUID

from pydantic import SecretStr
from s3fs import S3FileSystem
from acb.adapters import AdapterStatus
from acb.config import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b79ed498d940")
MODULE_STATUS = AdapterStatus.STABLE


class StorageSettings(StorageBaseSettings):
    access_key_id: SecretStr
    secret_access_key: SecretStr


class Storage(StorageBase):
    file_system: t.Any = S3FileSystem


depends.set(Storage)
