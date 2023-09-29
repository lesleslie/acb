import asyncio
import secrets
import sys
import typing as t
from abc import ABC
from abc import abstractmethod
from contextlib import suppress
from contextvars import ContextVar
from importlib import import_module
from inspect import currentframe
from pathlib import Path
from secrets import token_bytes
from secrets import token_urlsafe
from warnings import warn
from platform import python_version_tuple

import nest_asyncio
from acb.actions import dump
from acb.actions import load
from acb.depends import depends
from aiopath import AsyncPath
from async_lru import alru_cache
from inflection import camelize
from inflection import titleize
from inflection import underscore
from pydantic import AliasChoices
from pydantic import AliasPath
from pydantic import BaseModel
from pydantic import SecretStr
from pydantic._internal._utils import deep_update
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from pydantic_settings.sources import _annotation_is_complex
from pydantic_settings.sources import SettingsError
from pydantic_settings.utils import path_type_label
from pydantic_settings.utils import path_type_labels

nest_asyncio.apply()

_deployed: bool = True if Path.cwd().name == "app" else False  # or "srv"?
_app_secrets: set[str] = set()
_secrets_path: AsyncPath = AsyncPath("tmp/secrets")
project: str = ""
app_name: str = ""
required_adapters: ContextVar[set[str]] = ContextVar(
    "required_adapters", default={"logger", "secrets"}
)
adapter_categories: ContextVar[set[str]] = ContextVar(
    "adapter_categories", default=set()
)
available_adapters: ContextVar[dict[str, str]] = ContextVar(
    "available_adapters", default={}
)
enabled_adapters: ContextVar[dict[str, str]] = ContextVar(
    "enabled_adapters", default={}
)
package_registry: ContextVar[dict[str, AsyncPath]] = ContextVar(
    "package_registry", default={}
)


def register_package() -> None:
    packages = package_registry.get()
    pkg_path = AsyncPath(currentframe().f_code.co_filename).parent
    pkg_name = pkg_path.stem
    packages[pkg_name] = pkg_path
    package_registry.set(packages)


def gen_password(size: int = 10) -> str:
    return secrets.token_urlsafe(size)


def import_adapter(adapter: t.Optional[str] = None) -> t.Any:
    with suppress(KeyError):
        adapter_dir = Path(currentframe().f_back.f_code.co_filename).parent
        if not adapter:
            adapter = adapter_dir.stem
        adapter_class = camelize(adapter)
        adapter_settings_class = f"{adapter_class}Settings"
        adapter_path = adapter_dir / enabled_adapters.get()[adapter]
        adapter_module = import_module(".".join(adapter_path.parts[-4:]))
        return getattr(adapter_module, adapter_class), getattr(
            adapter_module, adapter_settings_class
        )
    if adapter in required_adapters.get():
        raise SystemExit(f"Required adapter {adapter!r} not found.")
    warn(f"Adapter {adapter!r} not found.")


class PydanticBaseSettingsSource(ABC):
    def __init__(self, settings_cls: type["Settings"]) -> None:
        self.settings_cls = settings_cls
        self.config = settings_cls.model_config

    @abstractmethod
    def get_field_value(self, field: FieldInfo, field_name: str) -> t.Any:
        raise NotImplementedError()

    @staticmethod
    def field_is_complex(field: FieldInfo) -> bool:
        return _annotation_is_complex(field.annotation, field.metadata)

    async def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        if (self.field_is_complex(field) or value_is_complex) and value:
            return await load.json(value)
        return value

    @abstractmethod
    async def __call__(self) -> t.Any:
        raise NotImplementedError()


class InitSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self, settings_cls: type["Settings"], init_kwargs: dict[str, t.Any]
    ) -> None:
        self.init_kwargs = init_kwargs
        super().__init__(settings_cls)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[t.Any, str, bool]:
        return None, "", False

    async def __call__(self) -> t.Any:
        return self.init_kwargs

    def __repr__(self) -> str:
        return f"InitSettingsSource(init_kwargs={self.init_kwargs!r})"


class FileSecretsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type["Settings"],
        secrets_dir: t.Optional[str | AsyncPath | Path] = None,
    ) -> None:
        super().__init__(settings_cls)
        self.secrets_dir = secrets_dir or self.config.get("secrets_dir")

    @staticmethod
    async def path_type_label(p: AsyncPath) -> t.Any:
        if await p.exists():
            for method, name in path_type_labels.items():
                if getattr(p, method)():
                    return name
            return "unknown"

    @classmethod
    async def find_case_path(
        cls,
        dir_path: AsyncPath,
        file_name: str,
    ) -> t.Any:
        async for f in dir_path.iterdir():
            if f.name == file_name or f.name.lower() == file_name.lower():
                return f
        return None

    def _extract_field_info(
        self, field: FieldInfo, field_name: str
    ) -> list[tuple[str, str, bool]]:
        field_info: list[tuple[str, str, bool]] = []
        if isinstance(field.validation_alias, (AliasChoices, AliasPath)):
            v_alias: t.Optional[
                str | list[str | int] | list[list[str | int]]
            ] = field.validation_alias.convert_to_aliases()
        else:
            v_alias = field.validation_alias

        def add_to_field_info(alias: str, condition: bool) -> None:
            return field_info.append((alias, alias, condition))

        if v_alias:
            if isinstance(v_alias, list):  # AliasChoices, AliasPath
                for alias in v_alias:
                    if isinstance(alias, str):  # AliasPath
                        add_to_field_info(alias, True if len(alias) > 1 else False)
                    elif isinstance(alias, list):  # AliasChoices
                        first_arg = t.cast(str, alias[0])
                        add_to_field_info(first_arg, True if len(alias) > 1 else False)
            else:  # string validation alias
                add_to_field_info(v_alias, False)
        else:
            add_to_field_info(field_name, False)
        return field_info

    async def get_field_value(self, field: FieldInfo, field_name: str) -> t.Any:
        field_key: str = ""
        value_is_complex: bool = False
        for field_key, env_name, value_is_complex in self._extract_field_info(
            field, field_name
        ):
            path = await self.find_case_path(self.secrets_path, env_name)
            if not path:
                continue
            if await path.is_file():
                return (
                    SecretStr((await path.read_text()).strip()),
                    field_key,
                    value_is_complex,
                )
            else:
                warn(
                    f"attempted to load secret file {path!r} but found a "
                    f"{await self.path_type_label(path)} instead",
                    stacklevel=4,
                )
        return None, field_key, value_is_complex

    async def __call__(self) -> t.Any:
        global _app_secrets
        data: dict[str, t.Any] = {}
        self.adapter_name: str = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        if self.adapter_name == "debug":
            return data
        if self.secrets_dir is None:
            return data
        self.secrets_path = await AsyncPath(self.secrets_dir).expanduser()
        if not await self.secrets_path.exists():
            warn(f'directory "{self.secrets_path}" does not exist')
            await self.secrets_path.mkdir(parents=True, exist_ok=True)
        if not await self.secrets_path.is_dir():
            raise SettingsError(
                f"secrets_dir must reference a directory, not a "
                f"{path_type_label(self.secrets_path)}"
            )
        for field_name, field in self.settings_cls.model_fields.items():
            try:
                field_value, field_key, value_is_complex = await self.get_field_value(
                    field, "_".join([self.adapter_name, field_name])
                )
            except Exception as e:
                raise SettingsError(
                    f'error getting value for field "{field_name}" from '
                    f'source "{self.__class__.__name__}"'
                ) from e
            try:
                field_value = await self.prepare_field_value(
                    field_name, field, field_value, value_is_complex
                )
            except ValueError:
                raise SettingsError(
                    f'error parsing value for field "{field_name}" from'
                    f' source "{self.__class__.__name__}"'
                )
            if field_value is not None:
                _app_secrets.add(field_key)
                data[field_name] = field_value
        return data

    def __repr__(self) -> str:
        return f"FileSecretsSource(_secrets_dir={self.secrets_dir!r})"


