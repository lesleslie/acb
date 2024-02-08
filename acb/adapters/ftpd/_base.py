from acb.adapters import AdapterBase

from acb.config import Settings


class FtpdBaseSettings(Settings):
    port: int = 8021
    max_connections: int = 42


class FtpdBase(AdapterBase): ...
