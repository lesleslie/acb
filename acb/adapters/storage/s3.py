from uuid import UUID

import typing as t
from pydantic import SecretStr
from s3fs import S3FileSystem

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b79ed498d940")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="S3 Storage",
    category="storage",
    provider="aws",
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
    required_packages=["s3fs"],
    description="AWS S3 storage adapter with streaming and bulk operations support",
    settings_class="StorageSettings",
    config_example={
        "access_key_id": "your-aws-access-key",  # pragma: allowlist secret
        "secret_access_key": "your-aws-secret-key",  # pragma: allowlist secret
        "region": "us-west-2",
        "bucket": "my-storage-bucket",
    },
)


class StorageSettings(StorageBaseSettings):
    access_key_id: SecretStr
    secret_access_key: SecretStr


class Storage(StorageBase):
    file_system: t.Any = S3FileSystem

    # Health checking removed as part of architectural simplification


depends.set(Storage, "s3")
