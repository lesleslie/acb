import typing as t

from acb.actions import hash
from acb.adapters.logger import Logger
from acb.config import Config
from acb.config import Settings
from acb.depends import depends
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
    buckets: dict[str, str] = {"test": "test-bucket"}
    loggers: t.Optional[list[str]] = []

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.prefix = self.prefix or config.app.name or ""
        self.user_project = (
            self.user_project or config.app.name or ""
        )  # used for billing


class StorageBucket:
    config: Config = depends()
    logger: Logger = depends()  # type: ignore

    def __init__(
        self,
        client: t.Any,
        bucket: str,
        prefix: t.Optional[str] = None,
    ) -> None:
        self.client = client
        self.bucket = self.config.storage.buckets[bucket]
        self.prefix = prefix or self.config.storage.prefix
        self.root = AsyncPath(f"{self.bucket}/{self.prefix}")

    def get_name(self, path: AsyncPath) -> str:
        return path.name

    def get_path(self, path: AsyncPath) -> str:
        return str(self.root / path)

    def get_url(self, path: AsyncPath) -> str:
        return self.client.url(self.get_path(path))

    async def get_date_created(self, path: AsyncPath) -> t.Any:
        return (await self.stat(path))["timeCreated"]

    async def get_date_updated(self, path: AsyncPath) -> t.Any:
        return (await self.stat(path))["updated"]

    async def get_size(self, path: AsyncPath) -> int:
        return (await self.stat(path))["size"]

    @staticmethod
    async def get_checksum(path: AsyncPath) -> int:
        return await hash.crc32c(path)  # type: ignore

    async def get_signed_url(self, path: AsyncPath, expires: int = 3600) -> t.Any:
        return await self.client._sign(self.get_path(path), expires=expires)

    async def stat(self, path: AsyncPath) -> t.Any:
        return await self.client._info(self.get_path(path))

    async def list(self, dir_path: AsyncPath) -> t.Any:
        return await self.client._ls(self.get_path(dir_path))

    async def exists(self, path: AsyncPath) -> t.Any:
        return await self.client._exists(self.get_path(path))

    async def create_bucket(self, path: AsyncPath) -> t.Any:
        return await self.client._mkdir(
            self.get_path(path),
            create_parents=True,
            enable_versioning=False,
            # acl="public-read",
        )

    async def read(self, path: AsyncPath) -> t.Any:
        stor_path = self.get_path(path)
        self.logger.debug(f"Getting {stor_path}...")
        try:
            data = await self.client._cat_file(stor_path)
        except (NotFound, FileNotFoundError):
            raise FileNotFoundError  # for jinja loaders
        self.logger.debug(f"Got - {stor_path}")
        return data

    async def open(self, path: AsyncPath) -> t.BinaryIO:
        async with self.client.open(self.get_path(path), "rb") as f:
            return f.read()

    async def write(self, path: AsyncPath, data: t.Any) -> t.Any:
        stor_path = self.get_path(path)
        self.logger.debug(f"Saving {stor_path}...")
        await self.client._pipe_file(stor_path, data)
        self.logger.debug(f"Saved - {stor_path}")

    async def delete(self, path: AsyncPath) -> t.Any:
        stor_path = self.get_path(path)
        self.logger.debug(f"Deleting {stor_path}...")
        await self.client._rm_file(stor_path)
        self.logger.debug(f"Deleted - {stor_path}")


class StorageBase:
    client: t.Any
    config: Config = depends()
    logger: Logger = depends()  # type: ignore

    async def init(self) -> None:
        self.client = self.client(asynchronous=True)
        for bucket in self.config.storage.buckets:
            setattr(self, bucket, StorageBucket(self.client, bucket))
            self.logger.debug(f"{bucket.title()} storage bucket initialized")


class StorageFile:
    def __init__(self, *, name: str, storage: StorageBucket) -> None:
        self._storage: StorageBucket = storage
        self._name: str = name

    @property
    def name(self) -> str:
        return self._storage.get_name(AsyncPath(self._name))

    @property
    def path(self) -> str:
        return self._storage.get_path(AsyncPath(self._name))

    @property
    async def size(self) -> t.Any:
        return await self._storage.get_size(AsyncPath(self._name))

    @property
    async def checksum(self) -> t.Any:
        return await self._storage.get_checksum(AsyncPath(self._name))

    async def open(self) -> t.Any:
        return await self._storage.open(AsyncPath(self._name))

    async def write(self, file: t.BinaryIO) -> t.Any:
        return await self._storage.write(path=AsyncPath(self._name), data=file)

    def __str__(self) -> str:
        return self.path


class StorageImage(StorageFile):
    def __init__(
        self, *, name: str, storage: StorageBucket, height: int, width: int
    ) -> None:
        super().__init__(name=name, storage=storage)
        self._width = width
        self._height = height

    @property
    def height(self) -> int:
        return self._height

    @property
    def width(self) -> int:
        return self._width
