import asyncio
import typing as t

from acb.config import ac
from acb.config import Settings
from acb.logger import logger
from aiopath import AsyncPath
from google.cloud.exceptions import NotFound


# CORS policy for upload bucket - upload-cors.json
#
# [
#     {
#       "origin": ["*"],
#       "method": ["*"],
#       "responseHeader": ["*"],
#       "maxAgeSeconds": 600
#     }
# ]


class StorageBaseSettings(Settings):
    prefix: t.Optional[str] = None
    user_project: t.Optional[str] = None  # used for billing
    buckets: dict[str, str] = {}

    def model_post_init(self, __context: t.Any) -> None:
        self.prefix: str = ac.app.name
        self.user_project: str = ac.app.name  # used for billing


class StorageBucket:
    client: t.Any
    bucket: t.Optional[str]
    root: t.Optional[AsyncPath]
    prefix: str = ""
    cache_control: t.Optional[str] = None

    def __init__(self, client, bucket: str, prefix: str = None) -> None:
        self.client = client
        self.prefix = prefix or ac.app.name or self.prefix
        self.bucket = ac.storage.buckets[bucket]
        self.root = AsyncPath(f"{self.bucket}/{self.prefix}")

    def get_name(self, path: AsyncPath) -> str:
        return path.name

    def get_path(self, path: AsyncPath) -> str:
        return str(self.root / path)

    def get_url(self, path: AsyncPath):
        return self.client.url(self.get_path(path))

    async def get_date_created(self, path: AsyncPath) -> str:
        return (await self.stat(path))["timeCreated"]

    async def get_date_updated(self, path: AsyncPath) -> str:
        return (await self.stat(path))["updated"]

    async def get_size(self, path: AsyncPath) -> int:
        return (await self.stat(path))["size"]

    async def get_signed_url(self, path: AsyncPath, expires: int = 3600) -> str:
        return await self.client._sign(self.get_path(path), expires=expires)

    async def stat(self, path: AsyncPath) -> dict:
        return await self.client._info(self.get_path(path))

    async def list(self, dir_path: AsyncPath):
        return await self.client._ls(self.get_path(dir_path))

    async def exists(self, path: AsyncPath):
        return await self.client._exists(self.get_path(path))

    async def create_bucket(self, path: AsyncPath):
        return await self.client._mkdir(
            self.get_path(path),
            create_parents=True,
            enable_versioning=False,
            # acl="public-read",
        )

    async def read(self, path: AsyncPath):
        stor_path = self.get_path(path)
        logger.debug(f"Getting {stor_path}...")
        try:
            data = await self.client._cat_file(stor_path)
        except (NotFound, FileNotFoundError):
            raise FileNotFoundError  # for jinja loaders
        logger.debug(f"Got - {stor_path}")
        return data

    async def write(self, path: AsyncPath, data: t.Any) -> None:
        stor_path = self.get_path(path)
        logger.debug(f"Saving {stor_path}...")
        await self.client._pipe_file(stor_path, data)
        logger.debug(f"Saved - {stor_path}")

    async def delete(self, path: AsyncPath) -> None:
        stor_path = self.get_path(path)
        logger.debug(f"Deleting {stor_path}...")
        await self.client._rm_file(stor_path)
        logger.debug(f"Deleted - {stor_path}")


class StorageBase:
    client: t.Any

    # session: t.Any

    async def init(self) -> t.NoReturn:
        loop = asyncio.get_running_loop()
        self.client = self.client(asynchronous=True, loop=loop)
        for bucket in ac.storage.buckets:
            setattr(self, bucket, StorageBucket(self.client, bucket))
            logger.debug(f"{bucket.title()} storage bucket initialized.")
        logger.info("Storage initialized.")


# class BaseStorage:  # pragma: no cover
#     def get_name(self, name: str) -> str:
#         ...
#
#     def get_path(self, name: str) -> str:
#         ...
#
#     def get_size(self, name: str) -> int:
#         ...
#
#     def open(self, name: str) -> BinaryIO:
#         ...
#
#     def write(self, file: BinaryIO, name: str) -> str:
#         ...
#
#
# class StorageFile:
#     """
#     The file object returned by the storage.
#     """
#
#     def __init__(self, *, name: str, storage: BaseStorage) -> None:
#         self._name = name
#         self._storage = storage
#
#     @property
#     def name(self) -> str:
#         """File name including extension."""
#
#         return self._storage.get_name(self._name)
#
#     @property
#     def path(self) -> str:
#         """Complete file path."""
#
#         return self._storage.get_path(self._name)
#
#     @property
#     def size(self) -> int:
#         """File size in bytes."""
#
#         return self._storage.get_size(self._name)
#
#     def open(self) -> BinaryIO:
#         """
#         Open a file handle of the file.
#         """
#
#         return self._storage.open(self._name)
#
#     def write(self, file: BinaryIO) -> str:
#         """
#         Write input file which is opened in binary mode to destination.
#         """
#
#         return self._storage.write(file=file, name=self._name)
#
#     def __str__(self) -> str:
#         return self.path
#
#
# class StorageImage(StorageFile):
#     """
#     Inherits features of `StorageFile` and adds image specific properties.
#     """
#
#     def __init__(
#         self, *, name: str, storage: BaseStorage, height: int, width: int
#     ) -> None:
#         super().__init__(name=name, storage=storage)
#         self._width = width
#         self._height = height
#
#     @property
#     def height(self) -> int:
#         """
#         Image height in pixels.
#         """
#
#         return self._height
#
#     @property
#     def width(self) -> int:
#         """
#         Image width in pixels.
#         """
#
#         return self._width
