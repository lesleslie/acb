from acb.config import ac
from acb.config import load_adapter

for adapter in ac.enabled_adapters:
    globals()[adapter] = load_adapter(adapter)
