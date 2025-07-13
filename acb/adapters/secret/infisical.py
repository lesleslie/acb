import asyncio
import builtins
import os
import typing as t
from uuid import UUID

from infisical_sdk import InfisicalSDKClient
from acb.adapters import AdapterStatus
from acb.depends import depends
from acb.logger import Logger

from ._base import SecretBase, SecretBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b854cbd7bb5c")
MODULE_STATUS = AdapterStatus.STABLE


class SecretSettings(SecretBaseSettings):
    host: str = "https://app.infisical.com"
    client_id: str | None = None
    client_secret: str | None = None
    token: str | None = None
    project_id: str | None = None
    environment: str = "dev"
    secret_path: str = os.getenv("ACB_TEST_SECRET_PATH", "/")
    cache_ttl: int | None = 60


class Secret(SecretBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()

    async def _create_client(self) -> InfisicalSDKClient:
        client = InfisicalSDKClient(
            host=self.config.secret.host,
            token=self.config.secret.token,
            cache_ttl=self.config.secret.cache_ttl,
        )
        if (
            not self.config.secret.token
            and self.config.secret.client_id
            and self.config.secret.client_secret
        ):
            client.auth.universal_auth.login(
                client_id=self.config.secret.client_id,
                client_secret=self.config.secret.client_secret,
            )
        return client

    async def get_client(self) -> InfisicalSDKClient:
        return await self._ensure_client()

    @property
    def client(self) -> InfisicalSDKClient:
        if self._client is None:
            msg = "Client not initialized. Call get_client() first."
            raise RuntimeError(msg)
        return self._client

    @depends.inject
    async def init(self, logger: Logger = depends()) -> None:
        try:
            await self.get_client()
            await self.list()
            logger.info("Infisical secret adapter initialized successfully")
        except Exception as e:
            logger.exception(f"Failed to initialize Infisical secret adapter: {e}")
            raise

    def extract_secret_name(self, secret_path: str) -> str:
        return secret_path.split("/")[-1].removeprefix(self.prefix)

    async def list(self, adapter: str | None = None) -> list[str]:
        try:
            filter_prefix = f"{self.prefix}{adapter}_" if adapter else self.prefix
            project_id = self.config.secret.project_id
            if not project_id:
                msg = "Project ID is required but not set in configuration"
                raise ValueError(msg)
            client = await self.get_client()
            response = await asyncio.to_thread(
                client.secrets.list_secrets,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
            )
            return [
                self.extract_secret_name(secret.secretKey)
                for secret in response.secrets
                if secret.secretKey.startswith(filter_prefix)
            ]
        except Exception as e:
            self.logger.exception(f"Failed to list secrets: {e}")
            raise

    async def get(self, name: str, version: str | None = None) -> str | None:
        try:
            project_id = self.config.secret.project_id
            if not project_id:
                msg = "Project ID is required but not set in configuration"
                raise ValueError(msg)
            full_name = f"{self.prefix}{name}"
            client = await self.get_client()
            response = await asyncio.to_thread(
                client.secrets.get_secret_by_name,
                secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
                version=version or "",
            )
            self.logger.info(f"Fetched secret - {name}")
            return response.secretValue
        except Exception as e:
            self.logger.exception(f"Failed to get secret {name}: {e}")
            raise

    async def create(self, name: str, value: str) -> None:
        try:
            project_id = self.config.secret.project_id
            if not project_id:
                msg = "Project ID is required but not set in configuration"
                raise ValueError(msg)
            full_name = f"{self.prefix}{name}"
            client = await self.get_client()
            await asyncio.to_thread(
                client.secrets.create_secret_by_name,
                secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
                secret_value=value,
            )
            self.logger.debug(f"Created secret - {name}")
        except Exception as e:
            self.logger.exception(f"Failed to create secret {name}: {e}")
            raise

    async def update(self, name: str, value: str) -> None:
        try:
            project_id = self.config.secret.project_id
            if not project_id:
                msg = "Project ID is required but not set in configuration"
                raise ValueError(msg)
            full_name = f"{self.prefix}{name}"
            client = await self.get_client()
            await asyncio.to_thread(
                client.secrets.update_secret_by_name,
                current_secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
                secret_value=value,
            )
            self.logger.debug(f"Updated secret - {name}")
        except Exception as e:
            self.logger.exception(f"Failed to update secret {name}: {e}")
            raise

    async def set(self, name: str, value: str) -> None:
        if await self.exists(name):
            await self.update(name, value)
        else:
            await self.create(name, value)

    async def exists(self, name: str) -> bool:
        try:
            await self.get(name)
            return True
        except Exception:
            return False

    async def delete(self, name: str) -> None:
        try:
            project_id = self.config.secret.project_id
            if not project_id:
                msg = "Project ID is required but not set in configuration"
                raise ValueError(msg)
            full_name = f"{self.prefix}{name}"
            client = await self.get_client()
            await asyncio.to_thread(
                client.secrets.delete_secret_by_name,
                secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
            )
            self.logger.debug(f"Deleted secret - {name}")
        except Exception as e:
            self.logger.exception(f"Failed to delete secret {name}: {e}")
            raise

    async def list_versions(self, name: str) -> builtins.list[str]:
        self.logger.warning(
            "Listing secret versions is not currently supported by the Infisical adapter",
        )
        return []


depends.set(Secret)
