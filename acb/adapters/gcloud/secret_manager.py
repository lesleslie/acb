from contextlib import suppress
from logging import getLogger
from pathlib import Path
from random import choice
from secrets import compare_digest
from secrets import token_bytes
from secrets import token_urlsafe
from string import ascii_letters
from string import digits
from string import punctuation
from typing import Any
from typing import Optional
from warnings import catch_warnings
from warnings import filterwarnings

from addict import Dict as adict
from aiopath import AsyncPath
from google.api_core.exceptions import AlreadyExists
from google.auth import default
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request
from google.cloud.secretmanager import SecretManagerServiceClient
from google.oauth2.credentials import Credentials
from msgspec import yaml
from pydantic import BaseSettings

secret_dir = "tmp/secrets"
deployed = False

logger = getLogger()

basedir = Path().cwd()

settings = adict(yaml.decode((basedir / "settings" / "app.yml").read_bytes()))
debug = adict(yaml.decode((basedir / "settings" / "debug.yml").read_bytes()))


def gen_password(size: int) -> str:
    chars = ascii_letters + digits + punctuation
    return "".join(choice(chars) for i in range(size))


class AppSecrets(BaseSettings):
    database_host: Optional[str]
    database_user: Optional[str]
    database_password: Optional[str]
    database_connection: Optional[str]
    redis_host: Optional[str]
    redis_password: Optional[str]
    mailgun_api_key: Optional[str]
    facebook_app_id: Optional[str]
    facebook_app_secret: Optional[str]
    firebase_api_key: Optional[str]
    slack_api_key: Optional[str]
    google_service_account: Optional[Any]
    google_service_account_json: Optional[str]
    google_maps_api_key: Optional[str]
    google_maps_dev_api_key: Optional[str]
    google_upload_json: Optional[str]
    recaptcha_dev_key: Optional[str]
    recaptcha_production_key: Optional[str]
    app_secret_key = token_urlsafe(32)
    app_secure_salt: Optional[str] = str(token_bytes(32))
    app_mail_password: Optional[str] = gen_password(10)

    def __init__(self, **data: Any):
        super().__init__(**data)

    class Config:
        extra = "forbid"


class SecretManager:
    client: Optional[SecretManagerServiceClient]
    authed_session: Optional[AuthorizedSession]
    creds: Optional[Credentials]
    target_audience: Optional[str]
    projects: Optional[list]
    project: Optional[str] = settings.project
    domain: Optional[str] = settings.domain
    prefix: Optional[str] = settings.name
    parent: Optional[str] = f"projects/{settings.project}"
    secret_dir: str = secret_dir

    class Config:
        arbitrary_types_allowed = True

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
        if debug.secret_manager:
            logger.debug(f"Secrets access token:\n{self.creds.token}")
        return self.creds.token

    async def verify_access_token(self, token: str) -> bool:
        verified = compare_digest(self.creds.token, token)
        if debug.secret_manager:
            logger.debug(f"Secrets access token verified - {verified}")
        return verified

    async def list(self):
        secrets = self.client.list_secrets(request={"parent": self.parent})
        secrets = [self.extract_secret_name(secret.name) for secret in secrets]
        secrets = [s for s in secrets if s.split("_")[0] in [settings.name, "000"]]
        # if not deployed and debug.secret_manager:
        #     await pf(secrets)
        return secrets

    async def get(self, name: str) -> str:
        name = self.get_name(name)
        path = f"projects/{self.project}/secrets/{name}/versions/latest"
        version = self.client.access_secret_version(request={"name": path})
        payload = str(version.payload.data.decode())
        if not deployed:
            logger.info(f"Fetched secret - {name.removeprefix('000_')}")
        return payload

    async def create(self, name: str, value: str):
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
                    "payload": {"data": bytes(str.encode(f"{value}"))},
                }
            )
            if not deployed:
                logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str):
        name = self.get_name(name)
        secret = self.client.secret_path(self.project, name)
        self.client.add_secret_version(
            request={
                "parent": secret,
                "payload": {"data": bytes(str.encode(f"{value}"))},
            }
        )
        if not deployed:
            logger.debug(f"Updated secret - {name}")

    async def delete(self, name: str):
        name = self.get_name(name)
        secret = self.client.secret_path(self.project, name)
        self.client.delete_secret(request={"name": secret})
        if not deployed:
            logger.debug(f"Deleted secret - {secret}")

    async def load(self, name, secrets, cls_dict):
        if name not in secrets:
            await self.create(name, cls_dict[name])
        secret = await self.get(name)
        return secret

    async def load_all(self, cls_dict):
        secrets = await self.list()
        data = adict()
        secret_dir = AsyncPath(self.secret_dir)
        await secret_dir.mkdir()
        for name in cls_dict.keys():
            secret = await self.load(name, secrets, cls_dict)
            data[name] = secret
            secret_path = secret_dir / name
            await secret_path.write_text(secret)
        return data

    async def init(self):
        if not await AsyncPath(secret_manager.secret_dir).exists():
            return await secret_manager.load_all(AppSecrets().dict())
        else:
            return AppSecrets(_secrets_dir=secret_manager.secret_dir)

    def __init__(self):
        super().__init__()
        self.debug = None
        self.target_audience = f"https://{self.domain}"
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            creds, projects = default()
        self.creds = creds
        self.projects = projects
        self.client = SecretManagerServiceClient(credentials=self.creds)
        self.authed_session = AuthorizedSession(self.creds)
        if debug.secret:
            Path(secret_dir).rmdir()


secret_manager = SecretManager()
