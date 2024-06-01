from acb.adapters import AdapterBase, import_adapter
from acb.config import Settings

Logger = import_adapter()


class MonitoringBaseSettings(Settings): ...


class MonitoringBase(AdapterBase): ...
