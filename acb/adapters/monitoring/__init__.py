from acb.config import load_adapter
from acb.config import Settings


class MonitoringBaseSettings(Settings):
    ...


monitoring = load_adapter("monitoring")
