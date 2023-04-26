import linecache
import pickle
import sys
import tomllib
from pathlib import Path
from re import search

import msgspec
import tomlkit
from addict import Dict as adict
from aiopath import AsyncPath
from itsdangerous import Serializer as SecureSerializer
from pathy import Path as PathyPath


class AcbEncoder:
    def __init__(self):
        self.serializers = adict(
            json=msgspec.json,
            yaml=msgspec.yaml,
            msgpack=msgspec.msgpack,
            pickle=pickle,
            toml=tomllib,
        )
        pickle.encode = pickle.dumps
        pickle.decode = pickle.loads
        tomllib.encode = tomlkit.dumps
        tomllib.dumps = tomlkit.dumps
        tomllib.decode = tomllib.loads
        for s in self.serializers.keys():
            setattr(self, s, self.__call__)

    async def process(
            self, obj, path, action, serializer, sort_keys, use_list, **kwargs
    ) -> adict | bytes:
        if action in ("load", "decode"):
            if serializer is msgspec.msgpack:
                kwargs.use_list = use_list
            if isinstance(obj, AsyncPath):
                obj = await obj.read_text()
            return adict(serializer.decode(obj, **kwargs))
        elif action in ("dump", "encode"):
            if serializer is msgspec.yaml:
                kwargs.sort_keys = sort_keys
            data = serializer.encode(obj, **kwargs)
            if isinstance(path, AsyncPath):
                return await path.write_text(data)
            elif isinstance(path, PathyPath):
                return path.write_text(data)
            return data

    def get_vars(self, frame):
        code_context = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
        calling_method = search("await\s(\w+)\.(\w+)\(", code_context)
        return calling_method.group(1), self.serializers[calling_method.group(2)]

    def get_serializer(self, serializer, secret_key, secure_salt):
        secure = secret_key and secure_salt
        return (
            SecureSerializer(secret_key, secure_salt, serializer=serializer)
            if secure
            else serializer
        )

    async def __call__(
            self,
            obj: str | Path | AsyncPath | Path | bytes | dict | adict = None,
            path: AsyncPath | Path | PathyPath | str | None = None,
            sort_keys: bool = True,
            use_list: bool = False,
            secret_key: str = None,
            secure_salt: str = None,
            **kwargs,
    ) -> adict | bytes:
        obj = obj if not isinstance(obj, Path | AsyncPath) else AsyncPath(obj)
        path = AsyncPath(path) if isinstance(path, Path | str) else path
        action, serializer = self.get_vars(sys._getframe(1))
        serializer = self.get_serializer(serializer, secret_key, secure_salt)
        return await self.process(
            obj, path, action, serializer, sort_keys, use_list, **kwargs
        )


dump = load = encode = decode = AcbEncoder()
