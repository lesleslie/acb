import asyncio
import os
import typing as t
from contextvars import ContextVar
from enum import Enum
from functools import cached_property
from pathlib import Path
from secrets import token_bytes, token_urlsafe
from string import punctuation

import nest_asyncio
import rich.repr
from anyio import Path as AsyncPath
from inflection import titleize, underscore
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic._internal._utils import deep_update
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict
from pydantic_settings.sources import SettingsError

from . import register_pkg
from .actions.encode import dump, load
from .adapters import (
    _deployed,
    _testing,
    adapter_registry,
    get_adapter,
    import_adapter,
    root_path,
    secrets_path,
    settings_path,
    tmp_path,
)
from .depends import depends

nest_asyncio.apply()

register_pkg()

_app_secrets: ContextVar[set[str]] = ContextVar("_app_secrets", default=set())


async def get_version() -> str:
    pyproject_toml = root_path.parent / "pyproject.toml"
    version_file = root_path / "_version"
    if await pyproject_toml.exists():
        _version = (await load.toml(pyproject_toml)).get("project").get("version")
        await version_file.write_text(_version)
        return _version
    elif await version_file.exists():
        return await version_file.read_text()
    return "0.0.1"


def get_version_default() -> str:
    return asyncio.run(get_version())


project: str = ""
app_name: str = ""
debug: dict[str, bool] = {}


class Platform(str, Enum):
    aws = "aws"
    gcp = "gcp"
    azure = "azure"


async def init_app() -> None:
    init_paths = [
        tmp_path,
        secrets_path,
    ]
    init_paths = (
        init_paths
        if _deployed or _testing or root_path.stem == "acb"
        else (init_paths + [AsyncPath(settings_path)])
    )
    for path in init_paths:
        await path.mkdir(exist_ok=True)


asyncio.run(init_app())


def gen_password(size: int = 10) -> str:
    return token_urlsafe(size)


class PydanticSettingsProtocol(t.Protocol):
    adapter_name: str
    secrets_path: AsyncPath
    settings_cls: type["Settings"]
    model_config: SettingsConfigDict

    def __init__(
        self,
        settings_cls: type["Settings"],
        secrets_path: AsyncPath = ...,
    ) -> None: ...

    def get_model_secrets(self) -> dict[str, FieldInfo]: ...

    async def __call__(self) -> dict[str, t.Any]: ...

    def __repr__(self) -> str: ...


class PydanticSettingsSource:
    adapter_name: str = "app"
    settings_cls: type["Settings"]
    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
    )

    def __init__(
        self,
        settings_cls: type["Settings"],
        secrets_path: t.Optional[AsyncPath] = None,
    ) -> None:
        from acb.adapters import secrets_path as sp

        self.settings_cls = settings_cls
        self.adapter_name = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        self.secrets_path = secrets_path if secrets_path is not None else sp
        self.config = settings_cls.model_config

    def get_model_secrets(self) -> dict[str, FieldInfo]:
        return {
            "_".join((self.adapter_name, n)): v
            for n, v in self.settings_cls.model_fields.items()
            if v.annotation is SecretStr
        }

    async def __call__(self) -> dict[str, t.Any]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(secrets_path={self.secrets_path!r})"


class InitSettingsSource(PydanticSettingsSource):
    def __init__(
        self, settings_cls: type["Settings"], init_kwargs: dict[str, t.Any]
    ) -> None:
        self.init_kwargs = init_kwargs
        super().__init__(settings_cls=settings_cls)

    async def __call__(self) -> dict[str, t.Any]:
        return self.init_kwargs


class EnvSettingsSource(PydanticSettingsSource):
    async def __call__(self) -> dict[str, t.Any]:
        env_vars = {}
        for key, val in os.environ.items():
            if key.startswith(f"{self.adapter_name.upper()}_"):
                field_key = key.lower().removeprefix(f"{self.adapter_name}_")
                if field_key.endswith("__list"):
                    env_vars[field_key.removesuffix("__list")] = val.split(",")
                else:
                    env_vars[field_key] = val
        return env_vars


