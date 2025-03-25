import hashlib
import typing as t

import dill
from aiocache import BaseCache
from aiocache.serializers import BaseSerializer
from itsdangerous.serializer import Serializer as SecureSerializer
from msgspec import msgpack
from acb.actions.compress import compress, decompress
from acb.config import AdapterBase, Config, Settings, import_adapter
from acb.depends import depends

Logger = import_adapter()


class CacheBaseSettings(Settings):
    default_ttl: int = 86400
    query_ttl: int = 600
    response_ttl: t.Optional[int] = 3600
    template_ttl: t.Optional[int] = 86400

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.response_ttl = self.default_ttl if config.deployed else 1


class MsgPackSerializer(BaseSerializer):
    def __init__(self, *args: t.Any, use_list: bool = True, **kwargs: t.Any) -> None:
        self.use_list = use_list
        super().__init__(*args, **kwargs)

    def dumps(self, value: t.Any) -> bytes:  # type: ignore
        msgpack_data = msgpack.encode(value)
        return compress.brotli(msgpack_data)

    def loads(self, value: bytes | None) -> t.Any:  # type: ignore
        if value is None:
            return None
        msgpack_data = decompress.brotli(value)
        return msgpack.decode(msgpack_data)  # type: ignore


class SecurePickleSerializer(BaseSerializer):
    DEFAULT_ENCODING = None

    @depends.inject
    def __init__(
        self, config: Config = depends(), *args: t.Any, **kwargs: t.Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.serializer = SecureSerializer(
            secret_key=config.app.secret_key.get_secret_value(),
            salt=config.app.secure_salt.get_secret_value(),
            serializer=dill,
            signer_kwargs=dict(digest_method=hashlib.sha256),
        )

    def dumps(self, value: t.Any) -> bytes:  # type: ignore
        serialized_data = self.serializer.dumps(value)
        return compress.brotli(serialized_data)

    def loads(self, value: bytes | None) -> t.Any:  # type: ignore
        if value is None:
            return None
        serialized_data = decompress.brotli(value)
        return self.serializer.loads(serialized_data)


class CacheProtocol(t.Protocol):
    async def set(
        self, key: str, value: bytes, ttl: t.Optional[int] = None
    ) -> None: ...
    async def get(self, key: str) -> t.Optional[bytes]: ...
    async def exists(self, key: str) -> bool: ...
    async def clear(self, namespace: str) -> None: ...
    async def scan(self, pattern: str) -> t.AsyncIterator[str]: ...  # noqa


class CacheBase(AdapterBase, BaseCache): ...
