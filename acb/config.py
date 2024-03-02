import asyncio
import typing as t
from abc import ABC
from abc import abstractmethod
from contextvars import ContextVar
from functools import cached_property
from pathlib import Path
from secrets import token_bytes
from secrets import token_urlsafe

import nest_asyncio
from acb import tmp_path
from acb.actions.encode import dump
from acb.actions.encode import load
from acb.adapters import adapter_registry
from acb.adapters import import_adapter
from acb.adapters import register_adapters
from acb.adapters import settings_path
from acb.depends import depends
from aiopath import AsyncPath
from inflection import titleize
from inflection import underscore
from pydantic import BaseModel
from pydantic import SecretStr
from pydantic._internal._utils import deep_update
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict
from pydantic_settings.sources import SettingsError

nest_asyncio.apply()

register_adapters()

project: str = ""
app_name: str = ""
debug: dict[str, bool] = {}
_deployed: bool = True if Path.cwd().name == "app" else False
_secrets_path: AsyncPath = tmp_path / "secrets"
_app_secrets: ContextVar[set[str]] = ContextVar("_app_secrets", default=set())


async def init_app() -> None:
    for path in (
        tmp_path,
        _secrets_path,
        AsyncPath(settings_path),
    ):
        await path.mkdir(exist_ok=True)


asyncio.run(init_app())


def gen_password(size: int = 10) -> str:
    return token_urlsafe(size)


class PydanticBaseSettingsSource(ABC):
    adapter_name: str = "app"

    def __init__(
        self,
        settings_cls: type["Settings"],
        secrets_dir: AsyncPath = _secrets_path,
    ) -> None:
        self.settings_cls = settings_cls
        self.adapter_name = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        self.secrets_dir = secrets_dir
        self.config = settings_cls.model_config

    def get_model_secrets(self) -> dict[str, FieldInfo]:
        return {
            "_".join((self.adapter_name, n)): v
            for n, v in self.settings_cls.model_fields.items()
            if v.annotation is SecretStr
        }

    @abstractmethod
    async def __call__(self) -> dict[str, t.Any]:
        raise NotImplementedError


class InitSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self, settings_cls: type["Settings"], init_kwargs: dict[str, t.Any]
    ) -> None:
        self.init_kwargs = init_kwargs
        super().__init__(settings_cls)

    async def __call__(self) -> dict[str, t.Any]:
        return self.init_kwargs

    def __repr__(self) -> str:
        return f"InitSettingsSource(init_kwargs={self.init_kwargs!r})"


class FileSecretSource(PydanticBaseSettingsSource):
    async def get_field_value(self, field_name: str) -> SecretStr | None:
        path = self.secrets_path / field_name
        if await path.is_file():
            return SecretStr((await path.read_text()).strip())

    async def __call__(self) -> dict[str, t.Any]:
        data = {}
        self.secrets_path = await AsyncPath(self.secrets_dir).expanduser()
        if not await self.secrets_path.exists():
            await self.secrets_path.mkdir(parents=True, exist_ok=True)
        model_secrets = self.get_model_secrets()
        for field_key in model_secrets:
            field_key = field_key.removeprefix(f"{app_name}_")
            if field_key in _app_secrets.get():
                continue
            try:
                field_value = await self.get_field_value(field_key)
            except Exception as e:
                raise SettingsError(
                    f'error getting value for field "{field_key}" from '
                    f'source "{self.__class__.__name__}"'
                ) from e
            if field_value is not None:
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                data[field_name] = field_value
                _app_secrets.get().add(field_key)
        return data

    def __repr__(self) -> str:
        return f"FileSecretSource(_secrets_dir={self.secrets_dir!r})"


class ManagerSecretSource(PydanticBaseSettingsSource):
    @cached_property
    def manager(self):
        manager_class = import_adapter("secret")
        manager = depends.get(manager_class)
        return manager

    async def load_secrets(self) -> t.Any:
        data = {}
        adapter_secrets = self.get_model_secrets()
        missing_secrets = {
            n: v for n, v in adapter_secrets.items() if n not in _app_secrets.get()
        }
        if missing_secrets and self.manager:
            manager_secrets = await self.manager.list(self.adapter_name)
            for field_key, field_value in missing_secrets.items():
                stored_field_key = "_".join((app_name, field_key))
                secret_path = self.secrets_dir / field_key
                if not await secret_path.exists():
                    if field_key not in manager_secrets:
                        await self.manager.create(
                            stored_field_key, field_value.default.get_secret_value()
                        )
                secret = await self.manager.get(stored_field_key)
                await secret_path.write_text(secret)
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                data[field_name] = SecretStr(secret)
                _app_secrets.get().add(field_key)
        return data

    async def __call__(self) -> t.Any:
        data = await self.load_secrets()
        return data