class FileSecretSource(PydanticSettingsSource):
    async def get_field_value(self, field_name: str) -> SecretStr | None:
        path = self.secrets_path / field_name
        if await path.is_file():
            return SecretStr((await path.read_text()).strip())

    async def __call__(self) -> dict[str, t.Any]:
        data = {}

        if _testing:
            model_secrets = self.get_model_secrets()
            for field_key, field_info in model_secrets.items():
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                if hasattr(field_info, "default") and field_info.default is not None:
                    data[field_name] = field_info.default
                else:
                    data[field_name] = SecretStr(f"test_secret_for_{field_name}")
            return data

        self.secrets_path = await AsyncPath(self.secrets_path).expanduser()
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
                    f"Error getting value for field '{field_key}' from "
                    f"source '{self.__class__.__name__}: {e}'"
                )
            if field_value is not None:
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                data[field_name] = field_value
                _app_secrets.get().add(field_key)

        return data


class ManagerSecretSource(PydanticSettingsSource):
    @cached_property
    def secret_manager(self):
        secret = depends.get()
        return secret

    async def load_secrets(self) -> t.Any:
        data = {}

        if _testing:
            adapter_secrets = self.get_model_secrets()
            for field_key, field_info in adapter_secrets.items():
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                if hasattr(field_info, "default") and field_info.default is not None:
                    data[field_name] = field_info.default
                else:
                    data[field_name] = SecretStr(f"test_secret_for_{field_name}")
            return data

        adapter_secrets = self.get_model_secrets()
        missing_secrets = {
            n: v for n, v in adapter_secrets.items() if n not in _app_secrets.get()
        }
        if missing_secrets and self.secret_manager:
            manager_secrets = await self.secret_manager.list(self.adapter_name)
            for field_key, field_value in missing_secrets.items():
                stored_field_key = "_".join((app_name, field_key))
                secret_path = self.secrets_path / field_key
                if not await secret_path.exists():
                    if field_key not in manager_secrets:
                        await self.secret_manager.create(
                            stored_field_key, field_value.default.get_secret_value()
                        )
                secret = await self.secret_manager.get(stored_field_key)
                await secret_path.write_text(secret)
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                data[field_name] = SecretStr(secret)
                _app_secrets.get().add(field_key)
        return data

    async def __call__(self) -> t.Any:
        data = await self.load_secrets()
        return data


class YamlSettingsSource(PydanticSettingsSource):
    async def load_yml_settings(self) -> t.Any:
        global project, app_name, debug
        if self.adapter_name == "secret":
            return {}

        yml_path = AsyncPath(settings_path / f"{self.adapter_name}.yml")

        if _testing:
            default_settings = {
                name: info.default
                for name, info in self.settings_cls.model_fields.items()
                if (info.annotation is not SecretStr)
            }
            if self.adapter_name == "debug":
                debug = default_settings
            if self.adapter_name == "app":
                project = "test_project"
                app_name = "test_app"
            return default_settings

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
            project = yml_settings.get("project")
            app_name = yml_settings["name"]

        return yml_settings or {}

    async def __call__(self) -> dict[str, t.Any]:
        data = {}
        if _testing or Path.cwd().name != "acb":
            for field_name, field in (await self.load_yml_settings()).items():
                if field is not None:
                    data[field_name] = field
            return data
        return data


class SettingsProtocol(t.Protocol):
    model_config: t.ClassVar[SettingsConfigDict]

    def __init__(
        __pydantic_self__,  # type: ignore
        _secrets_path: AsyncPath = ...,
        **values: t.Any,
    ) -> None: ...

    _settings_build_values: t.Callable[..., t.Awaitable[t.Dict[str, t.Any]]]

    settings_customize_sources: t.Callable[..., tuple[PydanticSettingsProtocol, ...]]


