import datetime as _datetime
import linecache
import sys
import typing as t
from dataclasses import dataclass
from re import search
from types import FrameType

import dill
import msgspec
import yaml
from anyio import Path as AsyncPath

__all__: list[str] = ["load", "dump", "encode", "decode"]


def yaml_encode(
    obj: t.Any,
    *,
    enc_hook: t.Callable[[t.Any], t.Any] | None = None,
    sort_keys: bool = False,
) -> bytes:
    dumper = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
    dumper.add_representer(
        type(None),
        lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
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
    path: AsyncPath | None = None
    action: str | None = None
    sort_keys: bool = True
    use_list: bool = False
    secure: bool = False
    secret_key: str | None = None
    secure_salt: str | None = None
    serializer: t.Callable[..., t.Any] | None = None

    def __init__(self) -> None:
        self.serializers = serializers.__dict__
        for s in self.serializers:
            setattr(self, s, self.__call__)

    async def process(self, obj: t.Any, **kwargs: object) -> t.Any:
        if self.action in ("load", "decode"):
            if self.serializer is msgspec.msgpack:  # type: ignore
                kwargs["use_list"] = self.use_list
            if isinstance(obj, AsyncPath):
                obj = await obj.read_text()
            return self.serializer.decode(obj, **kwargs)  # type: ignore
        elif self.action in ("dump", "encode"):
            if self.serializer is msgspec.yaml:  # type: ignore
                kwargs["sort_keys"] = self.sort_keys
            data: bytes = self.serializer.encode(obj, **kwargs)  # type: ignore
            if isinstance(self.path, AsyncPath):
                return await self.path.write_bytes(data)
            return data

    def get_vars(self, frame: FrameType) -> tuple[str, t.Any]:
        code_context = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
        pattern = r"await\s(\w+)\.(\w+)\("
        calling_method = search(pattern, code_context)
        return calling_method.group(1), self.serializers[calling_method.group(2)]

    async def __call__(
        self,
        obj: t.Any,
        path: AsyncPath | None = None,
        sort_keys: bool = False,
        use_list: bool = False,
        **kwargs: object,
    ) -> t.Any:
        self.path = path
        self.sort_keys = sort_keys
        self.use_list = use_list
        self.action, self.serializer = self.get_vars(sys._getframe(1))
        return await self.process(obj, **kwargs)  # type: ignore


dump = load = encode = decode = Encode()
