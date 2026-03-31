from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Optional

import typer
from prompt_toolkit.completion import WordCompleter

from shppy import Atoms, io
from shppy.tools.inputs import input_formats, input_path
from shppy.tui.prompts import FinishPrompt, TitlePrompt

KNOWN_FORMATS = {
    r".*\.(?:xyz|extxyz)$": "extxyz",
    r".*\.(?:vasp|poscar)$": "vasp",
    r".*\.cif$": "cif",
    r".*\.(?:lammpstraj|lammpstrj)$": "lammps-dump-text",
    r".*\.xml$": "espresso-xml",
    r"^(?:POSCAR|CONTCAR|XDATCAR)$": "vasp",
}

DEFAULT_EXTENSION = {
    "extxyz": ".xyz",
    "vasp": ".vasp",
    "cif": ".cif",
    "lammps-dump-text": ".lammpstrj",
    "espresso-xml": ".xml",
}

assert set(KNOWN_FORMATS.values()) == set(DEFAULT_EXTENSION.keys()), (
    "KNOWN_FORMATS and DEFAULT_EXTENSION keys must match."
)

_BUILD_FORMAT_CACHE = [
    (re.compile(pattern), fmt) for pattern, fmt in KNOWN_FORMATS.items()
]


def detect_fmt_by_path(path: str) -> Optional[str]:
    path = Path(path).name
    for rx, fmt in _BUILD_FORMAT_CACHE:
        if rx.match(path):
            return fmt
    return None


def default_format_completer():
    return WordCompleter(list(DEFAULT_EXTENSION.keys()), ignore_case=True)


app = typer.Typer(help="Structure-to-structure conversion.")


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    inp: Annotated[
        Optional[str], typer.Option("--input", "-i", help="Input structure file path.")
    ] = None,
    fmt: Annotated[
        Optional[str],
        typer.Option(
            "--format", "-f", help="Input structure format (overrides auto-detection)."
        ),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output structure file path."),
    ] = None,
    out_format: Annotated[
        Optional[str],
        typer.Option(
            "--out-format", "-F", help="Output format (overrides auto-detection)."
        ),
    ] = None,
):
    TitlePrompt("shppy s2s").run()

    available = list(DEFAULT_EXTENSION.keys())
    if fmt is not None and fmt not in available:
        FinishPrompt(False, f"In format '{fmt}' is not supported.").run()
        exit(1)
    if (
        out_format is not None
        and out_format not in available
        or out_format == "expresso-xml"
    ):
        FinishPrompt(False, f"Out format '{out_format}' is not supported.").run()
        exit(1)

    if inp is None:
        inp_pth = input_path("Input structure file", need_exist=True)
    else:
        inp_pth = Path(inp)
        if not inp_pth.is_file():
            FinishPrompt(False, f"Input file '{inp}' does not exist.").run()
            exit(1)

    if fmt is None:
        fmt = detect_fmt_by_path(str(inp_pth))
        fmt = input_formats(fmt, available)

    if fmt == "espresso-xml":
        atoms = io.espresso.XML(inp_pth).traj()
    else:
        atoms = Atoms.read_traj(str(inp_pth), format=fmt)

    if output is None:
        out_pth = inp_pth.parent / (inp_pth.stem + ".xyz")
        out_pth = input_path(
            "Output structure file",
            default=str(out_pth),
            ghost=str(out_pth),
            need_exist=False,
        )
    else:
        out_pth = Path(output)

    if out_format is None:
        out_format = detect_fmt_by_path(str(out_pth))
        out_format = input_formats(out_format, available)

    atoms.write(str(out_pth), format=out_format)

    FinishPrompt(True, "Success").run()
