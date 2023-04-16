import inspect
import pickle
from pathlib import Path
from re import search
from typing import Any

import msgspec
from addict import Dict as adict
from aiopath import AsyncPath
from itsdangerous import Serializer as SecureSerializer


class AcbEncoder:
    async def process(self):
        if self.action == "load":
            data = self.obj
            if self.path:
                data = await self.path.read_bytes()
            return adict(self.serializer.decode(data, **self.kwargs))
        else:
            data = self.serializer.encode(self.obj, **self.kwargs)
            if self.path:
                return await self.path.write_text(data)
            return data

    def __init__(self):
        self.action = inspect.stack()[1][4][0].split(" = ")[0]
        self.serializers = adict(
            json=msgspec.json, yaml=msgspec.yaml, msgpack=msgspec.msgpack, pickle=pickle
        )
        pickle.encode = pickle.dumps
        pickle.decode = pickle.loads
        for s in self.serializers.keys():
            setattr(self, s, self.__call__)
            setattr(self, f"secure_{s}", self.__call__)

    async def __call__(
        self,
        obj: Any = None,
        path: Path | AsyncPath | str = None,
        sort_keys: bool = False,
        use_list: bool = False,
        secret_key: str = None,
        secure_salt: str = None,
        **kwargs,
    ):
        self.obj = obj
        self.path = None if not path else AsyncPath(path)
        self.secret_key = secret_key
        self.secure_salt = secure_salt
        serializer = search("await\s\w+\.(\w+)\(", inspect.stack()[1][4][0]).group(1)
        self.secure = self.secret_key and self.secure_salt
        serializer = self.serializers[serializer.removeprefix("secure_")]
        self.kwargs = adict(kwargs)
        if self.action == "load" and serializer is msgspec.msgpack:
            self.kwargs.use_list = use_list
        elif self.action == "dump" and serializer is msgspec.yaml:
            self.kwargs.sort_keys = sort_keys
        self.serializer = (
            SecureSerializer(self.secret_key, self.secure_salt, serializer=serializer)
            if self.secure
            else serializer
        )
        return await self.process()


dump = load = AcbEncoder()
