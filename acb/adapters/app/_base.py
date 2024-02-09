from acb.adapters import AdapterBase
from acb.adapters import import_adapter
from acb.config import AppSettings as AppConfigSettings

Logger = import_adapter()


class AppBaseSettings(AppConfigSettings): ...


class AppBase(AdapterBase): ...
