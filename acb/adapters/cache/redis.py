import typing as t
from contextlib import contextmanager
from os import getpid
from sys import getsizeof

import anyio
from acb import AppSettings
from aiopath import AsyncPath
from httpx import Request
from httpx import Response
from pydantic import BaseSettings
# from httpx_cache.serializer.base import BaseSerializer
# from httpx_cache.serializer.common import MsgPackSerializer
# from httpx_cache.utils import get_cache_key
from redis.asyncio import Redis as AsyncRedis


class CacheSettings(AppSettings):
    type = "redis"
    default_timeout = 86400
    redis_password: str = ac.secrets.redis_password if ac.deployed else None
    template_timeout = 300 if ac.deployed else 1
    media_timeout = 15_768_000
    media_control = f"max-age={str(media_timeout)} public"
    serializer_kwargs = dict(
        secret_key=ac.secrets.app_secret_key, salt=ac.secrets.app_secure_salt
    )

    kwargs = dict(
        host=ac.secrets.redis_host if ac.deployed else ac.app.localhost,
        # password=ac.secrets.redis_password if deployed else None,
        port=6379,
        db=0,
        health_check_interval=15,
        # expire_after=cache.default_timeout,
    )

    def __init__(self, **data: t.Any):
        super().__init__(**data)

        class CacheConfig(BaseSettings):
            session = {**self.kwargs}
            starlette = {**self.kwargs, **dict(db=1)}
            theme = {**self.kwargs, **dict(db=2)}
            jinja = {**self.kwargs, **dict(db=3)}
            resize = {**self.kwargs, **dict(db=4)}
            httpx = {**self.kwargs, **dict(db=5)}
            settings = {**self.kwargs, **dict(db=6)}

        self.configs = CacheConfig()


class SetKeyAioRedis(AsyncRedis):
    def __init__(self, prefix: t.Optional[str] = None, **configs):
        super().__init__(**configs)
        self.prefix = prefix or ac.app.name

    @contextmanager
    async def transaction(self, unique_key: str, ttl=600) -> t.AsyncGenerator:
        tkey = "_transaction_".join([self.prefix, unique_key])

        if self.set(tkey, str(getpid()), nx=True):
            await self.expire(tkey, ttl)
        else:
            yield False
        try:
            yield True
        finally:
            await self.delete(tkey)


class HttpxAioRedis(AsyncRedis):
    async_lock = anyio.Lock()

    def __init__(
        self, serializer: t.Optional[BaseSerializer] = None, **configs
    ) -> None:
        super().__init__(**configs)
        self.serializer = serializer or MsgPackSerializer()

        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Excpected serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )

    async def _get(self, request: Request) -> t.Optional[Response]:
        key = get_cache_key(request)
        cached_data = await self.get(key)
        ic(key)
        ic(getsizeof(cached_data))

        if cached_data is not None:
            decompressed_data = self.serializer.loads(
                cached=cached_data, request=request
            )
            ic(getsizeof(decompressed_data))
            return decompressed_data
        return None

    async def aget(self, request: Request) -> t.Optional[Response]:
        return await self._get(request)

    async def aset(
        self, *, request: Request, response: Response, content: t.Optional[bytes] = None
    ) -> None:
        to_cache = self.serializer.dumps(response=response, content=content)
        key = get_cache_key(request)
        ic(key)
        ic(getsizeof(to_cache))
        async with self.async_lock:
            await self.set(key, to_cache)

    async def adelete(self, request: Request) -> None:
        key = get_cache_key(request)
        async with self.async_lock:
            await self.delete(key)

    async def aclose(self):
        await self.close()


class AppAioRedis(AioRedis):
    def __init__(self, namespace: t.Optional[str] = None, **configs):
        super().__init__(**configs)
        self.prefix = prefix or ac.app.name

    async def clear(self, namespace: str = None, key: str = None):
        namespace = namespace or self.prefix
        if namespace:
            async for k in self.scan_iter(f"{namespace}:*"):
                await self.delete(k)
            return True
        elif key:
            return await self.delete(key) if key else None

    async def all(self, namespace: str = None) -> list:
        namespace = namespace or self.prefix
        if namespace:
            keys = []
            async for key in self.scan_iter(f"{namespace}:*"):
                keys.append(key.decode())
            return keys


import typing as tp
from datetime import timedelta

import httpx
from aiorwlock import RWLock as AsyncRWLock
from fasteners import ReaderWriterLock as RWLock
from redis.asyncio import Redis as AsyncRedis

from httpx_cache.serializer.base import BaseSerializer
from httpx_cache.serializer.common import MsgPackSerializer
from httpx_cache.utils import get_cache_key

__all__ = ["RedisCache"]


