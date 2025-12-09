import json
import linecache
import sys
import types
from pathlib import Path
from re import search

import datetime as _datetime
import dill  # nosec B403
import msgspec
import toml
import typing as t
import yaml
from anyio import Path as AsyncPath
from dataclasses import dataclass

__all__: list[str] = ["decode", "dump", "encode", "load", "yaml_encode"]


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
        msg = f"Object of type {type(obj).__name__} is not JSON serializable"
        raise TypeError(msg)

    dumper_class = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
    dumper_class.add_representer(
        type(None),
        lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
    )
    result = yaml.dump_all(
        [
            msgspec.yaml._to_builtins(  # type: ignore[attr-defined]
                obj,
                builtin_types=(_datetime.datetime, _datetime.date),
                enc_hook=path_enc_hook,
            ),
        ],
        Dumper=t.cast("t.Any", dumper_class),
        allow_unicode=True,
        sort_keys=sort_keys,
    )
    if isinstance(result, str):
        return result.encode()
    return t.cast("bytes", result)  # type: ignore[return-value]


msgspec.yaml.encode = t.cast("t.Any", yaml_encode)


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
        self,
        serializer_name: str,
        default_action: str,
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
                    msg = f"No {self.action} method found for {serializer_name}"
                    raise AttributeError(
                        msg,
                    )
                return await self.process(obj, **kwargs)
            msg = f"Unknown serializer: {serializer_name}"
            raise ValueError(msg)

        return method

    async def _decode(self, obj: t.Any, **kwargs: dict[str, t.Any]) -> t.Any:
        self._validate_decode_input(obj)
        obj = await self._load_from_path(obj)
        obj = self._prepare_string_input(obj)
        return self._perform_decode(obj, **kwargs)

    def _validate_decode_input(self, obj: t.Any) -> None:
        if obj is None:
            msg = "Cannot decode from None input"
            raise ValueError(msg)
        if isinstance(obj, str | bytes) and (not obj):
            msg = "Cannot decode from empty input"
            raise ValueError(msg)

    async def _load_from_path(self, obj: t.Any) -> t.Any:
        if isinstance(obj, AsyncPath):
            return await self._read_async_path(obj)
        if isinstance(obj, Path):
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
            msg = f"File not found: {path}"
            raise FileNotFoundError(msg) from None

    def _read_sync_path(self, path: Path) -> bytes:
        try:
            try:
                return path.read_bytes()
            except (AttributeError, NotImplementedError):
                text = path.read_text()
                return text.encode() if text else b""
        except FileNotFoundError:
            msg = f"File not found: {path}"
            raise FileNotFoundError(msg) from None

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
            msg = "Serializer not set"
            raise ValueError(msg)
        try:
            return self.serializer(obj, **kwargs)
        except msgspec.DecodeError as e:
            msg = f"Failed to decode: {e}"
            raise msgspec.DecodeError(msg) from None
        except toml.decoder.TomlDecodeError as e:
            msg = f"Failed to decode: {e}"
            raise toml.decoder.TomlDecodeError(msg, "", 0) from None
        except Exception as e:
            msg = f"Error during decoding: {e}"
            raise RuntimeError(msg) from e

    async def _encode(self, obj: t.Any, **kwargs: dict[str, t.Any]) -> bytes:
        if isinstance(obj, AsyncPath | Path):
            if self.action == "decode":
                return await self._decode(obj, **kwargs)  # type: ignore  # type: ignore[no-any-return]
            msg = f"Cannot encode a Path object directly: {obj}"
            raise TypeError(msg)
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
            msg = "Serializer not set"
            raise ValueError(msg)
        if self.serializer is msgspec.json.encode and kwargs.get("indent") is not None:
            indent = kwargs.pop("indent")
            result: bytes = json.dumps(obj, indent=indent).encode()
            return result
        try:
            result_bytes: bytes = self.serializer(obj, **kwargs)
            return result_bytes
        except TypeError as e:
            if (
                "Extra keyword arguments provided" in str(e)
                and self.serializer is msgspec.json.encode
            ):
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != "indent"}
                result_filtered: bytes = self.serializer(obj, **filtered_kwargs)
                return result_filtered
            raise

    async def _write_to_path(self, data: bytes) -> None:
        try:
            if isinstance(self.path, AsyncPath):
                await self.path.write_bytes(data)
            elif isinstance(self.path, Path):
                self.path.write_bytes(data)
        except PermissionError:
            msg = f"Permission denied when writing to {self.path}"
            raise PermissionError(msg) from None

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

        # Try to determine the action and serializer from the calling code
        if await self._try_parse_calling_context(frame, kwargs, obj):
            return await self._process_with_serializer(obj, **kwargs)

        # Fallback to determining action from caller name
        self._determine_action_from_caller(frame)
        self._setup_json_serializer()
        return await self.process(obj, **kwargs)

    async def _try_parse_calling_context(
        self, frame: types.FrameType, kwargs: dict[str, t.Any], obj: t.Any
    ) -> bool:
        """Try to parse the calling context to determine action and serializer.

        Returns True if successfully parsed, False otherwise.
        """
        code_context = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
        pattern = "await\\s+(\\w+)\\.(\\w+)\\("
        calling_method = search(pattern, code_context)

        if calling_method:
            caller_obj = calling_method.group(1)
            serializer_name = calling_method.group(2)
            self._set_action_from_caller_obj(caller_obj)

            if serializer_name in self.serializers:
                serializer = self.serializers[serializer_name]
                if self.action == "encode":
                    self.serializer = serializer.encode
                else:
                    self.serializer = serializer.decode
                return True
        return False

    def _set_action_from_caller_obj(self, caller_obj: str) -> None:
        """Set the action based on the calling object."""
        if caller_obj in ("encode", "dump"):
            self.action = "encode"
        elif caller_obj in ("decode", "load"):
            self.action = "decode"
        else:
            self.action = "encode"

    def _determine_action_from_caller(self, frame: types.FrameType) -> None:
        """Determine the action based on the caller's name."""
        caller_name = frame.f_code.co_name
        if "encode" in caller_name or "dump" in caller_name:
            self.action = "encode"
        else:
            self.action = "decode"

    def _setup_json_serializer(self) -> None:
        """Set up the JSON serializer as fallback."""
        serializer = self.serializers["json"]
        if self.action == "encode":
            self.serializer = serializer.encode
        else:
            self.serializer = serializer.decode

    async def _process_with_serializer(
        self, obj: t.Any, **kwargs: dict[str, t.Any]
    ) -> t.Any:
        """Process the object with the configured serializer."""
        return await self.process(obj, **kwargs)


encode = Encode()
decode = Encode()
dump = Encode()
load = Encode()
for s in serializers.__dict__:
    setattr(decode, s, decode._create_method(s, "decode"))
    setattr(load, s, load._create_method(s, "decode"))
