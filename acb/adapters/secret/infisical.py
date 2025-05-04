import asyncio
import typing as t
from functools import cached_property

from infisical_sdk import InfisicalSDKClient
from acb.depends import depends
from acb.logger import Logger

from ._base import SecretBase, SecretBaseSettings


class SecretSettings(SecretBaseSettings):
    host: str = "https://app.infisical.com"
    client_id: t.Optional[str] = None
    client_secret: t.Optional[str] = None
    token: t.Optional[str] = None
    project_id: t.Optional[str] = None
    environment: str = "dev"
    secret_path: str = "/"
    cache_ttl: t.Optional[int] = 60


class Secret(SecretBase):
    @cached_property
    def client(self) -> InfisicalSDKClient:
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

    @depends.inject
    async def init(self, logger: Logger = depends()) -> None:
        try:
            await self.list()
            logger.info("Infisical secret adapter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Infisical secret adapter: {e}")
            raise

    def extract_secret_name(self, secret_path: str) -> str:
        return secret_path.split("/")[-1].removeprefix(self.prefix)

    async def list(self, adapter: t.Optional[str] = None) -> t.List[str]:
        try:
            filter_prefix = f"{self.prefix}{adapter}_" if adapter else self.prefix

            project_id = self.config.secret.project_id
            if not project_id:
                raise ValueError("Project ID is required but not set in configuration")

            response = await asyncio.to_thread(
                self.client.secrets.list_secrets,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
            )

            secret_names = [
                self.extract_secret_name(secret.secretKey)
                for secret in response.secrets
                if secret.secretKey.startswith(filter_prefix)
            ]

            return secret_names
        except Exception as e:
            self.logger.error(f"Failed to list secrets: {e}")
            raise

    async def get(self, name: str, version: t.Optional[str] = None) -> t.Optional[str]:
        try:
            project_id = self.config.secret.project_id
            if not project_id:
                raise ValueError("Project ID is required but not set in configuration")

            full_name = f"{self.prefix}{name}"

            response = await asyncio.to_thread(
                self.client.secrets.get_secret_by_name,
                secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
                version=version or "",
            )

            self.logger.info(f"Fetched secret - {name}")
            return response.secretValue
        except Exception as e:
            self.logger.error(f"Failed to get secret {name}: {e}")
            raise

    async def create(self, name: str, value: str) -> None:
        try:
            project_id = self.config.secret.project_id
            if not project_id:
                raise ValueError("Project ID is required but not set in configuration")

            full_name = f"{self.prefix}{name}"

            await asyncio.to_thread(
                self.client.secrets.create_secret_by_name,
                secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
                secret_value=value,
            )

            self.logger.debug(f"Created secret - {name}")
        except Exception as e:
            self.logger.error(f"Failed to create secret {name}: {e}")
            raise

    async def update(self, name: str, value: str) -> None:
        try:
            project_id = self.config.secret.project_id
            if not project_id:
                raise ValueError("Project ID is required but not set in configuration")

            full_name = f"{self.prefix}{name}"

            await asyncio.to_thread(
                self.client.secrets.update_secret_by_name,
                current_secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
                secret_value=value,
            )

            self.logger.debug(f"Updated secret - {name}")
        except Exception as e:
            self.logger.error(f"Failed to update secret {name}: {e}")
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
                raise ValueError("Project ID is required but not set in configuration")

            full_name = f"{self.prefix}{name}"

            await asyncio.to_thread(
                self.client.secrets.delete_secret_by_name,
                secret_name=full_name,
                project_id=project_id,
                environment_slug=self.config.secret.environment,
                secret_path=self.config.secret.secret_path,
            )

            self.logger.debug(f"Deleted secret - {name}")
        except Exception as e:
            self.logger.error(f"Failed to delete secret {name}: {e}")
            raise

    async def list_versions(self, name: str) -> t.List[str]:
        self.logger.warning(
            "Listing secret versions is not currently supported by the Infisical adapter"
        )
        return []


depends.set(Secret)
