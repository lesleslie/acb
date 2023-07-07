import typing as t

from aiopathy import set_client_params
from . import StorageBase
from . import StorageBaseSettings
from pydantic import SecretStr
from pydantic import HttpUrl


class StorageSettings(StorageBaseSettings):
    access_key_id: SecretStr
    secret_access_key: SecretStr
    scheme: str = "s3"
    https_url: HttpUrl = "https://s3.amazonaws.com"

    def model_post_init(self, __context: t.Any) -> None:
        super().model_post_init(self)
        set_client_params(
            self.scheme, key_id=self.access_key_id, key_secret=self.secret_access_key
        )


class Storage(StorageBase):
    ...


storage = Storage()
