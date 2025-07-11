import typing as t

from aiocache import BaseCache
from aiocache.serializers import BaseSerializer
from msgspec import msgpack
from acb.actions.compress import compress, decompress
from acb.config import Config, Settings
from acb.depends import depends
from acb.logger import Logger


class CacheBaseSettings(Settings):
    default_ttl: int = 86400
    query_ttl: int = 600
    response_ttl: int | None = 3600
    template_ttl: int | None = 86400

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.response_ttl = self.default_ttl if config.deployed else 1


class MsgPackSerializer(BaseSerializer):
    def __init__(self, *args: t.Any, use_list: bool = True, **kwargs: t.Any) -> None:
        self.use_list = use_list
        super().__init__(*args, **kwargs)

    def dumps(self, value: t.Any) -> str:
        msgpack_data = msgpack.encode(value)
        return compress.brotli(msgpack_data).decode("latin-1")

    def loads(self, value: str) -> t.Any:
        if not value:
            return None
        data_bytes = value.encode("latin-1")
        msgpack_data = decompress.brotli(data_bytes)
        if not msgpack_data:
            return None
        try:
            msgpack_bytes = msgpack_data.encode("latin-1")
        except AttributeError:
            msgpack_bytes = t.cast("bytes", msgpack_data)
        return msgpack.decode(msgpack_bytes)


class CacheProtocol(t.Protocol):
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...

    async def get(self, key: str) -> bytes | None: ...

    async def exists(self, key: str) -> bool: ...

    async def clear(self, namespace: str) -> None: ...

    async def scan(self, pattern: str) -> t.AsyncIterator[str]: ...


class CacheBase(BaseCache):
    config: Config = depends()
    logger: Logger = depends()

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        self._client = None
        self._client_lock = None

    async def _ensure_client(self) -> t.Any:
        if self._client is None:
            if self._client_lock is None:
                import asyncio

                self._client_lock = asyncio.Lock()
            async with self._client_lock:
                if self._client is None:
                    self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> t.Any:
        msg = "Subclasses must implement _create_client()"
        raise NotImplementedError(msg)
