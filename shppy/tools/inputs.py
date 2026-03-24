from typing import Optional
from shppy.tui.prompts import InfoPrompt, MultiSelectPrompt, FinishPrompt
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