class RedisCache(AsyncRedis):
    """Redis cache that stores cached responses in Redis.
    Uses a lock/async_lock to make sure each get/set/delete operation is safe.
    You can either provide an instance of 'Redis'/'AsyncRedis' or a redis url to
    have RedisCache create the connection for you.
    Args:
        serializer: Optional serializer for the data to cache, defaults to:
            httpx_cache.MsgPackSerializer
        namespace: Optional namespace for the cache keys, defaults to "httpx_cache"
        redis_url: Optional redis url, defaults to empty string
        redis: Optional redis instance, defaults to None
        aredis: Optional async redis instance, defaults to None
        default_ttl: Optional default ttl for cached responses, defaults to None
    """

    lock = RWLock()

    def __init__(
        self,
        serializer: t.Optional[BaseSerializer] = None,
        namespace: str = "acb_cache",
        default_ttl: t.Optional[timedelta] = None,
        **redis_configs,
    ) -> None:
        super().__init__(**redis_configs)
        self.namespace = namespace
        self.serializer = serializer or MsgPackSerializer()
        self.default_ttl = default_ttl
        if not isinstance(self.serializer, BaseSerializer):
            raise TypeError(
                "Expected serializer of type 'httpx_cache.BaseSerializer', "
                f"got {type(self.serializer)}"
            )
        self._async_lock: t.Optional[AsyncRWLock] = None

    @property
    def async_lock(self) -> AsyncRWLock:
        if self._async_lock is None:
            self._async_lock = AsyncRWLock()
        return self._async_lock

    def _get_namespaced_cache_key(self, request: httpx.Request) -> str:
        key = get_cache_key(request)
        if self.namespace:
            key = f"{self.namespace}:{key}"
        return key

    async def clear(self, namespace: str = None, key: str = None):
        namespace = namespace or self.prefix
        if namespace:
            async for k in self.scan_iter(f"{namespace}:*"):
                await self.delete(k)
            return True
        elif key:
            return await self.delete(key) if key else None

    async def all(self, namespace: str = None) -> list:
        namespace = namespace or self.prefix
        if namespace:
            keys = []
            async for key in self.scan_iter(f"{namespace}:*"):
                keys.append(key.decode())
            return keys

    async def get_with_ttl(self, key: str) -> t.Tuple[int, str]:
        async with self.redis.pipeline(transaction=not self.is_cluster) as pipe:
            return await pipe.ttl(key).get(key).execute()

    async def get_with_ttl(self, key: str) -> t.Tuple[int, str]:
        async with self.pipeline(transaction=True) as pipe:
            ttl, compressed_data = await pipe.ttl(key).get(key).execute()
        # ic(key)
        decompressed_data = None
        if compressed_data:
            decompressed_data = decompress.brotli(compressed_data)
            if decompressed_data:
                ic(ttl)
                ic(getsizeof(compressed_data))
                ic(getsizeof(decompressed_data))
        return ttl, decompressed_data

    async def get(self, name: AsyncPath | str, namespace: str = None):
        namespace = namespace or self.namespace
        key = self.key_name(name, namespace)
        compressed_data = await super().get(key)
        # ic(key)
        logger.debug(f"Fetching - {name}")
        try:
            decompressed_data = decompress.brotli(compressed_data)
            # ic(getsizeof(compressed_data))
            # ic(getsizeof(decompressed_data))
            logger.debug(f"Fetched - {name}")
            return (
                Markup(decompressed_data)
                if self.__class__.__name__ == "theme"
                else decompressed_data
            )
        except TypeError:
            return None  # for jinja loaders

    async def get(self, key: str) -> t.Optional[str]:
        return await self.redis.get(key)

    async def aget(self, request: httpx.Request) -> tp.Optional[httpx.Response]:
        key = self._get_namespaced_cache_key(request)
        async with self.async_lock.reader:
            cached_data = await self.aredis.get(key)
        if cached_data is not None:
            return self.serializer.loads(cached=cached_data, request=request)
        return None

    async def aset(
        self,
        *,
        request: httpx.Request,
        response: httpx.Response,
        content: tp.Optional[bytes] = None,
    ) -> None:
        to_cache = self.serializer.dumps(response=response, content=content)
        key = self._get_namespaced_cache_key(request)
        async with self.async_lock.writer:
            if self.default_ttl:
                await self.aredis.setex(key, self.default_ttl, to_cache)
            else:
                await self.aredis.set(key, to_cache)

    async def set(self, key: str, value: str, expire: t.Optional[int] = None) -> None:
        return await self.redis.set(key, value, ex=expire)

    async def set(
        self,
        name: AsyncPath | str,
        uncompressed_data,
        expire: int = None,
        prefix: str = None,
        **kwargs,
    ):
        prefix = prefix if prefix else self.prefix
        key = self.key_name(name, prefix)
        logger.debug(f"Caching... {name}")
        # ic(key)
        compressed_data = compress.brotli(uncompressed_data)
        await super().set(key, compressed_data, ex=expire)
        # ic(getsizeof(uncompressed_data))
        # ic(getsizeof(compressed_data))
        logger.debug(f"Cached - {name}")
        return uncompressed_data

    async def get_keys(self) -> list:
        return await self.all()

    async def adelete(self, request: httpx.Request) -> None:
        key = self._get_namespaced_cache_key(request)
        async with self.async_lock.writer:
            await self.delete(key)

    async def aclose(self) -> None:
        await self.close()

    async def set_exists(self, unique_key):
        return await self.sismember(self.namespace, unique_key)

    async def set_add(self, unique_key):
        return bool(await self.sadd(self.namespace, unique_key))

    async def set_remove(self, unique_key):
        return bool(await self.srem(self.namespace, unique_key))

    async def set_clear(self):
        return bool(await self.delete(self.namespace))

    async def set_all(self):
        return [v.decode() for v in await self.smembers(self.namespace)]
