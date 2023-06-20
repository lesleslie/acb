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
from google.cloud.secretmanager import SecretManagerServiceClient
from google.oauth2.credentials import Credentials


class SecretManager:
    client: Optional[SecretManagerServiceClient]
    authed_session: Optional[AuthorizedSession]
    creds: Optional[Credentials]
    # target_audience: Optional[str]
    # projects: Optional[list]
    project: Optional[str] = ac.app.project
    domain: Optional[str] = ac.domain
    prefix: Optional[str] = ac.app.name
    parent: Optional[str] = f"projects/{ac.app.project}"

    @staticmethod
    def extract_secret_name(secret: str) -> str:
        return Path(secret).parts[-1]

    def get_name(self, name: str) -> str:
        name = (
            name.replace("app_", f"{self.prefix}_")
            if name.startswith("app_")
            else f"000_{name}"
        )
        return name

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
        secrets = self.client.list_secrets(request={"parent": self.parent})
        secrets = [self.extract_secret_name(secret.name) for secret in secrets]
        secrets = [s for s in secrets if s.split("_")[0] in (ac.app.name, "000")]
        # if not deployed and debug.secret_manager:
        #     await apformat(secrets)
        return secrets

    async def get(self, name: str) -> str:
        name = self.get_name(name)
        path = f"projects/{self.project}/secrets/{name}/versions/latest"
        version = self.client.access_secret_version(request={"name": path})
        payload = version.payload.data.decode()
        if not ac.deployed:
            logger.info(f"Fetched secret - {name.removeprefix('000_')}")
        return payload

    async def create(self, name: str, value: str) -> None:
        name = self.get_name(name)
        parent = f"projects/{self.project}"
        with suppress(AlreadyExists):
            version = self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": name,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
            self.client.add_secret_version(
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
        self.client.add_secret_version(
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
        self.client.delete_secret(request={"name": secret})
        if not ac.deployed:
            logger.debug(f"Deleted secret - {secret}")

    async def load(self, name: str, secrets, cls_dict) -> str:
        if name not in secrets:
            await self.create(name, cls_dict[name])
        secret = await self.get(name)
        return secret

    # async def load_all(self, cls_dict) -> dict:
    #     secrets = await self.list()
    #     data = {}
    #     await self.secrets_dir.mkdir(exist_ok=True)
    #     for name in cls_dict.keys():
    #         secret = await self.load(name, secrets, cls_dict)
    #         data[name] = secret
    #         secret_path = self.secrets_dir / name
    #         await secret_path.write_text(secret)
    #     return data

    # async def __call__(self) -> BaseSettings | dict:
    #     if ac.debug.secrets:
    #         await self.secrets_dir.rmdir()
    #     if not await self.secrets_dir.exists():
    #         return await self.load_all(AppSecrets().model_dump())
    #     return AppSecrets(_secrets_dir=self.secrets_dir)

    def __init__(self) -> None:
        super().__init__()
        self.debug = None
        # self.target_audience = f"https://{self.domain}"
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            creds, projects = default()
        self.creds = creds
        self.projects = projects
        self.client = SecretManagerServiceClient(credentials=self.creds)
        self.authed_session = AuthorizedSession(self.creds)


secrets = SecretManager()
