import datetime as _datetime
import linecache
import sys
import typing as t
from dataclasses import dataclass
from re import search
from types import FrameType
from warnings import warn

import dill
import msgspec
import yaml
from aiopath import AsyncPath
from blake3 import blake3  # type: ignore
from itsdangerous import Serializer as SecureSerializer
from pydantic import SecretStr


def yaml_encode(
    obj: t.Any,
    *,
    enc_hook: t.Optional[t.Callable[[t.Any], t.Any]] = None,
    sort_keys: bool = False,
) -> bytes:
    dumper = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
    dumper.add_representer(
        type(None),
        lambda dumper, value: dumper.represent_scalar(  # type: ignore
            "tag:yaml.org,2002:null", ""
        ),
    )
    return yaml.dump_all(
        [
            msgspec.yaml._to_builtins(
                obj,
                builtin_types=(_datetime.datetime, _datetime.date),
                enc_hook=enc_hook,
            )
        ],
        encoding="utf-8",
        Dumper=dumper,  # type: ignore
        allow_unicode=True,
        sort_keys=sort_keys,
    )


msgspec.yaml.encode = yaml_encode


@dataclass
class Serializers:
    json: t.Any = msgspec.json
    yaml: t.Any = msgspec.yaml
    msgpack: t.Any = msgspec.msgpack
    pickle: t.Any = dill
    toml: t.Any = msgspec.toml

    def __post_init__(self) -> None:
        self.pickle.encode = dill.dumps
        self.pickle.decode = dill.loads


serializers = Serializers()


class Encode:
    json: t.Callable[..., t.Any]
    yaml: t.Callable[..., t.Any]
    msgpack: t.Callable[..., t.Any]
    toml: t.Callable[..., t.Any]
    pickle: t.Callable[..., t.Any]
    serializers: dict[str, t.Callable[..., t.Any]]
    path: t.Optional[AsyncPath] = None
    action: t.Optional[str] = None
    sort_keys: bool = True
    use_list: bool = False
    secure: bool = False
    secret_key: t.Optional[str] = None
    secure_salt: t.Optional[str] = None
    serializer: t.Optional[t.Callable[..., t.Any]] = None

    def __init__(self) -> None:
        self.serializers = serializers.__dict__
        for s in self.serializers:
            setattr(self, s, self.__call__)

    async def process(self, obj: t.Any, **kwargs: object) -> t.Any:
        if self.action in ("load", "decode"):
            if self.serializer is msgspec.msgpack:
                kwargs["use_list"] = self.use_list
            if isinstance(obj, AsyncPath):
                obj = await obj.read_text()
            return self.serializer.decode(obj, **kwargs)  # type: ignore
        elif self.action in ("dump", "encode"):
            if self.serializer is msgspec.yaml:
                kwargs["sort_keys"] = self.sort_keys
            data: bytes = self.serializer.encode(obj, **kwargs)  # type: ignore
            if isinstance(self.path, AsyncPath):
                return await self.path.write_bytes(data)
            return data

    @staticmethod
    def get_vars(frame: FrameType) -> tuple[str, t.Any]:
        code_context = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
        pattern = r"await\s(\w+)\.(\w+)\("
        calling_method = search(pattern, code_context)
        return calling_method.group(1), calling_method.group(2)  # type: ignore

    def get_serializer(self, serializer: t.Any) -> t.Any:
        return (
            serializer
            if not self.secure
            else SecureSerializer(
                secret_key=self.secret_key,  # type: ignore
                salt=self.secure_salt,
                serializer=serializer,
                signer_kwargs=dict(digest_method=blake3),
            )
        )

    async def __call__(
        self,
        obj: t.Any,
        path: t.Optional[AsyncPath] = None,
        sort_keys: bool = False,
        use_list: bool = False,
        secret_key: t.Optional[SecretStr] = None,
        secure_salt: t.Optional[SecretStr] = None,
        **kwargs: object,
    ) -> dict[str, str] | bytes:
        self.path = path
        self.sort_keys = sort_keys
        self.use_list = use_list
        self.secret_key = secret_key.get_secret_value() if secret_key else None
        self.secure_salt = secure_salt.get_secret_value() if secure_salt else None
        self.action, serializer_name = self.get_vars(sys._getframe(1))
        self.secure = all((secret_key, secure_salt))
        if not self.secure and (secret_key or secure_salt):
            warn(
                f"{serializer_name.title()} serializer won't sign "
                f"objects unless both "
                f"secret_key and secure_salt are set"
            )
        self.serializer = self.get_serializer(self.serializers[serializer_name])
        return await self.process(obj, **kwargs)  # type: ignore


dump = load = encode = decode = Encode()
