from __future__ import annotations

from pathlib import Path
from typing import Optional

from ase import io as ase_io
from shppy.io import XML
import typer
from shppy.tui.helper import (
    default_format_completer,
    default_path_completer,
    validate_existing_path,
)
from shppy.tui.prompts import (
    FillPrompt,
    FinishPrompt,
    InfoPrompt,
    TitlePrompt,
)

SPECIAL_FILENAME_FORMATS = {
    "POSCAR": "vasp",
    "CONTCAR": "vasp",
    "XDATCAR": "vasp-xdatcar",
}

EXTENSION_FORMATS = {
    ".xyz": "xyz",
    ".extxyz": "extxyz",
    ".vasp": "vasp",
    ".cif": "cif",
    ".lammpstraj": "lammps-dump-text",
    ".lammpstrj": "lammps-dump-text",
    ".xml": "espresso-xml",
}

OUTPUT_SUFFIX_BY_FORMAT = {
    "xyz": ".xyz",
    "extxyz": ".xyz",
    "vasp": ".POSCAR",
    "poscar": ".POSCAR",
    "vasp-xdatcar": ".XDATCAR",
}

SPECIAL_BASENAME_FORMATS = {
    "POSCAR": "vasp",
    "CONTCAR": "vasp",
    "XDATCAR": "vasp-xdatcar",
}

DEFAULT_OUTPUT_FORMAT = "extxyz"


app = typer.Typer(invoke_without_command=True, no_args_is_help=False, help="Structure-to-structure conversion.")


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    input: Optional[Path] = typer.Option(None, "--input", "-i", help="Input structure file path."),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Input format (overrides auto-detection)."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path (file or directory)."),
    out_format: Optional[str] = typer.Option(None, "--out-format", "-F", help="Output format (overrides auto-detection)."), 
) -> None:
    in_path = input.expanduser() if input is not None else None
    in_format = format
    out_path = output.expanduser() if output is not None else None

    if in_path is not None and in_format is None:
        in_format = SPECIAL_FILENAME_FORMATS.get(in_path.name.upper())
        if in_format is None:
            in_format = EXTENSION_FORMATS.get(in_path.suffix.lower())

    root = ctx.find_root()
    silent = bool(getattr(root, "obj", None) and root.obj.get("silent"))

    if silent:
        if in_path is None:
            raise typer.Exit(code=1)
        if not in_path.exists():
            raise typer.Exit(code=1)
        if in_format is None:
            raise typer.Exit(code=1)
    else:
        TitlePrompt("shppy s2s").run()
        InfoPrompt(
            "Information", "\n"
                           "Structure format conversion tool.\n"
                           "params:\n"
                           "  input(Path): Input structure file path\n"
                           "  format(str): Input format\n"
                           "  output(Path): Output file/directory\n"
                           "  out_format(str): Output format\n"
        ).run()

        if in_path is None:
            resolved_input: Optional[Path] = None

            def _validate_input_path(text: str) -> tuple[bool, str]:
                nonlocal resolved_input
                ok, msg, resolved = validate_existing_path(text)
                if ok and resolved is not None:
                    resolved_input = resolved
                    return True, ""
                return False, msg

            FillPrompt("Input path", value="").run(
                ghost="",
                completer=default_path_completer(),
                validator=_validate_input_path,
            )
            in_path = resolved_input

        if in_format is None:
            guessed_in_format = SPECIAL_FILENAME_FORMATS.get(in_path.name.upper())
            if guessed_in_format is None:
                guessed_in_format = EXTENSION_FORMATS.get(in_path.suffix.lower())
            in_format = (
                FillPrompt("Input format", value="").run(
                    ghost=guessed_in_format or "",
                    completer=default_format_completer(),
                )
                or guessed_in_format
                or None
            )

        if out_path is None:
            default_output = Path(in_path.name).with_suffix(".xyz")
            output_error = ""
            while out_path is None:
                submitted = FillPrompt("Output path", value="").run(
                    ghost=str(default_output),
                    completer=default_path_completer(),
                    error_message=output_error,
                )
                output_text = submitted or str(default_output)
                if output_text:
                    out_path = Path(output_text).expanduser()
                    break
                output_error = "Output path is required."

        guessed_out_format = SPECIAL_FILENAME_FORMATS.get(out_path.name.upper())
        if guessed_out_format is None:
            guessed_out_format = EXTENSION_FORMATS.get(out_path.suffix.lower())

        if out_format is None:
            out_format = (
                FillPrompt("Output format", value="").run(
                    ghost=guessed_out_format or DEFAULT_OUTPUT_FORMAT,
                    completer=default_format_completer(),
                )
                or guessed_out_format
                or DEFAULT_OUTPUT_FORMAT
            )

    try:
        if in_path is None:
            raise ValueError("input path is required")
        if in_format is None:
            raise ValueError("input format is not specified and cannot be detected")

        if out_path is None:
            out_format = DEFAULT_OUTPUT_FORMAT
            suffix = OUTPUT_SUFFIX_BY_FORMAT.get(out_format, f".{out_format}")
            out_path = in_path.with_suffix(suffix)
        else:
            if out_path.exists() and out_path.is_dir():
                out_path = out_path / in_path.with_suffix("").name

            stem_upper = out_path.stem.upper()
            if out_path.suffix == "" and stem_upper in SPECIAL_BASENAME_FORMATS:
                out_format = SPECIAL_BASENAME_FORMATS[stem_upper]
            else:
                if out_format is None:
                    out_format = SPECIAL_FILENAME_FORMATS.get(out_path.name.upper())
                    if out_format is None:
                        out_format = EXTENSION_FORMATS.get(out_path.suffix.lower())
                    if out_format is None:
                        out_format = DEFAULT_OUTPUT_FORMAT

            if out_path.suffix == "" and stem_upper not in SPECIAL_BASENAME_FORMATS:
                suffix = OUTPUT_SUFFIX_BY_FORMAT.get(out_format, f".{out_format}")
                out_path = out_path.with_suffix(suffix)

        if in_format == "espresso-xml":
            parser = XML(in_path)
            images = parser.step.atoms
        else:
            images = ase_io.read(in_path, format=in_format, index=":")

        if isinstance(images, (list, tuple)):
            seq = images
        else:
            seq = [images]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        ase_io.write(out_path, seq, format=out_format)
    except Exception as exc:  # pragma: no cover
        if not silent:
            FinishPrompt(success=False).run()
            typer.echo(f"Error while converting: {exc}", err=True)
        raise typer.Exit(code=1)
    if not silent:
        FinishPrompt(success=True).run()
