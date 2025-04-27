import typing as t
from contextlib import suppress
from functools import cached_property

from google.api_core.exceptions import AlreadyExists, PermissionDenied
from google.cloud.secretmanager_v1 import (
    AccessSecretVersionRequest,
    AddSecretVersionRequest,
    CreateSecretRequest,
    DeleteSecretRequest,
    ListSecretsRequest,
    ListSecretVersionsRequest,
    SecretManagerServiceAsyncClient,
)
from acb.config import project
from acb.depends import depends

from ._base import SecretBase, SecretBaseSettings


class SecretSettings(SecretBaseSettings): ...


class Secret(SecretBase):
    project: str = project
    parent: str = f"projects/{project}"

    def extract_secret_name(self, secret_path: str) -> str:
        return secret_path.split("/")[-1].removeprefix(self.prefix)

    async def list(self, adapter: t.Optional[str] = None) -> t.List[str]:
        filter_str = f"{self.prefix}{adapter}_" if adapter else self.prefix
        request = ListSecretsRequest(parent=self.parent, filter=filter_str)
        try:
            client_secrets = await self.client.list_secrets(request=request)
        except PermissionDenied:
            raise SystemExit(
                "\n ERROR:  'project' id in 'settings/app.yml' is invalid or not set!\n"
            )
        client_secrets = [
            self.extract_secret_name(secret.name) async for secret in client_secrets
        ]
        return client_secrets

    async def get(self, name: str, version: t.Optional[str] = None) -> t.Optional[str]:
        version_str = version or "latest"
        path = f"projects/{self.project}/secrets/{name}/versions/{version_str}"
        request = AccessSecretVersionRequest(name=path)
        response = await self.client.access_secret_version(request=request)
        payload = response.payload.data.decode()
        self.logger.info(f"Fetched secret - {name}")
        return payload

    async def create(self, name: str, value: str) -> None:
        with suppress(AlreadyExists):
            request = CreateSecretRequest(
                parent=self.parent,
                secret_id=name,
                secret={"replication": {"automatic": {}}},
            )
            version = await self.client.create_secret(request)
            request = AddSecretVersionRequest(
                parent=version.name,
                payload={"data": value.encode()},
            )
            await self.client.add_secret_version(request)
            self.logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str) -> None:
        secret = self.client.secret_path(self.project, name)
        request = AddSecretVersionRequest(
            parent=secret,
            payload={"data": value.encode()},
        )
        await self.client.add_secret_version(request)
        self.logger.debug(f"Updated secret - {name}")

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
        secret = self.client.secret_path(self.project, name)
        request = DeleteSecretRequest(name=secret)
        await self.client.delete_secret(request=request)
        self.logger.debug(f"Deleted secret - {secret}")

    async def list_versions(self, name: str) -> t.List[str]:
        secret = self.client.secret_path(self.project, name)
        request = ListSecretVersionsRequest(parent=secret)
        versions = await self.client.list_secret_versions(request=request)
        return [version.name.split("/")[-1] async for version in versions]

    @cached_property
    def client(self) -> SecretManagerServiceAsyncClient:
        return SecretManagerServiceAsyncClient()

    async def init(self) -> t.NoReturn: ...


depends.set(Secret)
