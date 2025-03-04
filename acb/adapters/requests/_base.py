import typing as t

from acb.config import AdapterBase, Settings


class RequestsBaseSettings(Settings):
    cache_ttl: int = 3600


class RequestsBase(AdapterBase):
    async def get(self, url: str, timeout: int) -> t.Any: ...

    async def post(self, url: str, data: dict[str, t.Any], timeout: int) -> t.Any: ...

    async def put(self, url: str, data: dict[str, t.Any], timeout: int) -> t.Any: ...

    async def delete(self, url: str, timeout: int) -> t.Any: ...
