import typing as t
from pathlib import Path

from encode import load
from encode import dump
from hash import hash
from pydantic import BaseSettings


class AppSettings(BaseSettings):
    formatted: bool = False
    basedir = Path("..").parent
    deployed = True if basedir.name == "app" else False

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
        json_loads = load.json
        json_dumps = dump.json

    def __init__(self, **values: t.Any):
        super().__init__(**values)
        name = self.__class__.__name__.replace("Settings", "").lower()
        settings = self.basedir / "settings"
        for path in [
            p for p in settings.iterdir() if p.suffix == ".yml" and p.stem == name
        ]:
            yml_settings = path.read_text()
            values = load.yml(yml_settings)
            current_hash = hash.crc32c(yml_settings)
            new_settings = dump.yml(values)
            new_hash = hash.crc32c(new_settings)
            if not self.deployed and not self.formatted and current_hash != new_hash:
                print(f"Changes detected in {path} - formatting...")
                path.write_text(new_settings)
                self.formatted = True
            super().__init__(**values)


class AppConfig(BaseSettings):
    ...

    class Config:
        extra = "allow"


ac = AppConfig()
