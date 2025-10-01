import asyncio
import os
from contextlib import suppress

from aioconsole import aprint
from rich.console import Console
from rich.traceback import install


class RichConsole(Console):
    def __init__(self) -> None:
        super().__init__()

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
                        # No running loop, safe to use asyncio.run
                        loop = asyncio.get_running_loop()

                    if loop is not None:
                        # Event loop is running, schedule the coroutine
                        # and use synchronous print as fallback
                        print(text, file=self.file)
                    else:
                        # No running loop, safe to use asyncio.run
                        asyncio.run(aprint(text))
                except UnicodeEncodeError as error:
                    error.reason = f"{error.reason}\n*** You may need to add PYTHONIOENCODING=utf-8 to your environment ***"
                    raise
                self.file.flush()
                del self._buffer[:]


console = RichConsole()
if os.getenv("DEPLOYED", "False").lower() != "true":
    install(console=console)
