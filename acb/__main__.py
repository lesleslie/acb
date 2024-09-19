import typer
from rich.traceback import install
from acb.console import console

cli = typer.Typer()

install(console=console)
