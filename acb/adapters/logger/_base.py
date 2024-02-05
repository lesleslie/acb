from acb.config import Settings


class LoggerBaseSettings(Settings):
    verbose: bool = False
    deployed_level: str = "ERROR"


class LoggerBase: ...
