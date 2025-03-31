import typing as t
from functools import cached_property

import nest_asyncio
from anyio import Path as AsyncPath
from fsspec.asyn import AsyncFileSystem
from google.cloud.exceptions import NotFound
from acb.actions import hash
from acb.adapters import get_adapter, tmp_path
from acb.config import AdapterBase, Config, Settings, import_adapter
from acb.debug import debug
from acb.depends import depends

Logger = import_adapter()
nest_asyncio.apply()


class StorageBaseSettings(Settings):
    prefix: t.Optional[str] = None
    local_path: t.Optional[AsyncPath] = tmp_path / "storage"
    user_project: t.Optional[str] = None
    buckets: dict[str, str] = {"test": "test-bucket"}
    cors: t.Optional[dict[str, dict[str, list[str] | int]]] = None
    local_fs: t.Optional[bool] = False
    memory_fs: t.Optional[bool] = False

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.prefix = self.prefix or config.app.name or ""
        self.user_project = self.user_project or config.app.name or ""
        self.local_fs = get_adapter("storage").name in ("file", "memory")
        self.memory_fs = get_adapter("storage").name == "memory"


class StorageBucket:
    config: Config = depends()
    logger: Logger = depends()

    def __init__(
        self,
        client: t.Any,
        bucket: str,
        prefix: t.Optional[str] = None,
    ) -> None:
        self.client = client
        self.name = bucket
        self.bucket = self.config.storage.buckets[bucket]
        self.prefix = prefix or self.config.storage.prefix
        self.root = AsyncPath(f"{self.bucket}/{self.prefix}")

    def get_name(self, path: AsyncPath) -> str:
        return path.name

    def get_path(self, path: AsyncPath) -> str:
        if self.config.storage.local_fs:
            return str(path)
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
        _path = self.get_path(path)
        if self.config.storage.memory_fs:
            info = self.client.info(_path)
            stat = dict(
                name=info.get("name"),
                size=info.get("size"),
                type=info.get("type"),
                mtime=self.client.modified(_path).timestamp(),
                created=self.client.created(_path).timestamp(),
            )
            return stat
        return await self.client._info(_path)

    async def list(self, dir_path: AsyncPath) -> t.Any:
        return await self.client._ls(self.get_path(dir_path))

    async def exists(self, path: AsyncPath) -> t.Any:
        if get_adapter("storage").name == "memory":
            return self.client.isfile(self.get_path(path))
        return await self.client._exists(self.get_path(path))

    async def create_bucket(self, path: AsyncPath) -> t.Any:
        create_args: dict[str, t.Any] = dict(
            create_parents=True,
            enable_versioning=False,
        )
        if self.name == "media":
            create_args["acl"] = "public-read"
            if self.config.storage.cors:
                self.client.set_cors(self.name, self.config.storage.cors)
        elif self.name == "templates":
            create_args["enable_versioning"] = True
        return await self.client._mkdir(self.get_path(path), **create_args)

    async def open(self, path: AsyncPath) -> t.BinaryIO:
        try:
            async with self.client.open(self.get_path(path), "rb") as f:
                return f.read()
        except (NotFound, FileNotFoundError, RuntimeError):
            raise FileNotFoundError
        except Exception as e:
            debug(e)
            raise e

    async def write(self, path: AsyncPath, data: t.Any) -> t.Any:
        stor_path = self.get_path(path)
        try:
            if get_adapter("storage").name == "memory":
                self.client.pipe_file(stor_path, data)
            else:
                await self.client._pipe_file(stor_path, data)
        except Exception as e:
            debug(e)
            raise e

    async def delete(self, path: AsyncPath) -> t.Any:
        stor_path = self.get_path(path)
        await self.client._rm_file(stor_path)


class StorageProtocol(t.Protocol):
    file_system: t.Any = AsyncFileSystem

    @cached_property
    def client(self) -> AsyncFileSystem: ...
    async def init(self) -> None: ...


class StorageBase(AdapterBase):
    file_system: t.Type[AsyncFileSystem]
    templates: StorageBucket | None = None
    media: StorageBucket | None = None
    test: StorageBucket | None = None

    @cached_property
    def client(self) -> AsyncFileSystem:
        return self.file_system(asynchronous=True)

    async def init(self) -> None:
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