class YamlSettingsSource(PydanticBaseSettingsSource):
    async def load_yml_settings(self) -> t.Any:
        global project, app_name, debug
        if self.adapter_name == "secret":
            return {}
        yml_path = AsyncPath(settings_path / f"{self.adapter_name}.yml")
        if not await yml_path.exists() and not _deployed:
            dump_settings = {
                name: info.default
                for name, info in self.settings_cls.model_fields.items()
                if (info.annotation is not SecretStr)
                and ("Optional" not in (str(info.annotation)))
            }
            await dump.yaml(dump_settings, yml_path)
        yml_settings = await load.yaml(yml_path)
        if self.adapter_name == "debug":
            for adapter in [
                a
                for a in adapter_registry.get()
                if a.category not in yml_settings.keys()
            ]:
                yml_settings[adapter.category] = False
            debug = yml_settings
        if not _deployed:
            await dump.yaml(yml_settings, yml_path, sort_keys=True)
        if self.adapter_name == "app":
            project = yml_settings["project"]
            app_name = yml_settings["name"]
        return yml_settings

    async def __call__(self) -> dict[str, t.Any]:
        data = {}
        if Path.cwd().name != "acb":
            for field_name, field in (await self.load_yml_settings()).items():
                if field is not None:
                    data[field_name] = field
            return data
        return data


class Settings(BaseModel):
    loggers: t.Optional[list[str]] = []

    model_config: t.ClassVar[SettingsConfigDict] = SettingsConfigDict(  # type: ignore
        extra="allow",
        arbitrary_types_allowed=True,
        validate_default=True,
        secrets_dir=_secrets_path,
        protected_namespaces=("model_", "settings_"),
    )

    def __init__(
        __pydantic_self__,  # type: ignore
        _secrets_dir: AsyncPath = _secrets_path,
        **values: t.Any,
    ) -> None:
        build_settings = __pydantic_self__._settings_build_values(
            values,
            _secrets_dir=_secrets_dir,
        )
        build_settings = asyncio.run(build_settings)
        super().__init__(**build_settings)

    def __getattr__(self, item: str) -> t.Any:
        return super().__getattr__(item)  # type: ignore

    async def _settings_build_values(
        self,
        init_kwargs: dict[str, t.Any],
        _secrets_dir: AsyncPath = _secrets_path,
    ) -> dict[str, t.Any]:
        secrets_dir = _secrets_dir or self.model_config.get("secrets_dir")
        init_settings = InitSettingsSource(self.__class__, init_kwargs=init_kwargs)
        file_secret_settings = FileSecretSource(
            self.__class__,
            secrets_dir=secrets_dir,
        )
        manager_secret_settings = ManagerSecretSource(
            self.__class__,
            secrets_dir=secrets_dir,
        )
        yaml_settings = YamlSettingsSource(self.__class__)

        sources = self.settings_customize_sources(
            self.__class__,
            init_settings=init_settings,
            yaml_settings=yaml_settings,
            file_secret_settings=file_secret_settings,
            manager_secret_settings=manager_secret_settings,
        )
        return deep_update(*reversed([await source() for source in sources]))

    @classmethod
    def settings_customize_sources(
        cls,
        settings_cls: t.Type["Settings"],
        init_settings: PydanticBaseSettingsSource,
        yaml_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
        manager_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            yaml_settings,
            file_secret_settings,
            manager_secret_settings,
        )


class DebugSettings(Settings):
    production: bool = False
    secrets: bool = False
    logger: bool = False


class AppSettings(Settings):
    project: str = "my-project"
    name: str = "myapp"
    title: str = "Asynchronous Component Base"
    domain: str = ""
    timezone: str = "US/Pacific"
    secret_key: SecretStr = SecretStr(token_urlsafe(32))
    secure_salt: SecretStr = SecretStr(str(token_bytes(32)))

    def model_post_init(self, __context: t.Any) -> None:
        self.title = self.title or titleize(self.name)


class Config(BaseModel, extra="allow"):
    deployed: bool = _deployed
    debug: t.Optional[Settings] = None
    app: t.Optional[Settings] = None

    def __getattr__(self, item: str) -> t.Any:
        return super().__getattr__(item)  # type: ignore

    def init(self) -> None:
        self.debug = DebugSettings()
        self.app = AppSettings()


depends.set(Config)
depends.get(Config).init()
