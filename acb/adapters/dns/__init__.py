from acb.config import import_adapter
from pydantic import BaseModel
import typing as t
from acb.depends import depends
from acb.config import Config

Dns, DnsSettings = import_adapter()


class DnsRecord(BaseModel):
    name: t.Optional[str] = None
    type: str = "TXT"
    ttl: int = 300
    rrdata: t.Optional[str | list[t.Any]] = None

    @depends.inject
    def model_post_init(self, __context: t.Any, config: Config = depends()) -> None:
        super().model_post_init(__context)
        self.name = f"mail.{config.app.domain}"
