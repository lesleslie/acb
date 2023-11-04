import typing as t

from acb.depends import depends
from gcsfs.core import GCSFileSystem
from google.cloud import storage
from ._base import StorageBase
from ._base import StorageBaseSettings


class StorageSettings(StorageBaseSettings):
    cors: t.Optional[dict[str, dict]] = dict(
        upload={
            "origin": ["*"],
            "method": ["*"],
            "responseHeader": ["*"],
            "maxAgeSeconds": 600,
        }
    )


class Storage(StorageBase):
    file_system: t.Any = GCSFileSystem

    def set_cors(self, bucket_name: str, cors_config: str) -> None:
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        bucket.cors = [self.config.storage.cors[cors_config]]
        bucket.patch()

        self.logger.debug(f"CORS policies for {bucket.name!r} bucket set")
        return bucket

    def remove_cors(self, bucket_name: str) -> None:
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        bucket.cors = []
        bucket.patch()

        self.logger.debug(f"CORS policies for {bucket.name!r} bucket removed")
        return bucket


depends.set(Storage)
