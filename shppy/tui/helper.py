from pathlib import Path

from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.layout.processors import Processor, Transformation

DEFAULT_FORMAT_OPTIONS = ["xyz", "extxyz", "cif", "lammpstraj", "vasp", "vasp-xdatcar"]


def default_path_completer() -> PathCompleter:
    return PathCompleter(expanduser=True)


def validate_existing_path(text: str) -> tuple[bool, str, Path | None]:
    value = (text or "").strip()
    if not value:
        return False, "Input path is required.", None
    p = Path(value).expanduser()
    if not p.exists():
        return False, f"Path '{value}' does not exist.", None
    return True, "", p


class GhostTextProcessor(Processor):
    def __init__(self, get_ghost_text):
        self.get_ghost_text = get_ghost_text

    def apply_transformation(self, transformation_input):
        fragments = transformation_input.fragments
        if transformation_input.lineno != 0:
            return Transformation(fragments)
        if transformation_input.buffer_control.buffer.text:
            return Transformation(fragments)
        ghost_text = self.get_ghost_text()
        if not ghost_text:
            return Transformation(fragments)
        return Transformation(fragments + [("class:ghost", ghost_text)])
