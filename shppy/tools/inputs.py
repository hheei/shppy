from pathlib import Path
from typing import Optional
from prompt_toolkit.completion import PathCompleter
from shppy.tui.prompts import InfoPrompt, MultiSelectPrompt, FinishPrompt, FillPrompt
from shppy.shell import Shell

def input_partitions(inp: Optional[str], shell: Shell):
    avail = shell.run("sinfo -h -o '%P'").out.split()
    if inp is None:
        if avail == []:
            FinishPrompt(False, "No partitions available").run()
            exit(1)
        r = MultiSelectPrompt("Select partitions to use:", options=avail).run(
            min_selected=1, max_selected=1
        )[0]
        return r
    else:
        if inp not in avail:
            FinishPrompt(False, f"Partition '{inp}' is not found").run()
        return inp

def input_formats(inp: Optional[str],
                  options: list[str]
                  ):
    if inp is None:
        r = MultiSelectPrompt("Select formats to use:", options=options).run(
            min_selected=1, max_selected=1
        )[0]
        return r
    else:
        if inp not in options:
            FinishPrompt(False, f"Format '{inp}' is not a valid option").run()
        return inp
    

def input_path(title: str = "Input path",
               default: Optional[str] = None,
               ghost: str = "", 
               need_empty: bool = False, 
               need_exist: bool = False
               ) -> Path:
    if need_empty and need_exist:
        FinishPrompt(False, "Cannot require both empty and existing path").run()
        exit(1)
        
    def _validate_input_path(text: str) -> tuple[bool, str]:
        text = text.strip()
        q = Path(text).expanduser()
        if text == "":
            if default is not None:
                return True, ""
            return False, "Input path is required."
        if need_exist and not q.exists():
            return False, f"Path '{text}' does not exist."
        if need_empty and q.exists():
            return False, f"Path '{text}' already exists."
        return True, ""

    pth = FillPrompt(title, value="").run(
        ghost=ghost,
        completer=PathCompleter(expanduser=True),
        validator=_validate_input_path
    )
    
    if pth.strip() == "" and default is not None:
        pth = default
    return Path(pth.strip()).expanduser()

if __name__ == "__main__":
    # for testing
    pth = input_path(need_empty=True, ghost="123.txt", default="123.txt")
    print(f"Got path: {pth}")