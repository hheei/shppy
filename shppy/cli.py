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

def _discover_and_register_tools() -> None:
    """Discover all `shppy.tools.*` modules that define a Typer `app` and register them."""
    import importlib
    import pkgutil

    package = tools
    # If tools.__all__ exists, prefer it as explicit ordering and selection.
    modules = []
    if hasattr(package, "__all__"):
        for tool in getattr(package, "__all__"):
            modules.append(f"{package.__name__}.{tool}")
    else:
        for module_info in pkgutil.iter_modules(package.__path__, prefix=package.__name__ + "."):
            _, module_name, _ = module_info
            modules.append(module_name)

    for module_name in modules:
        # ignore private/internal modules
        basename = module_name.rsplit(".", 1)[-1]
        if basename.startswith("_"):
            continue

        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        app_obj = getattr(module, "app", None)
        if app_obj is None:
            continue

        try:
            if not isinstance(app_obj, typer.Typer):
                continue
        except Exception:
            continue

        try:
            app.add_typer(app_obj, name=basename)
        except Exception:
            continue


_discover_and_register_tools()

