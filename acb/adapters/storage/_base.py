import typing as t
from functools import cached_property

try:
    import nest_asyncio
except ImportError:
    nest_asyncio = None
from anyio import Path as AsyncPath
from fsspec.asyn import AsyncFileSystem
from google.cloud.exceptions import NotFound
from acb.adapters import get_adapter, tmp_path
from acb.config import AdapterBase, Config, Settings
from acb.debug import debug
from acb.depends import depends

if nest_asyncio:
    nest_asyncio.apply()


class StorageBaseSettings(Settings):
    prefix: str | None = None
    local_path: AsyncPath | None = tmp_path / "storage"
    user_project: str | None = None
    buckets: dict[str, str] = {
        "test": "test-bucket",
    }
    cors: dict[str, dict[str, list[str] | int]] | None = None
    local_fs: bool | None = False
    memory_fs: bool | None = False

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.prefix = self.prefix or config.app.name or ""
        self.user_project = self.user_project or config.app.name or ""
        storage_adapter = get_adapter("storage")
        if storage_adapter is not None:
            self.local_fs = storage_adapter.name in ("file", "memory")
            self.memory_fs = storage_adapter.name == "memory"
        else:
            self.local_fs = False
            self.memory_fs = False


class StorageBucketProtocol(t.Protocol):
    root: AsyncPath
    prefix: str | None
    name: str
    bucket: str
    client: t.Any

    def get_name(self, path: AsyncPath) -> str: ...

    def get_path(self, path: AsyncPath) -> str: ...

    def get_url(self, path: AsyncPath) -> str: ...

    async def get_date_created(self, path: AsyncPath) -> t.Any: ...

    async def get_date_updated(self, path: AsyncPath) -> t.Any: ...

    async def get_size(self, path: AsyncPath) -> int: ...

    @staticmethod
    async def get_checksum(path: AsyncPath) -> int: ...

    async def get_signed_url(self, path: AsyncPath, expires: int = 3600) -> t.Any: ...

    async def stat(self, path: AsyncPath) -> t.Any: ...

    async def list(self, dir_path: AsyncPath) -> t.Any: ...

    async def exists(self, path: AsyncPath) -> t.Any: ...

    async def create_bucket(self, path: AsyncPath) -> t.Any: ...

    async def open(self, path: AsyncPath) -> t.BinaryIO: ...

    async def write(self, path: AsyncPath, data: t.Any) -> t.Any: ...

    async def delete(self, path: AsyncPath) -> t.Any: ...


class StorageBucket:
    root: AsyncPath
    client: t.Any
    bucket: str
    prefix: str | None = None
    config: Config = depends()

    def __init__(self, client: t.Any, bucket: str, prefix: str | None = None) -> None:
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
        from acb.actions.hash import hash

        checksum_hex = await hash.crc32c(path)
        return int(checksum_hex, 16)

    async def get_signed_url(self, path: AsyncPath, expires: int = 3600) -> t.Any:
        return await self.client._sign(self.get_path(path), expires=expires)

    async def stat(self, path: AsyncPath) -> t.Any:
        _path = self.get_path(path)
        if self.config.storage.memory_fs:
            info = self.client.info(_path)
            return {
                "name": info.get("name"),
                "size": info.get("size"),
                "type": info.get("type"),
                "mtime": self.client.modified(_path).timestamp(),
                "created": self.client.created(_path).timestamp(),
            }
        return await self.client._info(_path)

    async def list(self, dir_path: AsyncPath) -> t.Any:
        return await self.client._ls(self.get_path(dir_path))

    async def exists(self, path: AsyncPath) -> t.Any:
        if self.config.storage.memory_fs:
            return self.client.isfile(self.get_path(path))
        return await self.client._exists(self.get_path(path))

    async def create_bucket(self, path: AsyncPath) -> t.Any:
        create_args: dict[str, t.Any] = {
            "create_parents": True,
            "enable_versioning": False,
        }
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
            raise

    async def write(self, path: AsyncPath, data: t.Any) -> t.Any:
        stor_path = self.get_path(path)
        try:
            if self.config.storage.memory_fs:
                self.client.pipe_file(stor_path, data)
            else:
                await self.client._pipe_file(stor_path, data)
        except Exception as e:
            debug(e)
            raise

    async def delete(self, path: AsyncPath) -> t.Any:
        stor_path = self.get_path(path)
        await self.client._rm_file(stor_path)


class StorageProtocol(t.Protocol):
    file_system: t.Any
    templates: StorageBucket | None
    media: StorageBucket | None
    test: StorageBucket | None

    @cached_property
    def client(self) -> t.Any: ...

    async def init(self) -> None: ...


class StorageBase(AdapterBase):
    file_system: t.Any = AsyncFileSystem
    templates: StorageBucket | None = None
    media: StorageBucket | None = None
    test: StorageBucket | None = None

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()

    async def _create_client(self) -> t.Any:
        return self.file_system(asynchronous=True)

    async def get_client(self) -> t.Any:
        return await self._ensure_client()

    @property
    def client(self) -> t.Any:
        if self._client is None:
            msg = "Client not initialized. Call get_client() first."
            raise RuntimeError(msg)
        return self._client

    async def init(self) -> None:
        client = await self.get_client()
        for bucket in self.config.storage.buckets:
            setattr(self, bucket, StorageBucket(client, bucket))
            self.logger.debug(f"{bucket.title()} storage bucket initialized")


class StorageMediaProtocol(t.Protocol):
    _storage: StorageBucket
    _name: str

    def name(self) -> str: ...

    def path(self) -> str: ...

    async def size(self) -> t.Any: ...

    async def checksum(self) -> t.Any: ...

    async def open(self) -> t.Any: ...

    async def write(self, file: t.BinaryIO) -> t.Any: ...


class StorageFile:
    _storage: StorageBucket
    _name: str

    def __init__(self, *, name: str, storage: StorageBucket) -> None:
        self._storage = storage
        self._name = name

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
        self,
        *,
        name: str,
        storage: StorageBucket,
        height: int,
        width: int,
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
