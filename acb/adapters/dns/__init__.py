from acb.config import import_adapter
from ._base import DnsRecord

__all__: list[str] = ["Dns", "DnsSettings", "DnsRecord"]

Dns, DnsSettings = import_adapter()
