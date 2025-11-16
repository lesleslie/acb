from uuid import UUID

import typing as t
from adlfs import AzureBlobFileSystem
from pydantic import SecretStr

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import StorageBase, StorageBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b7bbc11f7b4c")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Azure Blob Storage",
    category="storage",
    provider="azure",
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
    required_packages=["adlfs"],
    description="Azure Blob Storage adapter with streaming and bulk operations",
    settings_class="StorageSettings",
    config_example={
        "connection_string": "DefaultEndpointsProtocol=https;AccountName=...",  # pragma: allowlist secret
        "container": "my-storage-container",
    },
)


class StorageSettings(StorageBaseSettings):
    connection_string: SecretStr


class Storage(StorageBase):
    file_system: t.Any = AzureBlobFileSystem


depends.set(Storage, "azure")
