from acb import load_adapter
from ._base import DnsRecord

__all__: list[str] = ["Dns", "DnsRecord"]

Dns = load_adapter()
