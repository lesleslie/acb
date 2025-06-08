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


def register_pkg() -> None:
    frame = currentframe()
    if frame is not None and frame.f_back is not None:
        path = AsyncPath(frame.f_back.f_code.co_filename).parent
    else:
        raise RuntimeError("Could not determine caller frame")
    name = path.stem
    registry = pkg_registry.get()
    if name not in [p.name for p in registry]:
        actions = asyncio.run(register_actions(path))
        adapters = asyncio.run(register_adapters(path))
        pkg = Pkg(name=name, path=path, actions=actions, adapters=adapters)
        registry.append(pkg)


register_pkg()
table_args: dict[str, t.Any] = {
    "show_lines": True,
    "box": box.ROUNDED,
    "min_width": 100,
    "border_style": "bold blue",
}


def display_components() -> None:
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
