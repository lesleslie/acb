import typing as t
from contextlib import suppress
from secrets import compare_digest
from warnings import catch_warnings
from warnings import filterwarnings

from acb.config import ac
from acb.config import app_name
from acb.config import project
from acb.logger import logger
from google.api_core.exceptions import AlreadyExists
from google.auth import default
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request
from google.cloud.secretmanager_v1 import AccessSecretVersionRequest
from google.cloud.secretmanager_v1 import AddSecretVersionRequest
from google.cloud.secretmanager_v1 import CreateSecretRequest
from google.cloud.secretmanager_v1 import DeleteSecretRequest
from google.cloud.secretmanager_v1 import ListSecretsRequest
from google.cloud.secretmanager_v1 import SecretManagerServiceAsyncClient
from . import SecretsBaseSettings


class SecretsSettings(SecretsBaseSettings):
    ...


class Secrets:
    project: str = ""
    parent: str = ""
    prefix: str = ""
    client: t.Optional[SecretManagerServiceAsyncClient] = None
    authed_session: t.Optional[AuthorizedSession] = None
    creds: t.Optional[t.Any] = None

    # @staticmethod
    def extract_secret_name(self, secret_path: str) -> str:
        return secret_path.split("/")[-1].removeprefix(self.prefix)

    async def get_access_token(self) -> str:
        self.creds.refresh(Request())
        logger.debug(f"Secrets access token:\n{self.creds.token}")
        return self.creds.token

    async def verify_access_token(self, token: str) -> bool:
        verified = compare_digest(self.creds.token, token)
        logger.debug(f"Secrets access token verified - {verified}")
        return verified

    async def list(self, adapter: str) -> list[str]:
        request = ListSecretsRequest(
            parent=self.parent, filter=f"{self.prefix}{adapter}_"
        )
        client_secrets = await self.client.list_secrets(request=request)
        client_secrets = [
            self.extract_secret_name(secret.name) async for secret in client_secrets
        ]
        return client_secrets

    async def get(self, name: str) -> str:
        path = f"projects/{self.project}/secrets/{name}/versions/latest"
        request = AccessSecretVersionRequest(name=path)
        version = await self.client.access_secret_version(request=request)
        payload = version.payload.data.decode()
        logger.info(f"Fetched secret - {name}")
        return payload

    async def create(self, name: str, value: str) -> t.NoReturn:
        with suppress(AlreadyExists):
            request = CreateSecretRequest(
                parent=self.parent,
                secret_id=name,
                secret={"replication": {"automatic": {}}},
            )
            version = await self.client.create_secret(request)
            request = AddSecretVersionRequest(
                parent=version.name,
                payload={"data": f"{value}".encode()},
            )
            await self.client.add_secret_version(request)
            if not ac.deployed:
                logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str) -> t.NoReturn:
        secret = self.client.secret_path(self.project, name)
        request = AddSecretVersionRequest(
            parent=secret,
            payload={"data": f"{value}".encode()},
        )
        await self.client.add_secret_version(request)
        if not ac.deployed:
            logger.debug(f"Updated secret - {name}")

    async def delete(self, name: str) -> t.NoReturn:
        secret = self.client.secret_path(self.project, name)
        request = DeleteSecretRequest(name=secret)
        await self.client.delete_secret(request=request)
        if not ac.deployed:
            logger.debug(f"Deleted secret - {secret}")

    async def init(self) -> t.NoReturn:
        self.project = project
        self.parent = f"projects/{project}"
        self.prefix = f"{app_name}_"
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            creds, _ = default()
        self.creds = creds
        self.client = SecretManagerServiceAsyncClient(credentials=self.creds)
        self.authed_session = AuthorizedSession(self.creds)


secrets = Secrets()