class ManagerSecretsSource(FileSecretsSource):
    adapter_name: str = ""

    @alru_cache(maxsize=1)
    async def get_manager(self):
        # manager = load_adapter("secrets")[0]()
        manager, _ = import_adapter("secrets")
        await manager.init()
        return manager

    async def load_secrets(self) -> t.Any:
        global _app_secrets
        data: dict[str, t.Any] = {}
        model_secrets = {
            "_".join((self.adapter_name, n)): v
            for n, v in self.settings_cls.model_fields.items()
            if v.annotation is SecretStr
        }
        unfetched_secrets = {
            n: v for n, v in model_secrets.items() if n not in _app_secrets
        }
        if unfetched_secrets:
            manager = await self.get_manager()
            manager_secrets = await manager.list(self.adapter_name)
            for field_key, field_value in unfetched_secrets.items():
                field_name = field_key.removeprefix(f"{self.adapter_name}_")
                stored_field_key = "_".join((_app_name, field_key))
                secret_path = _secrets_path / field_key
                if not await secret_path.exists():
                    if field_key not in manager_secrets:
                        await manager.create(
                            stored_field_key, field_value.default.get_secret_value()
                        )
                    secret = await manager.get(stored_field_key)
                    await secret_path.write_text(secret)
                    data[field_name] = secret
                _app_secrets.add(field_key)
        return data

    async def get_field_value(self, field: FieldInfo, field_name: str) -> t.Any:
        return field, field_name, False

    async def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        return value

    async def __call__(self) -> t.Any:
        data: dict[str, t.Any] = {}
        self.adapter_name: str = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        if self.adapter_name == "debug" or self.secrets_dir is None:
            return data
        await self.load_secrets()
        return await super().__call__()


class YamlSettingsSource(PydanticBaseSettingsSource):
    adapter_name: str = "app"

    async def load_yml_settings(self) -> t.Any:
        global _project, _app_name
        if self.adapter_name == "secrets":
            return {}
        yml_path = AsyncPath.cwd() / "settings" / f"{self.adapter_name}.yml"
        if not await yml_path.exists() and not _deployed:
            await yml_path.touch(exist_ok=True)
            dump_settings = {
                k: v.default
                for k, v in self.settings_cls.model_fields.items()
                if v.annotation is not SecretStr
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
            _project = yml_settings["project"]
            _app_name = yml_settings["name"]
        return yml_settings

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> t.Tuple[t.Any, str, bool]:
        return field, field_name, False

    async def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        return value

    async def __call__(self) -> t.Any:
        self.adapter_name: str = underscore(
            self.settings_cls.__name__.replace("Settings", "")
        )
        data: t.Dict[str, t.Any] = {}
        if Path.cwd().name != "acb":
            for field_name, field in (await self.load_yml_settings()).items():
                field_value, field_key, value_is_complex = self.get_field_value(
                    field, field_name
                )
                field_value = await self.prepare_field_value(
                    field_name, field, field_value, value_is_complex
                )
                if field_value is not None:
                    data[field_key] = field_value
            return data
        return data


class Settings(BaseModel):
    model_config: SettingsConfigDict = SettingsConfigDict(  # type: ignore
        extra="allow",
        arbitrary_types_allowed=True,
        validate_default=True,
        secrets_dir=None,
        protected_namespaces=("model_", "settings_"),
    )

    def __getattr__(self, item: str) -> t.Any:
        return super().__getattr__(item)  # type: ignore

    def __init__(
        __pydantic_self__,  # type: ignore
        _secrets_dir: t.Optional[str | AsyncPath | Path] = None,
        **values: t.Any,
    ) -> None:
        build_settings = __pydantic_self__._settings_build_values(
            values,
            _secrets_dir=_secrets_dir,
        )
        build_settings = asyncio.run(build_settings)
        super().__init__(**build_settings)

    async def _settings_build_values(
        self,
        init_kwargs: dict[str, t.Any],
        _secrets_dir: t.Optional[str | AsyncPath | Path] = None,
    ) -> t.Any:
        secrets_dir = _secrets_dir or self.model_config.get("secrets_dir")
        init_settings = InitSettingsSource(self.__class__, init_kwargs=init_kwargs)
        file_secrets_settings = FileSecretsSource(
            self.__class__,
            secrets_dir=secrets_dir,
        )
        sources = self.settings_customise_sources(
            self.__class__,
            init_settings=init_settings,
            file_secrets_settings=file_secrets_settings,
        )
        if sources:
            return deep_update(*reversed([await source() for source in sources]))
        return {}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type["Settings"],
        init_settings: PydanticBaseSettingsSource,
        file_secrets_settings: PydanticBaseSettingsSource,
    ) -> tuple[
        PydanticBaseSettingsSource,
        YamlSettingsSource,
        PydanticBaseSettingsSource,
        ManagerSecretsSource,
    ]:
        return (
            init_settings,
            YamlSettingsSource(settings_cls),
            file_secrets_settings,
            ManagerSecretsSource(settings_cls),
        )


