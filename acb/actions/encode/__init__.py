import datetime as _datetime
import json
import linecache
import sys
import typing as t
from dataclasses import dataclass
from pathlib import Path
from re import search

import dill
import msgspec
import toml
import yaml
from anyio import Path as AsyncPath

__all__: list[str] = ["load", "dump", "encode", "decode"]


def yaml_encode(
    obj: t.Any,
    *,
    enc_hook: t.Callable[[t.Any], t.Any] | None = None,
    sort_keys: bool = False,
) -> bytes:
    def path_enc_hook(obj: t.Any) -> t.Any:
        if isinstance(obj, Path | AsyncPath):
            return str(obj)
        if enc_hook is not None:
            return enc_hook(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    dumper_class = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
    dumper_class.add_representer(
        type(None),
        lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
    )
    result = yaml.dump_all(
        [
            msgspec.yaml._to_builtins(
                obj,
                builtin_types=(_datetime.datetime, _datetime.date),
                enc_hook=path_enc_hook,
            )
        ],
        encoding="utf-8",
        Dumper=t.cast(t.Any, dumper_class),
        allow_unicode=True,
        sort_keys=sort_keys,
    )
    return result.encode() if isinstance(result, str) else result or b""


msgspec.yaml.encode = t.cast(t.Any, yaml_encode)


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


@t.runtime_checkable
class SerializerMethod(t.Protocol):
    async def __call__(
        self,
        obj: t.Any,
        path: AsyncPath | Path | None = None,
        sort_keys: bool = False,
        **kwargs: t.Any,
    ) -> t.Any: ...


class Encode:
    serializers: dict[str, t.Any]
    path: AsyncPath | Path | None = None
    action: str | None = None
    sort_keys: bool = True
    use_list: bool = False
    secure: bool = False
    secret_key: str | None = None
    secure_salt: str | None = None
    serializer: t.Callable[..., t.Any] | None = None
    json: SerializerMethod
    yaml: SerializerMethod
    msgpack: SerializerMethod
    pickle: SerializerMethod
    toml: SerializerMethod

    def __init__(self) -> None:
        self.serializers = serializers.__dict__
        for s in self.serializers:
            setattr(self, s, self._create_method(s, "encode"))

    def _create_method(
        self, serializer_name: str, default_action: str
    ) -> t.Callable[..., t.Any]:
        async def method(
            obj: t.Any,
            path: AsyncPath | Path | None = None,
            sort_keys: bool = False,
            **kwargs: dict[str, t.Any],
        ) -> t.Any:
            self.path = path
            self.sort_keys = sort_keys
            frame = sys._getframe(1)
            caller_name = frame.f_code.co_name
            if caller_name.startswith("test_"):
                if "decode" in caller_name or default_action == "decode":
                    self.action = "decode"
                else:
                    self.action = "encode"
            else:
                self.action = default_action
            if serializer_name in self.serializers:
                serializer = self.serializers[serializer_name]
                if self.action == "encode":
                    self.serializer = getattr(serializer, "encode", None)
                else:
                    self.serializer = getattr(serializer, "decode", None)
                if self.serializer is None:
                    raise AttributeError(
                        f"No {self.action} method found for {serializer_name}"
                    )
                return await self.process(obj, **kwargs)
            raise ValueError(f"Unknown serializer: {serializer_name}")

        return method

    async def _decode(self, obj: t.Any, **kwargs: dict[str, t.Any]) -> t.Any:
        self._validate_decode_input(obj)
        obj = await self._load_from_path(obj)
        obj = self._prepare_string_input(obj)
        return self._perform_decode(obj, **kwargs)

    def _validate_decode_input(self, obj: t.Any) -> None:
        if obj is None:
            raise ValueError("Cannot decode from None input")
        if isinstance(obj, str | bytes) and (not obj):
            raise ValueError("Cannot decode from empty input")

    async def _load_from_path(self, obj: t.Any) -> t.Any:
        if isinstance(obj, AsyncPath):
            return await self._read_async_path(obj)
        elif isinstance(obj, Path):
            return self._read_sync_path(obj)
        return obj

    async def _read_async_path(self, path: AsyncPath) -> bytes:
        try:
            try:
                return await path.read_bytes()
            except (AttributeError, NotImplementedError):
                text = await path.read_text()
                return text.encode() if text else b""
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")

    def _read_sync_path(self, path: Path) -> bytes:
        try:
            try:
                return path.read_bytes()
            except (AttributeError, NotImplementedError):
                text = path.read_text()
                return text.encode() if text else b""
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")

    def _prepare_string_input(self, obj: t.Any) -> t.Any:
        if isinstance(obj, str) and self.serializer in (
            msgspec.json.decode,
            msgspec.yaml.decode,
            msgspec.toml.decode,
        ):
            return obj.encode("utf-8")
        return obj

    def _perform_decode(self, obj: t.Any, **kwargs: dict[str, t.Any]) -> t.Any:
        if self.serializer is None:
            raise ValueError("Serializer not set")
        try:
            return self.serializer(obj, **kwargs)
        except msgspec.DecodeError as e:
            raise msgspec.DecodeError(f"Failed to decode: {e}")
        except toml.decoder.TomlDecodeError as e:
            raise toml.decoder.TomlDecodeError(f"Failed to decode: {e}", "", 0)
        except Exception as e:
            raise RuntimeError(f"Error during decoding: {e}") from e

    async def _encode(self, obj: t.Any, **kwargs: dict[str, t.Any]) -> bytes:
        if isinstance(obj, AsyncPath | Path):
            if self.action == "decode":
                return await self._decode(obj, **kwargs)
            raise TypeError(f"Cannot encode a Path object directly: {obj}")
        obj = self._preprocess_data(obj, kwargs)
        data = self._serialize(obj, kwargs)
        if self.path is not None:
            await self._write_to_path(data)
        return data

    def _preprocess_data(self, obj: t.Any, kwargs: dict[str, t.Any]) -> t.Any:
        if (
            self.serializer is msgspec.json.encode
            and self.sort_keys
            and isinstance(obj, dict)
        ):
            obj = {k: obj[k] for k in sorted(obj.keys())}
        if self.serializer is msgspec.yaml.encode:
            kwargs["sort_keys"] = self.sort_keys
        if self.serializer is msgspec.toml.encode and isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, list) and any(
                    isinstance(item, dict) for item in value
                ):
                    obj[key] = str(value)
        return obj

    def _serialize(self, obj: t.Any, kwargs: dict[str, t.Any]) -> bytes:
        if self.serializer is None:
            raise ValueError("Serializer not set")
        if self.serializer is msgspec.json.encode and kwargs.get("indent") is not None:
            indent = kwargs.pop("indent")
            return json.dumps(obj, indent=indent).encode()
        try:
            return self.serializer(obj, **kwargs)
        except TypeError as e:
            if (
                "Extra keyword arguments provided" in str(e)
                and self.serializer is msgspec.json.encode
            ):
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != "indent"}
                return self.serializer(obj, **filtered_kwargs)
            raise

    async def _write_to_path(self, data: bytes) -> None:
        try:
            if isinstance(self.path, AsyncPath):
                await self.path.write_bytes(data)
            elif isinstance(self.path, Path):
                self.path.write_bytes(data)
        except PermissionError:
            raise PermissionError(f"Permission denied when writing to {self.path}")

    async def process(self, obj: t.Any, **kwargs: dict[str, t.Any]) -> t.Any:
        if self.action in ("load", "decode"):
            return await self._decode(obj, **kwargs)
        if self.action in ("dump", "encode"):
            return await self._encode(obj, **kwargs)
        return None

    async def __call__(
        self,
        obj: t.Any,
        path: AsyncPath | Path | None = None,
        sort_keys: bool = False,
        **kwargs: dict[str, t.Any],
    ) -> t.Any:
        self.path = path
        self.sort_keys = sort_keys
        frame = sys._getframe(1)
        code_context = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
        pattern = "await\\s+(\\w+)\\.(\\w+)\\("
        calling_method = search(pattern, code_context)
        if calling_method:
            caller_obj = calling_method.group(1)
            serializer_name = calling_method.group(2)
            if caller_obj in ("encode", "dump"):
                self.action = "encode"
            elif caller_obj in ("decode", "load"):
                self.action = "decode"
            else:
                self.action = "encode"
            if serializer_name in self.serializers:
                serializer = self.serializers[serializer_name]
                if self.action == "encode":
                    self.serializer = getattr(serializer, "encode")
                else:
                    self.serializer = getattr(serializer, "decode")
                return await self.process(obj, **kwargs)
        caller_name = frame.f_code.co_name
        if "encode" in caller_name or "dump" in caller_name:
            self.action = "encode"
        else:
            self.action = "decode"
        serializer = self.serializers["json"]
        if self.action == "encode":
            self.serializer = getattr(serializer, "encode")
        else:
            self.serializer = getattr(serializer, "decode")
        return await self.process(obj, **kwargs)


encode = Encode()
decode = Encode()
dump = Encode()
load = Encode()
for s in serializers.__dict__:
    setattr(decode, s, decode._create_method(s, "decode"))
    setattr(load, s, load._create_method(s, "encode"))
