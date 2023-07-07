import typing as t

from acb.config import ac
from aiopathy import set_client_params
from . import StorageBase
from . import StorageBaseSettings
from pydantic import HttpUrl


# from google.cloud.exceptions import NotFound


class StorageSettings(StorageBaseSettings):
    scheme: str = "gs"
    https_url: HttpUrl = "https://storage.googleapis.com"

    def model_post_init(self, __context: t.Any) -> None:
        super().model_post_init(self)
        set_client_params(self.scheme, project=ac.app.project)
        # set_client_params("gs", credentials=account.from_service_account_info(creds))


class Storage(StorageBase):
    ...


storage = Storage()
