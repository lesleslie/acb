import typing as t
from warnings import catch_warnings
from warnings import filterwarnings

from acb.config import Config
from acb.depends import depends
from gcsfs.core import GCSFileSystem
from google.cloud.storage import Client
from ._base import StorageBase
from ._base import StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    cors: t.Optional[dict[str, dict[str, list[str] | int]]] = dict(  # noqa: FURB123
        upload={
            "origin": ["*"],
            "method": ["*"],
            "responseHeader": ["*"],
            "maxAgeSeconds": 600,
        }
    )


class Storage(StorageBase):
    file_system: t.Any = GCSFileSystem

    @staticmethod
    @depends.inject
    def get_client(config: Config = depends()):
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
