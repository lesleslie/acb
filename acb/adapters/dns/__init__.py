from acb.config import ac
from pydantic import BaseModel
from acb.config import Settings
from acb.config import load_adapter


class DnsRecord(BaseModel):
    name: str = ac.app.mail_domain
    type: str = "TXT"
    ttl: int = 300
    rrdata: str | list = None


class DnsBaseSettings(Settings):
    ...


dns = load_adapter("dns")
