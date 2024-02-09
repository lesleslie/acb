from acb.adapters import import_adapter
from acb.adapters import AdapterBase
from acb.config import Settings

Logger = import_adapter()


class MonitoringBaseSettings(Settings): ...


class MonitoringBase(AdapterBase): ...
