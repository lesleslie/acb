from acb import load_adapter
from ._base import DnsRecord

__all__: list[str] = ["Dns", "DnsSettings", "DnsRecord"]

Dns, DnsSettings = load_adapter()
