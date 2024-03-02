import typing as t
from contextlib import suppress
from secrets import compare_digest
from warnings import catch_warnings
from warnings import filterwarnings

from acb.adapters import import_adapter
from acb.config import app_name
from acb.config import project
from acb.depends import depends
from google.api_core.exceptions import AlreadyExists
from google.api_core.exceptions import PermissionDenied
from google.auth import default
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request
from google.cloud.secretmanager_v1 import AccessSecretVersionRequest
from google.cloud.secretmanager_v1 import AddSecretVersionRequest
from google.cloud.secretmanager_v1 import CreateSecretRequest
from google.cloud.secretmanager_v1 import DeleteSecretRequest
from google.cloud.secretmanager_v1 import ListSecretsRequest
from google.cloud.secretmanager_v1 import SecretManagerServiceAsyncClient
from ._base import SecretBase
from ._base import SecretBaseSettings

Logger = import_adapter()


class SecretSettings(SecretBaseSettings): ...


class Secret(SecretBase):
    logger: Logger = depends()  # type: ignore
    project: str = ""
    parent: str = ""
    prefix: str = ""
    client: t.Optional[SecretManagerServiceAsyncClient] = None
    authed_session: t.Optional[AuthorizedSession] = None
    creds: t.Optional[t.Any] = None

    def extract_secret_name(self, secret_path: str) -> t.Any:
        return secret_path.split("/")[-1].removeprefix(self.prefix)

    async def get_access_token(self) -> t.Any:
        self.creds.refresh(Request())
        self.logger.debug(f"Secrets access token:\n{self.creds.token}")
        return self.creds.token

    async def verify_access_token(self, token: str) -> t.Any:
        verified = compare_digest(self.creds.token, token)
        self.logger.debug(f"Secrets access token verified - {verified}")
        return verified

    async def list(self, adapter: str) -> t.Any:
        request = ListSecretsRequest(
            parent=self.parent, filter=f"{self.prefix}{adapter}_"
        )
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

    async def get(self, name: str) -> t.Any:
        path = f"projects/{self.project}/secrets/{name}/versions/latest"
        request = AccessSecretVersionRequest(name=path)
        version = await self.client.access_secret_version(request=request)
        payload = version.payload.data.decode()
        self.logger.info(f"Fetched secret - {name}")
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
                payload={"data": value.encode()},
            )
            await self.client.add_secret_version(request)
            self.logger.debug(f"Created secret - {name}")

    async def update(self, name: str, value: str) -> t.NoReturn:
        secret = self.client.secret_path(self.project, name)
        request = AddSecretVersionRequest(
            parent=secret,
            payload={"data": value.encode()},
        )
        await self.client.add_secret_version(request)
        self.logger.debug(f"Updated secret - {name}")

    async def delete(self, name: str) -> t.NoReturn:
        secret = self.client.secret_path(self.project, name)
        request = DeleteSecretRequest(name=secret)
        await self.client.delete_secret(request=request)
        self.logger.debug(f"Deleted secret - {secret}")

    async def init(self) -> t.NoReturn:
        self.project = project
        self.parent = f"projects/{project}"
        self.prefix = f"{app_name}_"
        with catch_warnings():
            filterwarnings("ignore", category=Warning)
            creds, _ = default()
        self.creds = creds
        self.client = SecretManagerServiceAsyncClient(
            credentials=self.creds  # type: ignore
        )
        self.authed_session = AuthorizedSession(self.creds)


depends.set(Secret)
