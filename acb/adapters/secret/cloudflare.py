import builtins
from uuid import UUID

import typing as t

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import Inject, depends

from ._base import SecretBase, SecretBaseSettings

try:
    from cloudflare import Cloudflare
    from cloudflare._exceptions import (
        APIConnectionError,
        APIError,
        APITimeoutError,
        AuthenticationError,
        NotFoundError,
    )

    _cloudflare_available = True
    # CloudflareError is the base exception class
    CloudflareError = Exception
except ImportError:
    _cloudflare_available = False
    Cloudflare = None  # type: ignore[assignment,misc,no-redef]
    CloudflareError = Exception  # type: ignore[assignment,misc,no-redef]
    APIError = Exception  # type: ignore[assignment,misc,no-redef]
    AuthenticationError = Exception  # type: ignore[assignment,misc,no-redef]
    NotFoundError = Exception  # type: ignore[assignment,misc,no-redef]
    APIConnectionError = Exception  # type: ignore[assignment,misc,no-redef]
    APITimeoutError = Exception  # type: ignore[assignment,misc,no-redef]

MODULE_ID = UUID("0197ff44-c5a3-7040-8d7e-3b17c8e54692")
MODULE_STATUS = AdapterStatus.BETA

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Cloudflare KV",
    category="secret",
    provider="cloudflare",
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
    required_packages=["cloudflare>=3.0.0"],
    description="Cloudflare Workers KV secret management adapter",
    documentation_url="https://developers.cloudflare.com/kv/",
    repository_url="https://github.com/cloudflare/cloudflare-python",
    settings_class="SecretSettings",
    config_example={
        "api_token": "your-cloudflare-api-token",  # pragma: allowlist secret
        "account_id": "your-account-id",
        "namespace_id": "your-kv-namespace-id",
        "key_prefix": "acb_secrets_",
    },
)


class SecretSettings(SecretBaseSettings):
    api_token: str | None = None
    account_id: str | None = None
    namespace_id: str | None = None
    key_prefix: str = "acb_secrets_"
    ttl: int | None = None  # Optional TTL for keys in seconds


