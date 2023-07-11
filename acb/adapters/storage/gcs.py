from gcsfs.core import GCSFileSystem
from pydantic import HttpUrl
from . import StorageBase
from . import StorageBaseSettings


# from google.cloud.exceptions import NotFound


class StorageSettings(StorageBaseSettings):
    scheme: str = "gs"
    https_url: HttpUrl = "https://storage.googleapis.com"

    # def model_post_init(self, __context: t.Any) -> None:
    #     super().model_post_init(self)


class Storage(StorageBase):
    client: GCSFileSystem = GCSFileSystem
    # client: GCSFileSystem = GCSFileSystem(asynchronous=True, loop=loop)


storage = Storage()
