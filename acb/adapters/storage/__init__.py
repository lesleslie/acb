import asyncio
import typing as t


from acb.config import ac
from acb.config import Settings
from acb.depends import depends
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
        self.prefix = self.prefix or ac.app.name or ""
        self.user_project = self.user_project or ac.app.name or ""  # used for billing


class StorageBucket:
    def __init__(self, client, bucket: str, prefix: t.Optional[str] = None) -> None:
        self.client = client
        self.bucket = ac.storage.buckets[bucket]
        self.prefix = prefix or ac.storage.prefix
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

    async def init(self) -> None:
        loop = asyncio.get_running_loop()
        self.client = self.client(asynchronous=True, loop=loop)
        for bucket in ac.storage.buckets:
            setattr(self, bucket, StorageBucket(self.client, bucket))
            logger.debug(f"{bucket.title()} storage bucket initialized")
        logger.debug("Storage initialized")

    def get_name(self, name: str) -> str:
        ...

    def get_path(self, name: str) -> str:
        ...

    def get_size(self, name: str) -> int:
        ...

    def open(self, name: str) -> t.BinaryIO:
        ...

    def write(self, file: t.BinaryIO, name: str) -> str:
        ...


class StorageFile:
    _storage: StorageBase = depends()

    def __init__(self, *, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._storage.get_name(self._name)

    @property
    def path(self) -> str:
        return self._storage.get_path(self._name)

    @property
    def size(self) -> int:
        return self._storage.get_size(self._name)

    def open(self) -> t.BinaryIO:
        return self._storage.open(self._name)

    def write(self, file: t.BinaryIO) -> str:
        return self._storage.write(file=file, name=self._name)

    def __str__(self) -> str:
        return self.path


class StorageImage(StorageFile):
    def __init__(
        self, *, name: str, storage: StorageBase, height: int, width: int
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