class Secret(SecretBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        if not _cloudflare_available:
            msg = "Cloudflare SDK not available. Install with: uv add cloudflare"
            raise ImportError(msg)

    async def _create_client(self) -> Cloudflare:
        if not self.config.secret.api_token:
            msg = "Cloudflare API token is required"
            raise ValueError(msg)
        if not self.config.secret.account_id:
            msg = "Cloudflare account ID is required"
            raise ValueError(msg)
        if not self.config.secret.namespace_id:
            msg = "Cloudflare KV namespace ID is required"
            raise ValueError(msg)

        return Cloudflare(api_token=self.config.secret.api_token)

    async def get_client(self) -> Cloudflare:
        client = await self._ensure_client()
        return t.cast("Cloudflare", client)  # type: ignore[no-any-return]

    @property
    def client(self) -> Cloudflare:
        if self._client is None:
            msg = "Client not initialized. Call get_client() first."
            raise RuntimeError(msg)
        return self._client

    def _get_full_key(self, name: str) -> str:
        """Generate the full key name with prefix."""
        return f"{self.config.secret.key_prefix}{self.prefix}{name}"

    def _extract_secret_name(self, full_key: str) -> str:
        """Extract the secret name from the full key."""
        prefix = f"{self.config.secret.key_prefix}{self.prefix}"
        return full_key.removeprefix(prefix)

    @depends.inject
    async def init(self, logger: Inject[t.Any]) -> None:
        try:
            await self.get_client()
            # Test connection by attempting to list keys
            await self.list()
            logger.info("Cloudflare KV secret adapter initialized successfully")  # type: ignore[no-untyped-call]
        except (AuthenticationError, APIConnectionError, CloudflareError) as e:
            logger.exception(f"Failed to initialize Cloudflare KV secret adapter: {e}")  # type: ignore[no-untyped-call]
            raise
        except Exception as e:
            logger.exception(
                f"Unexpected error initializing Cloudflare KV secret adapter: {e}",
            )  # type: ignore[no-untyped-call]
            raise

    async def list(self, adapter: str | None = None) -> list[str]:
        try:
            filter_prefix = (
                f"{self.config.secret.key_prefix}{self.prefix}{adapter}_"
                if adapter
                else f"{self.config.secret.key_prefix}{self.prefix}"
            )

            client = await self.get_client()
            response = client.kv.namespaces.keys.list(
                self.config.secret.namespace_id,
                account_id=self.config.secret.account_id,
                prefix=filter_prefix,
            )

            return [
                self._extract_secret_name(key.name)
                for key in response.result
                if key.name.startswith(filter_prefix)
            ]
        except (APIError, NotFoundError, APITimeoutError, CloudflareError) as e:
            self.logger.exception(f"Failed to list secrets: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error listing secrets: {e}")
            raise

    async def get(self, name: str, version: str | None = None) -> str | None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            response = client.kv.namespaces.values.get(  # type: ignore[call-arg]
                self.config.secret.namespace_id,
                full_key,
                account_id=self.config.secret.account_id,
            )

            if response is None:
                return None

            self.logger.info(f"Fetched secret - {name}")
            return t.cast("str", response)  # type: ignore[return-value]
        except NotFoundError:
            # Cloudflare returns NotFoundError for missing keys
            return None
        except (APIError, APITimeoutError, CloudflareError) as e:
            self.logger.exception(f"Failed to get secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error getting secret {name}: {e}")
            raise

    async def create(self, name: str, value: str) -> None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            # Prepare the key-value pair
            kv_data = {"key": full_key, "value": value}
            if self.config.secret.ttl:
                kv_data["expiration_ttl"] = self.config.secret.ttl

            client.kv.namespaces.bulk.update(  # type: ignore[attr-defined]
                self.config.secret.namespace_id,
                [kv_data],
                account_id=self.config.secret.account_id,
            )

            self.logger.debug(f"Created secret - {name}")
        except (APIError, AuthenticationError, APITimeoutError, CloudflareError) as e:
            self.logger.exception(f"Failed to create secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error creating secret {name}: {e}")
            raise

    async def update(self, name: str, value: str) -> None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            # Prepare the key-value pair
            kv_data = {"key": full_key, "value": value}
            if self.config.secret.ttl:
                kv_data["expiration_ttl"] = self.config.secret.ttl

            client.kv.namespaces.bulk.update(  # type: ignore[attr-defined]
                self.config.secret.namespace_id,
                [kv_data],
                account_id=self.config.secret.account_id,
            )

            self.logger.debug(f"Updated secret - {name}")
        except (APIError, AuthenticationError, APITimeoutError, CloudflareError) as e:
            self.logger.exception(f"Failed to update secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error updating secret {name}: {e}")
            raise

    async def set(self, name: str, value: str) -> None:
        """Create or update a secret."""
        await self.update(name, value)  # KV update creates if not exists

    async def exists(self, name: str) -> bool:
        try:
            result = await self.get(name)
            return result is not None
        except (APIError, NotFoundError, APITimeoutError, CloudflareError):
            return False
        except Exception:
            return False

    async def delete(self, name: str) -> None:
        try:
            full_key = self._get_full_key(name)
            client = await self.get_client()

            client.kv.namespaces.bulk.delete(  # type: ignore[attr-defined]
                self.config.secret.namespace_id,
                [full_key],
                account_id=self.config.secret.account_id,
            )

            self.logger.debug(f"Deleted secret - {name}")
        except (APIError, NotFoundError, APITimeoutError, CloudflareError) as e:
            self.logger.exception(f"Failed to delete secret {name}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error deleting secret {name}: {e}")
            raise

    async def list_versions(self, name: str) -> builtins.list[str]:
        self.logger.warning(
            "Listing secret versions is not supported by Cloudflare KV adapter",
        )
        return []


depends.set(Secret, "cloudflare")
