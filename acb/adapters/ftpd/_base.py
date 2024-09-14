from acb.config import AdapterBase, Settings


class FtpdBaseSettings(Settings):
    port: int = 8021
    max_connections: int = 42


class FtpdBase(AdapterBase): ...
