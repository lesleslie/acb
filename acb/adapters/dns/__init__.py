from acb.config import ac
from acb.config import AppSettings
from importlib import import_module
from pydantic import BaseModel


class DnsRecord(BaseModel):
    name: str = ac.app.mail_domain
    type: str = "TXT"
    ttl: int = 300
    rrdata: str | list = None



class BaseDnsSettings(AppSettings):
    ...


dns = import_module(ac.adapters.dns).dns
