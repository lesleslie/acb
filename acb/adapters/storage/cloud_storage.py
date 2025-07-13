import typing as t
from uuid import UUID
from warnings import catch_warnings, filterwarnings

from gcsfs.core import GCSFileSystem
from google.cloud.storage import Client
from acb.adapters import AdapterStatus
from acb.config import Config
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7a742cd8f87")
MODULE_STATUS = AdapterStatus.STABLE


class StorageSettings(StorageBaseSettings):
    cors: dict[str, dict[str, list[str] | int]] | None = {
        "upload": {
            "origin": ["*"],
            "method": ["*"],
            "responseHeader": ["*"],
            "maxAgeSeconds": 600,
        },
    }


class Storage(StorageBase):
    file_system: t.Any = GCSFileSystem

    @staticmethod
    @depends.inject
    def get_client(config: Config = depends()) -> Client:
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            return Client(project=config.app.project)

    def set_cors(self, bucket_name: str, cors_config: str) -> None:
        bucket = self.get_client().get_bucket(bucket_name)
        bucket.cors = [self.config.storage.cors[cors_config]]
        bucket.patch()
        self.logger.debug(f"CORS policies for {bucket.name!r} bucket set")

    def remove_cors(self, bucket_name: str) -> None:
        bucket = self.get_client().storage_client.get_bucket(bucket_name)
        bucket.cors = []
        bucket.patch()
        self.logger.debug(f"CORS policies for {bucket.name!r} bucket removed")


depends.set(Storage)
