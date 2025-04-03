from pathlib import Path

import typer

cli = typer.Typer()

acb_path = Path(__file__)

app_name = Path.cwd().stem

if Path.cwd() == acb_path:
    raise SystemExit("ACB can not be run in the same directory as ACB itself.")
