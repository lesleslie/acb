import asyncio
import secrets
import typing as t
from abc import ABC
from abc import abstractmethod
from contextvars import ContextVar
from importlib import import_module
from inspect import currentframe
from pathlib import Path
from secrets import token_bytes
from secrets import token_urlsafe

import nest_asyncio
from acb.actions.encode import dump
from acb.actions.encode import load
from acb.depends import depends
from aiopath import AsyncPath
from async_lru import alru_cache
from inflection import camelize
from inflection import titleize
from inflection import underscore
from pydantic import BaseModel
from pydantic import SecretStr
from pydantic._internal._utils import deep_update
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from pydantic_settings.sources import SettingsError

nest_asyncio.apply()

project: str = ""
app_name: str = ""
_deployed: bool = True if Path.cwd().name == "app" else False  # or "srv"?
_pkg_path: AsyncPath = AsyncPath(__file__).parent
_base_path: AsyncPath = AsyncPath.cwd()
_tmp_path: AsyncPath = _base_path / "tmp"
_secrets_path: AsyncPath = _tmp_path / "secrets"
_settings_path: AsyncPath = _base_path / "settings"
_app_settings_path: AsyncPath = _settings_path / "app.yml"
_adapter_settings_path: AsyncPath = _settings_path / "adapters.yml"
_adapters_path = _pkg_path / "adapters"
required_adapters: ContextVar[dict[str, str]] = ContextVar(
    "required_adapters", default={"secrets": "secret_manager", "logger": "loguru"}
)
_app_secrets: ContextVar[set[str]] = ContextVar("_app_secrets", default=set())
loaded_adapters: ContextVar[set[str]] = ContextVar("loaded_adapters", default=set())
available_adapters: ContextVar[dict[str, str | None]] = ContextVar(
    "available_adapters", default={}
)
available_modules: ContextVar[dict[str, dict[str, AsyncPath]]] = ContextVar(
    "available_modules", default={}
)
enabled_adapters: ContextVar[dict[str, str]] = ContextVar(
    "enabled_adapters", default={}
)
package_registry: ContextVar[dict[str, str]] = ContextVar(
    "package_registry", default={}
)
logger_registry: ContextVar[set[str]] = ContextVar("logger_registry", default=set())


async def init_app() -> None:
    for path in (
        _tmp_path,
        _secrets_path,
        _settings_path,
    ):
        await path.mkdir(exist_ok=True)
    enabled_adapters.get().update(required_adapters.get())


asyncio.run(init_app())


def gen_password(size: int = 10) -> str:
    return secrets.token_urlsafe(size)


async def update_available_modules(
    adapters_path: AsyncPath,
) -> dict[str, dict[str, AsyncPath]]:
    _available_modules = available_modules.get()
    for adapter, module in {
        a.stem: {m.stem: m async for m in a.rglob("*.py") if not m.name.startswith("_")}
        async for a in adapters_path.iterdir()
        if await a.is_dir() and not a.name.startswith("__")
    }.items():
        _available_modules.update({adapter: module})
    available_modules.set(_available_modules)
    return _available_modules


async def update_available_adapters(adapters_path: AsyncPath) -> dict[str, str | None]:
    await update_available_modules(adapters_path)
    _available_modules = available_modules.get()
    if not await _adapter_settings_path.exists():
        await dump.yaml(
            {cat: None for cat in _available_modules} | required_adapters.get(),
            _adapter_settings_path,
        )
    _available_adapters = await load.yaml(_adapter_settings_path)
    _available_adapters.update(
        {a: None for a in _available_modules if a not in _available_adapters}
    )
    available_adapters.set(_available_adapters)
    await dump.yaml(_available_adapters, _adapter_settings_path)
    return _available_adapters


async def update_enabled_adapters() -> dict[str, str]:
    _enabled_adapters = enabled_adapters.get()
    _enabled_adapters.update(
        ({a: m for (a, m) in available_adapters.get().items() if m})
    )
    enabled_adapters.set(_enabled_adapters)
    return _enabled_adapters


async def register_package() -> tuple[str, AsyncPath, AsyncPath, dict[str, str | None]]:
    _packages = package_registry.get()
    _pkg_path = AsyncPath(currentframe().f_code.co_filename).parent
    _pkg_name = _pkg_path.name
    _adapters_path = _pkg_path / "adapters"
    package_registry.set({_pkg_name: str(_adapters_path)} | _packages)
    _available_adapters = await update_available_adapters(_adapters_path)
    return _pkg_name, _pkg_path, _adapters_path, _available_adapters


def import_adapter(adapter_name: t.Optional[str] = None) -> t.Any:
    # with suppress(KeyError):
    _pkg_path = Path(currentframe().f_code.co_filename).parent
    if adapter_name is None:
        adapter_name = Path(currentframe().f_back.f_code.co_filename).parent.stem
    _adapter_path = _pkg_path / "adapters" / adapter_name
    _adapter_class_name = camelize(adapter_name)
    _adapter_settings_class_name = f"{_adapter_class_name}Settings"
    _module_name = (
        enabled_adapters.get().get(adapter_name)
        or required_adapters.get().get(adapter_name)
        or ""
    )
    _module_path = _pkg_path / "adapters" / adapter_name / _module_name
    _imported_module = import_module(".".join(_module_path.parts[-4:]))
    _adapter_settings_class = getattr(_imported_module, _adapter_settings_class_name)
    _adapter_class = getattr(_imported_module, _adapter_class_name)
    loaded_adapters.get().add(adapter_name)
    return _adapter_class, _adapter_settings_class
    # if adapter_name in required_adapters.get():
    #     raise SystemExit(f"Required adapter {adapter_name!r} not found.")
    # warn(f"Adapter {adapter_name!r} not found.")


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


