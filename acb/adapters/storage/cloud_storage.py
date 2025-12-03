from uuid import UUID
from warnings import catch_warnings, filterwarnings

import typing as t
from gcsfs.core import GCSFileSystem
from google.cloud.storage import Client

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.config import Config
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7a742cd8f87")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Google Cloud Storage",
    category="storage",
    provider="gcp",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-20",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.STREAMING,
    ],
    required_packages=["gcsfs", "google-cloud-storage"],
    description="Google Cloud Storage adapter with CORS support and streaming",
    settings_class="StorageSettings",
    config_example={
        "project": "my-gcp-project",
        "cors": {
            "upload": {
                "origin": ["*"],
                "method": ["*"],
                "responseHeader": ["*"],
                "maxAgeSeconds": 600,
            },
        },
    },
)


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
            assert config.app is not None, "App config must be initialized"
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
