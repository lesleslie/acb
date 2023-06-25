from contextlib import suppress
from pathlib import Path
from secrets import compare_digest
from typing import Optional
from warnings import catch_warnings
from warnings import filterwarnings

from acb.config import ac
from acb.logger import logger
from google.api_core.exceptions import AlreadyExists
from google.auth import default
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request
from google.cloud.secretmanager_v1 import SecretManagerServiceAsyncClient
from google.cloud.secretmanager_v1 import ListSecretsRequest
from google.oauth2.credentials import Credentials
from icecream import ic


class SecretManager:
    parent: str
    client: Optional[SecretManagerServiceAsyncClient]
    authed_session: Optional[AuthorizedSession]
    creds: Optional[Credentials]

    @staticmethod
    def extract_secret_name(secret: str) -> str:
        return Path(secret).parts[-1]

    @staticmethod
    def get_name(name: str) -> str:
        return "_".join([ac.app.name, name])

    async def get_access_token(self) -> str:
        self.creds.refresh(Request())
        logger.debug(f"Secrets access token:\n{self.creds.token}")
        return self.creds.token

    async def verify_access_token(self, token: str) -> bool:
        verified = compare_digest(self.creds.token, token)
        logger.debug(f"Secrets access token verified - {verified}")
        return verified

    async def list(self) -> list:
        request = ListSecretsRequest(
            parent=self.parent,
        )
        client_secrets = await self.client.list_secrets(request=request)
        client_secrets = [
            self.extract_secret_name(secret.name) async for secret in client_secrets
        ]
        client_secrets = [s for s in client_secrets if s.split("_")[0] == self.app_name]
        return client_secrets

    async def get(self, name: str) -> str:
        name = self.get_name(name)
        path = f"projects/{ac.app.project}/secrets/{name}/versions/latest"
        version = await self.client.access_secret_version(request={"name": path})
        payload = version.payload.data.decode()
        logger.info(f"Fetched secret - {name}")
        return payload

    async def create(self, name: str, value: str) -> None:
        name = self.get_name(name)
        with suppress(AlreadyExists):
            version = await self.client.create_secret(
                request={
                    "parent": self.parent,
                    "secret_id": name,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
            await self.client.add_secret_version(
                request={
                    "parent": version.name,
                    "payload": {"data": f"{value}".encode()},
                }
            )
            if not ac.deployed:
                logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str) -> None:
        name = self.get_name(name)
        secret = self.client.secret_path(self.project, name)
        await self.client.add_secret_version(
            request={
                "parent": secret,
                "payload": {"data": f"{value}".encode()},
            }
        )
        if not ac.deployed:
            logger.debug(f"Updated secret - {name}")

    async def delete(self, name: str) -> None:
        name = self.get_name(name)
        secret = self.client.secret_path(self.project, name)
        await self.client.delete_secret(request={"name": secret})
        if not ac.deployed:
            logger.debug(f"Deleted secret - {secret}")

    async def load(
        self,
        name: str,
    ) -> str:
        secret = await self.get(name)
        return secret.removeprefix(f"{self.app_name}_")

    def __init__(self, project: str, app_name: str) -> None:
        super().__init__()
        self.debug = None
        self.project = project
        self.parent = f"projects/{project}"
        self.app_name = app_name
        # self.target_audience = f"https://{self.domain}"
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            creds, projects = default()
        self.creds = creds
        self.client = SecretManagerServiceAsyncClient(credentials=self.creds)
        self.authed_session = AuthorizedSession(self.creds)


secrets = SecretManager
