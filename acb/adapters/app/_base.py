from acb.config import AdapterBase, import_adapter
from acb.config import AppSettings as AppConfigSettings

Logger = import_adapter()


class AppBaseSettings(AppConfigSettings): ...


class AppBase(AdapterBase): ...