@rich.repr.auto
class Settings(BaseModel):
    model_config: t.ClassVar[SettingsConfigDict] = SettingsConfigDict(  # type: ignore
        extra="allow",
        arbitrary_types_allowed=True,
        validate_default=True,
        secrets_dir=Path(secrets_path),
        protected_namespaces=("model_", "settings_"),
    )

    def __init__(
        __pydantic_self__,  # type: ignore
        _secrets_path: AsyncPath = secrets_path,
        **values: t.Any,
    ) -> None:
        build_settings = __pydantic_self__._settings_build_values(
            values,
            _secrets_path=_secrets_path,
        )
        build_settings = asyncio.run(build_settings)
        if not isinstance(build_settings, dict):  # type: ignore
            build_settings = {}
        super().__init__(**build_settings)

    def __getattr__(self, item: str) -> t.Any:
        return super().__getattr__(item)  # type: ignore

    async def _settings_build_values(
        self,
        init_kwargs: dict[str, t.Any],
        _secrets_path: AsyncPath = secrets_path,
    ) -> dict[str, t.Any]:
        _secrets_path = secrets_path or self.model_config.get("secrets_dir")
        init_settings: InitSettingsSource = InitSettingsSource(
            self.__class__, init_kwargs=init_kwargs
        )
        file_secret_settings: FileSecretSource = FileSecretSource(
            self.__class__, secrets_path=secrets_path
        )
        manager_secret_settings: ManagerSecretSource = ManagerSecretSource(
            self.__class__, secrets_path=secrets_path
        )
        yaml_settings: YamlSettingsSource = YamlSettingsSource(self.__class__)

        sources = self.settings_customize_sources(
            settings_cls=self.__class__,
            init_settings=t.cast(PydanticSettingsProtocol, init_settings),
            yaml_settings=t.cast(PydanticSettingsProtocol, yaml_settings),
            file_secret_settings=t.cast(PydanticSettingsProtocol, file_secret_settings),
            manager_secret_settings=t.cast(
                PydanticSettingsProtocol, manager_secret_settings
            ),
        )
        return deep_update(*reversed([await source() for source in sources]))

    @classmethod
    def settings_customize_sources(
        cls,  # noqa: F841
        settings_cls: t.Type["Settings"],
        init_settings: PydanticSettingsProtocol,
        yaml_settings: PydanticSettingsProtocol,
        file_secret_settings: PydanticSettingsProtocol,
        manager_secret_settings: PydanticSettingsProtocol,
    ) -> tuple[PydanticSettingsProtocol, ...]:
        sources = [init_settings, yaml_settings, file_secret_settings]
        if get_adapter("secret") is not None:
            sources.append(manager_secret_settings)
        return tuple(sources)


class DebugSettings(Settings):
    production: bool = False
    secrets: bool = False
    logger: bool = False


class AppSettings(Settings):
    name: str = root_path.stem
    secret_key: SecretStr = SecretStr(token_urlsafe(32))
    secure_salt: SecretStr = SecretStr(str(token_bytes(32)))
    title: str | None = None
    domain: t.Optional[str] = None
    platform: t.Optional[Platform] = None
    project: t.Optional[str] = None
    region: t.Optional[str] = None
    timezone: t.Optional[str] = "US/Pacific"
    version: t.Optional[str] = Field(default_factory=get_version_default)

    def __init__(self, **values: t.Any) -> None:  # noqa: F841
        super().__init__(**values)
        self.title = self.title or titleize(self.name)

    @field_validator("name")
    @classmethod
    def cloud_compliant_app_name(cls, v: str) -> str:  # noqa: F841
        not_ok = [" ", "_", "."]
        _name = v
        for p in not_ok:
            _name = _name.replace(p, "-")
        for p in punctuation.replace("-", ""):
            _name = _name.replace(p, "")
        app_name = _name.strip("-").lower()
        if len(app_name) < 3:
            raise SystemExit("App name to short")
        elif len(app_name) > 63:
            raise SystemExit("App name to long")
        return app_name


@t.runtime_checkable
class ConfigProtocol(t.Protocol):
    deployed: bool
    root_path: AsyncPath
    secrets_path: AsyncPath
    settings_path: AsyncPath
    tmp_path: AsyncPath
    debug: DebugSettings | None
    app: AppSettings | None

    async def init(self) -> None: ...


@rich.repr.auto
class Config(BaseModel, arbitrary_types_allowed=True, extra="allow"):
    deployed: bool = _deployed
    root_path: AsyncPath = root_path
    secrets_path: AsyncPath = secrets_path
    settings_path: AsyncPath = settings_path
    tmp_path: AsyncPath = tmp_path
    debug: DebugSettings | None = None
    app: AppSettings | None = None

    def __getattr__(self, item: str) -> t.Any:
        return super().__getattr__(item)  # type: ignore

    def init(self) -> None:
        self.debug = DebugSettings()
        self.app = AppSettings()


depends.set(Config)
depends.get(Config).init()

Logger = import_adapter()


@rich.repr.auto
class AdapterBase:
    config: Config = depends()
    logger: Logger = depends()

    async def init(self) -> None: ...
