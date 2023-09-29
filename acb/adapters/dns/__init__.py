import typing as t

from acb.config import Config
from acb.config import import_adapter
from acb.depends import depends
from pydantic import BaseModel

Dns, DnsSettings = import_adapter()


class DnsRecord(BaseModel):
    name: t.Optional[str] = None
    type: str = "TXT"
    ttl: int = 300
    rrdata: t.Optional[str | list[t.Any]] = None

    @depends.inject
    def __init__(self, config: Config = depends(), **data: t.Any) -> None:
        super().__init__(**data)
        self.name = f"mail.{config.app.domain}"
