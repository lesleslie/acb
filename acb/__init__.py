import asyncio
import typing as t
from contextvars import ContextVar
from inspect import currentframe

import nest_asyncio
import rich.repr
from anyio import Path as AsyncPath
from pydantic import BaseModel, ConfigDict
from rich import box
from rich.console import RenderableType
from rich.padding import Padding
from rich.table import Table

from .actions import Action, action_registry, register_actions
from .adapters import Adapter, _deployed, get_adapters, register_adapters
from .console import console

nest_asyncio.apply()


@rich.repr.auto
class Pkg(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    path: AsyncPath
    actions: list[Action] = []
    adapters: list[Adapter] = []


pkg_registry: ContextVar[list[Pkg]] = ContextVar("pkg_registry", default=[])
_lazy_registration_queue: list[tuple[str, AsyncPath]] = []
_registration_completed: bool = False


def register_pkg() -> None:
    frame = currentframe()
    if frame is not None and frame.f_back is not None:
        path = AsyncPath(frame.f_back.f_code.co_filename).parent
    else:
        raise RuntimeError("Could not determine caller frame")
    name = path.stem
    if name not in [item[0] for item in _lazy_registration_queue]:
        _lazy_registration_queue.append((name, path))


async def _process_registration_queue() -> None:
    global _registration_completed
    if _registration_completed or not _lazy_registration_queue:
        return
    registry = pkg_registry.get()
    existing_names = {p.name for p in registry}
    for name, path in _lazy_registration_queue:
        if name not in existing_names:
            actions = await register_actions(path)
            adapters = await register_adapters(path)
            pkg = Pkg(name=name, path=path, actions=actions, adapters=adapters)
            registry.append(pkg)
            existing_names.add(name)
    _lazy_registration_queue.clear()
    _registration_completed = True


def ensure_registration() -> None:
    if _lazy_registration_queue and not _registration_completed:
        try:
            asyncio.get_running_loop()
            asyncio.create_task(_process_registration_queue())
        except RuntimeError:
            asyncio.run(_process_registration_queue())


try:
    from pathlib import Path

    from anyio import Path as AsyncPath

    from .adapters import Adapter, _update_adapter_caches, adapter_registry

    if not any(
        a.pkg == "acb" and a.category == "models" for a in adapter_registry.get()
    ):
        acb_adapters_path = AsyncPath(Path(__file__).parent / "adapters")
        essential_adapters = [
            Adapter(
                name="sqlmodel",
                class_name="Models",
                category="models",
                pkg="acb",
                module="acb.adapters.models.sqlmodel",
                enabled=False,
                installed=False,
                path=acb_adapters_path / "models" / "sqlmodel.py",
            ),
            Adapter(
                name="memory",
                class_name="Cache",
                category="cache",
                pkg="acb",
                module="acb.adapters.cache.memory",
                enabled=False,
                installed=False,
                path=acb_adapters_path / "cache" / "memory.py",
            ),
            Adapter(
                name="redis",
                class_name="Cache",
                category="cache",
                pkg="acb",
                module="acb.adapters.cache.redis",
                enabled=False,
                installed=False,
                path=acb_adapters_path / "cache" / "redis.py",
            ),
            Adapter(
                name="file",
                class_name="Storage",
                category="storage",
                pkg="acb",
                module="acb.adapters.storage.file",
                enabled=False,
                installed=False,
                path=acb_adapters_path / "storage" / "file.py",
            ),
            Adapter(
                name="httpx",
                class_name="Requests",
                category="requests",
                pkg="acb",
                module="acb.adapters.requests.httpx",
                enabled=False,
                installed=False,
                path=acb_adapters_path / "requests" / "httpx.py",
            ),
            Adapter(
                name="cloudflare",
                class_name="Dns",
                category="dns",
                pkg="acb",
                module="acb.adapters.dns.cloudflare",
                enabled=False,
                installed=False,
                path=acb_adapters_path / "dns" / "cloudflare.py",
            ),
        ]
        registry = adapter_registry.get()
        registry.extend(essential_adapters)
        _update_adapter_caches()
except Exception as e:
    print(f"Warning: ACB essential adapters registration failed: {e}")
    pass
table_args: dict[str, t.Any] = {
    "show_lines": True,
    "box": box.ROUNDED,
    "min_width": 100,
    "border_style": "bold blue",
}


def display_components() -> None:
    ensure_registration()
    if not _deployed:
        pkgs = Table(
            title="[b][u bright_white]A[/u bright_white][bright_green]synchronous [u bright_white]C[/u bright_white][bright_green]omponent [u bright_white]B[/u bright_white][bright_green]ase[/b]",
            **table_args,
        )
        for prop in ("Pkg", "Path"):
            pkgs.add_column(prop)
        for i, pkg in enumerate(pkg_registry.get()):
            pkgs.add_row(
                pkg.name,
                str(pkg.path),
                style="bold white" if i % 2 else "bold white on blue",
            )
        pkgs_padded: RenderableType = Padding(pkgs, (2, 4, 0, 4))
        console.print(pkgs_padded)
        actns = Table(
            title="[b][u bright_white]A[/u bright_white][bright_green]ctions",
            **table_args,
        )
        for prop in ("Name", "Pkg", "Methods"):
            actns.add_column(prop)
        for i, action in enumerate(action_registry.get()):
            actns.add_row(
                action.name,
                action.pkg,
                ", ".join(action.methods),
                style="bold white" if i % 2 else "bold white on blue",
            )
        actns_padded: RenderableType = Padding(actns, (0, 4, 1, 4))
        console.print(actns_padded)
        adptrs = Table(
            title="[b][u bright_white]A[/u bright_white][bright_green]datpters",
            **table_args,
        )
        for prop in ("Category", "Name", "Pkg"):
            adptrs.add_column(prop)
        for i, adapter in enumerate(get_adapters()):
            adptrs.add_row(
                adapter.category,
                adapter.name,
                adapter.pkg,
                style="bold white" if i % 2 else "bold white on blue",
            )
        adptrs_padded: RenderableType = Padding(adptrs, (0, 4, 1, 4))
        console.print(adptrs_padded)
