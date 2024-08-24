import pickle
import typing as t

from aiocache.serializers import BaseSerializer
from blake3 import blake3  # type: ignore
from itsdangerous.serializer import Serializer as SecureSerializer
from msgspec import msgpack
from acb.adapters import AdapterBase, import_adapter
from acb.config import Config, Settings
from acb.depends import depends

Logger = import_adapter()


class CacheBaseSettings(Settings):
    default_timeout: int = 86400

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.default_timeout = self.default_timeout if config.deployed else 1


class MsgSpecSerializer(BaseSerializer):
    def __init__(self, *args: t.Any, use_list: bool = True, **kwargs: t.Any) -> None:
        self.use_list = use_list
        super().__init__(*args, **kwargs)

    def dumps(self, value: t.Any) -> bytes:  # type: ignore
        return msgpack.encode(value)

    def loads(self, value: bytes | None) -> t.Any:  # type: ignore
        if value is None:
            return None
        return msgpack.decode(value)


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
            serializer=pickle,
            signer_kwargs=dict(digest_method=blake3),
        )

    def dumps(self, value: t.Any) -> bytes:  # type: ignore
        return self.serializer.dumps(value)

    def loads(self, value: bytes | None) -> t.Any:  # type: ignore
        if value is None:
            return None
        return self.serializer.loads(value)


class CacheBase(AdapterBase): ...
