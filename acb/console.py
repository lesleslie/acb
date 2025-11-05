import asyncio
import os
import re
import sys
from contextlib import suppress
from typing import Any, Literal

from aioconsole import aprint
from rich.console import Console as RichConsole
from rich.style import Style
from rich.text import Text
from rich.traceback import install
from acb.depends import depends


class Console(RichConsole):
    def __init__(self) -> None:
        # Detect non-interactive/plain environments early
        plain = False
        try:
            if os.environ.get("NO_COLOR") or os.environ.get("CJ_PLAIN_OUTPUT"):
                plain = True
            elif os.environ.get("CI") and not os.environ.get("CJ_FORCE_COLOR"):
                plain = True
            else:
                stream = sys.stdout
                if hasattr(stream, "isatty") and not stream.isatty():
                    plain = True
        except Exception:
            # If detection fails, prefer plain output to avoid ANSI leakage
            plain = True

        # Set up Rich Console arguments based on environment detection
        no_color = plain
        force_terminal = False if plain else None
        color_system: (
            Literal["auto", "standard", "256", "truecolor", "windows"] | None
        ) = "auto" if not plain else None

        super().__init__(
            no_color=no_color,
            force_terminal=force_terminal,
            color_system=color_system,
        )

        # Cache for quick checks during print calls
        self._plain_mode = plain
        # Pre-compiled ANSI pattern for stripping pre-colored input strings
        self._ansi_re = re.compile(
            r"\x1b\[[0-9;]*m"
        )  # REGEX OK: ANSI escape sequence stripping - simple character class pattern, no backtracking risk

    def print(  # type: ignore[override]
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Style | str | None = None,
        justify: Literal["default", "left", "center", "right", "full"] | None = None,
        overflow: Literal["fold", "crop", "ellipsis", "ignore"] | None = None,
        no_wrap: bool | None = None,
        emoji: bool | None = None,
        markup: bool | None = None,
        highlight: bool | None = None,
        width: int | None = None,
        height: int | None = None,
        crop: bool = True,
        soft_wrap: bool | None = None,
        new_line_start: bool = False,
    ) -> None:
        if not getattr(self, "_plain_mode", False):
            return super().print(
                *objects,
                sep=sep,
                end=end,
                style=style,
                justify=justify,
                overflow=overflow,
                no_wrap=no_wrap,
                emoji=emoji,
                markup=markup,
                highlight=highlight,
                width=width,
                height=height,
                crop=crop,
                soft_wrap=soft_wrap,
                new_line_start=new_line_start,
            )

        # In plain mode: strip rich markup and ANSI from string args
        processed: list[object] = []
        for obj in objects:
            if isinstance(obj, str):
                try:
                    text = Text.from_markup(obj).plain
                except Exception:
                    text = obj
                text = self._ansi_re.sub("", text)
                processed.append(text)
            else:
                processed.append(obj)

        # Disable highlighting which may introduce styling
        if highlight is None:
            highlight = False

        return super().print(
            *processed,
            sep=sep,
            end=end,
            style=style,
            justify=justify,
            overflow=overflow,
            no_wrap=no_wrap,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
            width=width,
            height=height,
            crop=crop,
            soft_wrap=soft_wrap,
            new_line_start=new_line_start,
        )

    def _write_buffer(self) -> None:
        with self._lock:
            if self.record and (not self._buffer_index):
                with self._record_buffer_lock:
                    self._record_buffer.extend(self._buffer[:])
            if self._buffer_index == 0:
                text = self._render_buffer(self._buffer[:])
                try:
                    # Try to get existing event loop first
                    loop = None
                    with suppress(RuntimeError):
                        loop = asyncio.get_running_loop()

                    if loop is not None:
                        # Event loop is running, schedule the coroutine
                        try:
                            asyncio.run_coroutine_threadsafe(aprint(text, end=""), loop)
                        except RuntimeError:
                            # and use synchronous write as fallback
                            self.file.write(text)
                    else:
                        # No running loop, safe to use asyncio.run
                        asyncio.run(aprint(text, end=""))
                except UnicodeEncodeError as error:
                    error.reason = (
                        f"{error.reason}\n*** You may need to add"
                        f" PYTHONIOENCODING=utf-8 to your environment ***"
                    )
                    raise
                self.file.flush()
                del self._buffer[:]


console = Console()
depends.set(Console, console)


if os.getenv("DEPLOYED", "False").lower() != "true":
    install(console=console)
