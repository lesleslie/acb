import asyncio

from aioconsole import aprint
from rich import box
from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.traceback import install
from acb.config import Config, adapter_registry
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


@depends.inject
def display_adapters(config: Config = depends()) -> None:
    if not config.deployed:
        table = Table(
            title="[b][u bright_white]A[/u bright_white][bright_green]synchronous "
            "[u bright_white]C[/u bright_white][bright_green]omponent "
            "[u bright_white]B[/u bright_white][bright_green]ase[/b]",
            show_lines=True,
            box=box.ROUNDED,
            min_width=88,
            border_style="bold blue",
            style="bold white",
        )
        for prop in ("Category", "Name", "Pkg", "Enabled"):
            table.add_column(prop)
        for adapter in adapter_registry.get():
            if adapter.enabled:
                table.add_row(
                    adapter.category,
                    adapter.name,
                    adapter.pkg,
                    str(adapter.enabled),
                    style="bold blue on white",
                )

            else:
                table.add_row(
                    adapter.category, adapter.name, adapter.pkg, str(adapter.enabled)
                )
        table = Padding(table, (2, 4))
        console.print(table)
