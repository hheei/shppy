from __future__ import annotations

import typer
from shppy import tools

app = typer.Typer(no_args_is_help=True, help="Shppy command line interface.")


@app.callback()
def main(
    ctx: typer.Context,
    silent: bool = typer.Option(
        False,
        "--silent",
        "-s",
        help="Disable interactive TUI; only CLI arguments and defaults are used.",
    ),
) -> None:
    """
    Top-level callback to store global options (currently only --silent).
    """
    ctx.obj = {"silent": silent}


# Manual linkage: each tool owns its subcommand and parser.
app.add_typer(tools.s2s.app, name="s2s")


if __name__ == "__main__":  # pragma: no cover
    app()

