import typing as t

from aiopathy import set_client_params
from . import StorageBase
from . import StorageBaseSettings
from pydantic import SecretStr
from pydantic import HttpUrl


class StorageSettings(StorageBaseSettings):
    connection_string: SecretStr
    scheme: str = "azure"
    https_url: HttpUrl = "https://storage.azure.com"

    def model_post_init(self, __context: t.Any) -> None:
        super().model_post_init(self)
        set_client_params(self.scheme, connection_string=self.connection_string)


class Storage(StorageBase):
    ...


storage = Storage()
