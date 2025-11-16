import builtins
from uuid import UUID

import typing as t

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import Inject, depends

from ._base import SecretBase, SecretBaseSettings

try:
    from azure.core.exceptions import (
        AzureError,
        ClientAuthenticationError,
        HttpResponseError,
        ResourceNotFoundError,
    )
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    _azure_available = True
except ImportError:
    _azure_available = False
    SecretClient = None  # type: ignore[assignment,misc,no-redef]
    DefaultAzureCredential = None  # type: ignore[assignment,misc,no-redef]
    ClientAuthenticationError = Exception  # type: ignore[assignment,misc,no-redef]
    ResourceNotFoundError = Exception  # type: ignore[assignment,misc,no-redef]
    HttpResponseError = Exception  # type: ignore[assignment,misc,no-redef]
    AzureError = Exception  # type: ignore[assignment,misc,no-redef]

MODULE_ID = UUID("0197ff44-c5a3-7040-8d7e-3b17c8e54693")
MODULE_STATUS = AdapterStatus.BETA

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Azure Key Vault",
    category="secret",
    provider="azure",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-17",
    last_modified="2025-01-17",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.ENCRYPTION,
        AdapterCapability.CACHING,
    ],
    required_packages=["azure-keyvault-secrets>=4.8.0", "azure-identity>=1.15.0"],
    description="Azure Key Vault secret management adapter",
    documentation_url="https://docs.microsoft.com/en-us/azure/key-vault/",
    repository_url="https://github.com/Azure/azure-sdk-for-python",
    settings_class="SecretSettings",
    config_example={
        "vault_url": "https://your-vault.vault.azure.net/",  # pragma: allowlist secret
        "tenant_id": "your-tenant-id",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",  # pragma: allowlist secret
        "secret_prefix": "acb-secrets-",  # pragma: allowlist secret
    },
)


class SecretSettings(SecretBaseSettings):
    vault_url: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    secret_prefix: str = "acb-secrets-"


