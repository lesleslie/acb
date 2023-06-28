from acb.config import Settings
from acb.config import load_adapter


class NosqlBaseSettings(Settings):
    ...


nosql = load_adapter("nosql")
