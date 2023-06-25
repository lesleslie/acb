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
from google.cloud.secretmanager import SecretManagerServiceAsyncClient
from google.oauth2.credentials import Credentials


class SecretManager:
    client: Optional[SecretManagerServiceAsyncClient]
    authed_session: Optional[AuthorizedSession]
    creds: Optional[Credentials]
    parent: Optional[str] = None

    # target_audience: Optional[str]
    # projects: Optional[list]
    # project: Optional[str] = ac.app.project
    # domain: Optional[str] = ac.app.domain
    # prefix: Optional[str] = ac.app.name

    # secrets_path: AsyncPath = ac.secrets.path
    @staticmethod
    def extract_secret_name(secret: str) -> str:
        return Path(secret).parts[-1]

    @staticmethod
    def get_name(name: str) -> str:
        return "_".join([ac.app.name, name])

    async def get_access_token(self) -> str:
        self.creds.refresh(Request())
        if ac.debug.secret_manager:
            logger.debug(f"Secrets access token:\n{self.creds.token}")
        return self.creds.token

    async def verify_access_token(self, token: str) -> bool:
        verified = compare_digest(self.creds.token, token)
        if ac.debug.secret_manager:
            logger.debug(f"Secrets access token verified - {verified}")
        return verified

    async def list(self) -> list:
        client_secrets = await self.client.list_secrets(request={"parent": self.parent})
        client_secrets = [
            self.extract_secret_name(secret.name) async for secret in client_secrets
        ]
        client_secrets = [s for s in client_secrets if s.split("_")[0] == ac.app.name]
        # if not deployed and debug.secret_manager:
        #     await apformat(secrets)
        return client_secrets

    async def get(self, name: str) -> str:
        name = self.get_name(name)
        path = f"projects/{ac.app.project}/secrets/{name}/versions/latest"
        version = await self.client.access_secret_version(request={"name": path})
        payload = version.payload.data.decode()
        if not ac.deployed:
            logger.info(f"Fetched secret - {name}")
        return payload

    async def create(self, name: str, value: str) -> None:
        name = self.get_name(name)
        parent = f"projects/{ac.app.project}"
        with suppress(AlreadyExists):
            version = await self.client.create_secret(
                request={
                    "parent": parent,
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
        secret = self.client.secret_path(ac.app.project, name)
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
        secret = self.client.secret_path(ac.app.project, name)
        await self.client.delete_secret(request={"name": secret})
        if not ac.deployed:
            logger.debug(f"Deleted secret - {secret}")

    # async def load(self, name: str, all_secrets, cls_dict) -> str:
    async def load(self, name: str) -> str:
        # if name not in all_secrets:
        #     await self.create(name, cls_dict[name])
        secret = await self.get(name)
        return secret.removeprefix(f"{ac.app.name}_")

    def __init__(self) -> None:
        super().__init__()
        self.debug = None
        self.parent = f"projects/{ac.app.project}"
        # self.target_audience = f"https://{self.domain}"
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            creds, projects = default()
        self.creds = creds
        self.projects = projects
        self.client = SecretManagerServiceAsyncClient(credentials=self.creds)
        self.authed_session = AuthorizedSession(self.creds)


secrets = SecretManager()
