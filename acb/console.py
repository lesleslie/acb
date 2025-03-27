import asyncio
import typing as t

from aioconsole import aprint
from rich import box
from rich.console import Console, RenderableType
from rich.padding import Padding
from rich.table import Table
from rich.traceback import install
from acb import pkg_registry
from acb.actions import action_registry
from acb.adapters import get_adapters
from acb.config import Config
from acb.depends import depends


class RichConsole(Console):
    config: Config = depends()

    def __init__(self) -> None:
        super().__init__()
        if not self.config.deployed:
            install(console=self)

    def _write_buffer(self) -> None:
        with self._lock:
            if self.record and not self._buffer_index:
                with self._record_buffer_lock:
                    self._record_buffer.extend(self._buffer[:])

            if self._buffer_index == 0:
                text = self._render_buffer(self._buffer[:])
                try:
                    asyncio.run(aprint(text))
                except UnicodeEncodeError as error:
                    error.reason = (
                        f"{error.reason}\n*** You may need to add"
                        f" PYTHONIOENCODING=utf-8 to your environment ***"
                    )
                    raise
                self.file.flush()
                del self._buffer[:]


console = RichConsole()

table_args: dict[str, t.Any] = {
    "show_lines": True,
    "box": box.ROUNDED,
    "min_width": 100,
    "border_style": "bold blue",
}


@depends.inject
def display_components(config: Config = depends()) -> None:
    if not config.deployed:
        pkgs = Table(
            title="[b][u bright_white]A[/u bright_white][bright_green]synchronous "
            "[u bright_white]C[/u bright_white][bright_green]omponent "
            "[u bright_white]B[/u bright_white][bright_green]ase[/b]",
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