class DebugSettings(Settings):
    production: bool = False
    main: bool = False
    secrets: bool = False
    logger: bool = False
    app: bool = False


class AppSettings(Settings):
    project: str = "myproject"
    name: str = "myapp"
    title: t.Optional[str] = "My App"
    domain: str = "mydomain.local"
    secret_key: SecretStr = SecretStr(token_urlsafe(32))
    secure_salt: SecretStr = SecretStr(str(token_bytes(32)))
    _secrets_dir: t.Optional[str | Path | AsyncPath] = None

    def model_post_init(self, __context: t.Any) -> None:
        self.domain = f"{self.name}.local"
        self.title = self.title or titleize(self.name)


class Config(BaseSettings, extra="allow"):
    pkgdir: AsyncPath = AsyncPath(__file__).parent
    basedir: AsyncPath = AsyncPath.cwd()
    deployed: bool = False
    tmp: t.Optional[AsyncPath] = None
    app_settings_path: t.Optional[AsyncPath] = None
    adapter_settings_path: t.Optional[AsyncPath] = None
    secrets_path: t.Optional[AsyncPath] = None
    available_adapters: dict[str, t.Any] = {}
    adapter_categories: set[str] = set()
    enabled_adapters: dict[str, str] = {}
    debug: t.Optional[Settings] = None
    app: t.Optional[Settings] = None

    def model_post_init(self, __context: t.Any) -> None:
        self.tmp = self.basedir / "tmp"
        self.app_settings_path = self.basedir / "settings"
        self.adapter_settings_path = self.app_settings_path / "adapters.yml"
        self.secrets_path = self.basedir / _secrets_path
        self.deployed = True if self.basedir.name == "app" else _deployed
        self.app = AppSettings(_secrets_dir=self.secrets_path)
        self.debug = DebugSettings()
        self.deployed = _deployed

    def __getattr__(self, item: str) -> t.Any:
        return super().__getattr__(item)  # type: ignore

    async def init(self, deployed: bool = False) -> t.Any:
        self.deployed = deployed
        for path in (
            self.app_settings_path,
            self.tmp,
            self.secrets_path,
        ):
            await path.mkdir(exist_ok=True)
        py_version = ".".join(python_version_tuple()[0:2])
        mod_dir = self.basedir / "__pypackages__" / py_version / "lib"
        sys.path.append(str(mod_dir))
        if self.basedir.name != "acb":
            self.adapter_categories = {
                path.stem
                async for path in (self.pkgdir / "adapters").iterdir()
                if await path.is_dir() and not path.name.startswith("__")
            }
            if not await self.adapter_settings_path.exists():
                await dump.yaml(
                    {cat: None for cat in self.adapter_categories},
                    self.adapter_settings_path,
                )
            self.available_adapters = await load.yaml(self.adapter_settings_path)
            for adapter in [
                a for a in self.adapter_categories if a not in self.available_adapters
            ]:
                self.available_adapters[adapter] = None
            await dump.yaml(self.available_adapters, self.adapter_settings_path)
            self.enabled_adapters = {
                c: a
                for c, a in self.available_adapters.items()
                if c in self.adapter_categories and a
            }
            for a in required_adapters.get():
                self.enabled_adapters = {
                    a: self.enabled_adapters.pop(a),
                    **self.enabled_adapters,
                }
            del self.enabled_adapters["secrets"]
            adapter_categories.set(self.adapter_categories)
            available_adapters.set(self.available_adapters)
            enabled_adapters.set(self.enabled_adapters)
        return self


depends.set(Config, Config())
