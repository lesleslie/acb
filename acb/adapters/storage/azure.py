import typing as t
from uuid import UUID

from adlfs import AzureBlobFileSystem
from pydantic import SecretStr
from acb.adapters import AdapterStatus
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7bbc11f7b4c")
MODULE_STATUS = AdapterStatus.STABLE


class StorageSettings(StorageBaseSettings):
    connection_string: SecretStr


class Storage(StorageBase):
    file_system: t.Any = AzureBlobFileSystem


depends.set(Storage)