class FileSecretsSource(PydanticBaseSettingsSource):
    # def __init__(
    #     self,
    #     settings_cls: type[BaseSettings],
    #     secrets_dir: str | Path | None = None,
    #     case_sensitive: bool | None = None,
    #     env_prefix: str | None = None,
    # ) -> None:
    #     super().__init__(settings_cls)
    #     self.secrets_dir = (
    #         secrets_dir if secrets_dir is not None else self.config.get("secrets_dir")
    #     )

    async def get_field_value(self, field_name: str) -> SecretStr | None:
        path = self.secrets_path / field_name
        if await path.is_file():
            return SecretStr((await path.read_text()).strip())

    async def __call__(self) -> dict[str, t.Any]:
        data = {}
        if self.adapter_name == "debug":
            return data
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
        return f"FileSecretsSource(_secrets_dir={self.secrets_dir!r})"


class ManagerSecretsSource(PydanticBaseSettingsSource):
    @alru_cache(maxsize=1)
    async def get_manager(self):
        manager = import_adapter("secrets")[0]()
        await manager.init()
        return manager

    async def load_secrets(self) -> t.Any:
        data = {}
        adapter_secrets = self.get_model_secrets()
        missing_secrets = {
            n: v for n, v in adapter_secrets.items() if n not in _app_secrets.get()
        }
        if missing_secrets:
            manager = await self.get_manager()
            manager_secrets = await manager.list(self.adapter_name)
            for field_key, field_value in missing_secrets.items():
                stored_field_key = "_".join((app_name, field_key))
                secret_path = self.secrets_dir / field_key
                if not await secret_path.exists():
                    if field_key not in manager_secrets:
                        await manager.create(
                            stored_field_key, field_value.default.get_secret_value()
                        )
                secret = await manager.get(stored_field_key)
                await secret_path.write_text(secret)
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                data[field_name] = SecretStr(secret)
                _app_secrets.get().add(field_key)
        return data

    async def __call__(self) -> t.Any:
        if self.adapter_name == "debug":
            return {}
        data = await self.load_secrets()
        return data


class YamlSettingsSource(PydanticBaseSettingsSource):
    async def load_yml_settings(self) -> t.Any:
        global project, app_name
        if self.adapter_name == "secrets":
            return {}
        yml_path = _settings_path / f"{self.adapter_name}.yml"
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
            for adptr in [
                adptr
                for adptr in enabled_adapters.get()
                if adptr not in yml_settings.keys()
            ]:
                yml_settings[adptr] = False
        if not _deployed:
            await dump.yaml(yml_settings, yml_path)
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
        file_secrets_settings = FileSecretsSource(
            self.__class__,
            secrets_dir=secrets_dir,
        )
        manager_secrets_settings = ManagerSecretsSource(
            self.__class__,
            secrets_dir=secrets_dir,
        )
        yaml_settings = YamlSettingsSource(self.__class__)

        sources = self.settings_customize_sources(
            self.__class__,
            init_settings=init_settings,
            yaml_settings=yaml_settings,
            file_secrets_settings=file_secrets_settings,
            manager_secrets_settings=manager_secrets_settings,
        )
        return deep_update(*reversed([await source() for source in sources]))

    @classmethod
    def settings_customize_sources(
        cls,
        settings_cls: t.Type["Settings"],
        # settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        yaml_settings: PydanticBaseSettingsSource,
        file_secrets_settings: PydanticBaseSettingsSource,
        manager_secrets_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            yaml_settings,
            file_secrets_settings,
            manager_secrets_settings,
        )


class DebugSettings(Settings):
    main: bool = False
    production: bool = False
    secrets: bool = False
    logger: bool = False
    app: bool = False
    adapters: bool = False


class AppSettings(Settings):
    project: str = "test-project"
    name: str = "test"
    title: str = "Test App"
    domain: str = "test_app.local"
    secret_key: SecretStr = SecretStr(token_urlsafe(32))
    secure_salt: SecretStr = SecretStr(str(token_bytes(32)))

    def model_post_init(self, __context: t.Any) -> None:
        self.title = self.title or titleize(self.name)


class Config(BaseSettings, extra="allow"):
    deployed: bool = _deployed
    debug: t.Optional[Settings] = None
    app: t.Optional[Settings] = None

    def __getattr__(self, item: str) -> t.Any:
        return super().__getattr__(item)  # type: ignore

    async def init(self) -> t.Any:
        (
            _pkg_name,
            _pkg_path,
            _adapters_path,
            _available_adapters,
        ) = await register_package()
        _enabled_adapters = await update_enabled_adapters()
        for a in required_adapters.get():
            _enabled_adapters = {a: _enabled_adapters.pop(a)} | _enabled_adapters
        del _enabled_adapters["secrets"]
        enabled_adapters.set(_enabled_adapters)
        self.app = AppSettings()
        self.debug = DebugSettings()


depends.set(Config, Config())
