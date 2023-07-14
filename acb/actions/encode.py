import linecache
import sys
import typing as t
from os import PathLike
from re import search
from types import FrameType
from warnings import warn

import dill as pickle
import msgspec
from aiopath import AsyncPath
from blake3 import blake3  # type: ignore
from itsdangerous import Serializer as SecureSerializer


class AcbEncoder:
    json: t.Callable[..., t.Any]
    yaml: t.Callable[..., t.Any]
    msgpack: t.Callable[..., t.Any]
    toml: t.Callable[..., t.Any]
    pickle: t.Callable[..., t.Any]

    serializers: dict = dict(
        json=msgspec.json,
        yaml=msgspec.yaml,
        msgpack=msgspec.msgpack,
        pickle=pickle,
        toml=msgspec.toml,
    )

    def __init__(self) -> None:
        pickle.encode = pickle.dumps
        pickle.decode = pickle.loads
        for s in self.serializers.keys():
            setattr(self, s, self.__call__)

    async def process(
        self,
        obj: bytes | str | AsyncPath,
        path: AsyncPath,
        action: str,
        serializer: t.Any,
        # sort_keys: bool,
        use_list: bool,
        **kwargs,
    ) -> int | bytes:
        if action in ("load", "decode"):
            if serializer is msgspec.msgpack:
                kwargs["use_list"] = use_list
            if isinstance(obj, AsyncPath):
                obj = await obj.read_text()
            return serializer.decode(obj, **kwargs)
        elif action in ("dump", "encode"):
            # if serializer is msgspec.yaml:
            #     kwargs["sort_keys"] = sort_keys
            data = serializer.encode(obj, **kwargs)
            if isinstance(path, AsyncPath):
                return await path.write_bytes(data)
            return data

    def get_vars(self, frame: FrameType):
        code_context = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
        calling_method = search("await\s(\w+)\.(\w+)\(", code_context)
        return calling_method.group(1), self.serializers[calling_method.group(2)]

    def get_serializer(self, serializer, secret_key, secure_salt):
        secure = secret_key and secure_salt
        return (
            SecureSerializer(
                secret_key,
                salt=secure_salt,
                serializer=serializer,
                signer_kwargs=dict(digest_method=blake3),
            )
            if secure
            else serializer
        )

    async def __call__(
        self,
        obj: str | PathLike | dict,
        path: t.Optional[AsyncPath] = None,
        # sort_keys: bool = True,
        use_list: bool = False,
        secret_key: t.Optional[str] = None,
        secure_salt: t.Optional[str] = None,
        **kwargs,
    ) -> dict | bytes:
        action, serializer = self.get_vars(sys._getframe(1))
        if (secret_key and not secure_salt) or (secure_salt and not secret_key):
            warn(
                f"{serializer} serializer won't sign objects unless both "
                f"secret_key and secure_salt are set"
            )
        serializer = self.get_serializer(serializer, secret_key, secure_salt)
        return await self.process(
            obj,
            path,
            action,
            serializer,
            use_list,
            # sort_keys,
            **kwargs,
        )


dump = load = encode = decode = AcbEncoder()