class Secret(SecretBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        if not _azure_available:
            msg = "Azure SDK not available. Install with: uv add azure-keyvault-secrets azure-identity"
            raise ImportError(msg)

    async def _create_client(self) -> SecretClient:
        if not self.config.secret.vault_url:
            msg = "Azure Key Vault URL is required"
            raise ValueError(msg)

        # Use DefaultAzureCredential for authentication
        # This supports multiple authentication methods in order:
        # 1. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
        # 2. Managed Identity
        # 3. Azure CLI
        # 4. Visual Studio Code
        # 5. Azure PowerShell
        credential = DefaultAzureCredential()

        return SecretClient(  # type: ignore  # type: ignore[no-any-return]
            vault_url=self.config.secret.vault_url,
            credential=credential,
        )

    async def get_client(self) -> SecretClient:
        return await self._ensure_client()  # type: ignore  # type: ignore[no-any-return]

    @property
    def client(self) -> SecretClient:
        if self._client is None:
            msg = "Client not initialized. Call get_client() first."
            raise RuntimeError(msg)
        return self._client

    def _get_full_key(self, name: str) -> str:
        """Generate the full secret name with prefix."""
        # Azure Key Vault secret names must be alphanumeric and dashes only
        safe_prefix = self.config.secret.secret_prefix.replace("_", "-")
        safe_name = name.replace("_", "-")
        return f"{safe_prefix}{self.prefix.replace('_', '-')}{safe_name}"

    def _extract_secret_name(self, full_key: str) -> str:
        """Extract the secret name from the full key."""
        safe_prefix = f"{self.config.secret.secret_prefix.replace('_', '-')}{self.prefix.replace('_', '-')}"
        extracted = full_key.removeprefix(safe_prefix)
        # Convert back to underscore format for consistency
        return extracted.replace("-", "_")

    @depends.inject
    async def init(self, logger: Inject[t.Any]) -> None:
        try:
            await self.get_client()
            # Test connection by attempting to list secrets
            await self.list()
            logger.info("Azure Key Vault secret adapter initialized successfully")  # type: ignore[no-untyped-call]
        except (ClientAuthenticationError, HttpResponseError, AzureError) as e:
            logger.exception(  # type: ignore[no-untyped-call]
                f"Failed to initialize Azure Key Vault secret adapter: {e}",
            )
            raise
        except Exception as e:
            logger.exception(  # type: ignore[no-untyped-call]
                f"Unexpected error initializing Azure Key Vault secret adapter: {e}",
            )
            raise

    async def list(self, adapter: str | None = None) -> list[str]:
        try:
            safe_prefix = self.config.secret.secret_prefix.replace("_", "-")
            filter_prefix = (
                f"{safe_prefix}{self.prefix.replace('_', '-')}{adapter.replace('_', '-')}-"
                if adapter is not None
                else f"{safe_prefix}{self.prefix.replace('_', '-')}"
            )

            client = await self.get_client()
            secret_properties = client.list_properties_of_secrets()

            result = []
            for secret_property in secret_properties:
                if secret_property.name and secret_property.name.startswith(
                    filter_prefix,
                ):
                    secret_name = self._extract_secret_name(secret_property.name)
                    result.append(secret_name)

            return result
        except (ClientAuthenticationError, HttpResponseError, AzureError) as e:
            self.logger.exception(f"Failed to list secrets: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error listing secrets: {e}")
            raise

    async def get(self, name: str, version: str | None = None) -> str | None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            if version:
                secret = client.get_secret(full_key, version=version)
            else:
                secret = client.get_secret(full_key)

            if secret is None or secret.value is None:
                return None

            self.logger.info(f"Fetched secret - {name}")
            return secret.value
        except ResourceNotFoundError:
            # Azure returns ResourceNotFoundError for missing secrets
            return None
        except (ClientAuthenticationError, HttpResponseError, AzureError) as e:
            self.logger.exception(f"Failed to get secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error getting secret {name}: {e}")
            raise

    async def create(self, name: str, value: str) -> None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            client.set_secret(full_key, value)
            self.logger.debug(f"Created secret - {name}")
        except (ClientAuthenticationError, HttpResponseError, AzureError) as e:
            self.logger.exception(f"Failed to create secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error creating secret {name}: {e}")
            raise

    async def update(self, name: str, value: str) -> None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            # In Azure Key Vault, set_secret creates a new version if the secret exists
            client.set_secret(full_key, value)
            self.logger.debug(f"Updated secret - {name}")
        except (ClientAuthenticationError, HttpResponseError, AzureError) as e:
            self.logger.exception(f"Failed to update secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error updating secret {name}: {e}")
            raise

    async def set(self, name: str, value: str) -> None:
        """Create or update a secret."""
        await self.update(name, value)  # Azure Key Vault set_secret handles both cases

    async def exists(self, name: str) -> bool:
        try:
            result = await self.get(name)
            return result is not None
        except (
            ClientAuthenticationError,
            ResourceNotFoundError,
            HttpResponseError,
            AzureError,
        ):
            return False
        except Exception:
            return False

    async def delete(self, name: str) -> None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            # Azure Key Vault has soft delete - this begins the deletion process
            client.begin_delete_secret(full_key)
            self.logger.debug(f"Deleted secret - {name}")
        except (
            ClientAuthenticationError,
            ResourceNotFoundError,
            HttpResponseError,
            AzureError,
        ) as e:
            self.logger.exception(f"Failed to delete secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error deleting secret {name}: {e}")
            raise

    async def list_versions(self, name: str) -> builtins.list[str]:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            secret_versions = client.list_properties_of_secret_versions(full_key)
            return [
                version_property.version
                for version_property in secret_versions
                if version_property.version
            ]

        except (
            ClientAuthenticationError,
            ResourceNotFoundError,
            HttpResponseError,
            AzureError,
        ) as e:
            self.logger.exception(f"Failed to list versions for secret {name}: {e}")
            return []
        except Exception as e:
            self.logger.exception(
                f"Unexpected error listing versions for secret {name}: {e}",
            )
            return []


depends.set(Secret, "azure")
