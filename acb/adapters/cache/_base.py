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
    default_timeout: int = 86400

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.default_timeout = self.default_timeout if config.deployed else 1


class MsgPackSerializer(BaseSerializer):
    def __init__(self, *args: t.Any, use_list: bool = True, **kwargs: t.Any) -> None:
        self.use_list = use_list
        super().__init__(*args, **kwargs)

    def dumps(self, value: t.Any) -> bytes:  # type: ignore
        return compress.brotli(msgpack.encode(value))

    def loads(self, value: bytes | None) -> t.Any:  # type: ignore
        if value is None:
            return None
        return msgpack.decode(decompress.brotli(value))  # type: ignore


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
        return compress.brotli(self.serializer.dumps(value))

    def loads(self, value: bytes | None) -> t.Any:  # type: ignore
        if value is None:
            return None
        return self.serializer.loads(decompress.brotli(value))


class CacheBase(AdapterBase, BaseCache): ...
