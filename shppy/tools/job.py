import datetime as dt
import os
from pathlib import Path
from typing import Annotated, Optional

import typer

from shppy.shell import Shell
from shppy.tools.inputs import input_partitions
from shppy.tui.prompts import FinishPrompt, TitlePrompt

app = typer.Typer(help="Job management commands.", no_args_is_help=True)


@app.command(help="Generate a job.sh file")
def make(
    partition: Annotated[
        Optional[str],
        typer.Option("--partition", "-p", help="Partition to submit the job to."),
    ] = None,
    output: Annotated[
        str,
        typer.Option(
            "--output", "-o", help="Output path for the generated job script."
        ),
    ] = "job.sh",
):
    TitlePrompt("shppy job make").run()
    pth = Path(output)
    sh = Shell()

    partition = input_partitions(partition, sh)

    r = sh.run(f'sinfo -p {partition} -h -o "%l %e %c %G"').out.strip().split()
    time, mem, cpus, gres = r

    mem_per_cpu = int(int(mem.split("-")[1]) / int(cpus) / 100) * 100

    if gres == "(null)":
        ntasks_per_node = int(cpus)
        cpus_per_task = 1
    else:
        ntasks_per_node = int(gres.split(":")[-1])
        cpus_per_task = int(cpus) // ntasks_per_node

    with open(pth, "w") as f:
        f.write(
            "#!/bin/bash\n"
            f"#SBATCH --partition={partition}\n"
            "#SBATCH --job-name=ShppyJob\n"
            "#SBATCH --nodes=1\n"
            f"#SBATCH --ntasks-per-node={ntasks_per_node}\n"
            f"#SBATCH --time={time}\n"
            f"#SBATCH --mem-per-cpu={mem_per_cpu}M\n"
            f"#SBATCH --cpus-per-task={cpus_per_task}\n"
        )
        if gres != "(null)":
            f.write("#SBATCH --gpus-per-task=1\n")

        f.write(
            "#SBATCH --output=slurm-%j.out\n"
            "#SBATCH --error=slurm-%j.err\n"
            "\n"
            "shppy job init\n"
            "source ~/.bashrc && module purge && cd ${SLURM_SUBMIT_DIR}\n"
            "export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK} MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK}"
        )

    FinishPrompt(True, "Success!").run()


@app.command(help="Initialize environment for job running.", hidden=True)
def init(
    user: Annotated[
        Optional[str], typer.Option("--user", "-u", help="Task running user.")
    ] = None,
    global_log_dir: Annotated[
        str,
        typer.Option(
            "--global-log-dir", "-g", help="Global log directory to link job logs to."
        ),
    ] = "~/.jobs",
):
    print("┌ shppy job init")
    print("│")
    job_id = os.environ.get("SLURM_JOB_ID", None)
    s_dir = os.environ.get("SLURM_SUBMIT_DIR", None)
    if user is None:
        user = os.getenv("USER", "UNK")
    if job_id is None or s_dir is None:
        print("└ This script is meant to be run with `sbatch`")
        exit(1)
    
    s_dir = Path(s_dir)
    g_dir = Path(global_log_dir).expanduser() / dt.datetime.now().strftime("%Y%m%d")
    g_dir.mkdir(parents=True, exist_ok=True)

    if (s_dir / "slurm.out").exists(follow_symlinks=False):
        (s_dir / "slurm.out").unlink()
    if (s_dir / "slurm.err").exists(follow_symlinks=False):
        (s_dir / "slurm.err").unlink()
    if (g_dir / f"slurm-{job_id}.out").exists(follow_symlinks=False):
        (g_dir / f"slurm-{job_id}.out").unlink()
    if (g_dir / f"slurm-{job_id}.err").exists(follow_symlinks=False):
        (g_dir / f"slurm-{job_id}.err").unlink()

    Path(s_dir / "slurm.out").symlink_to(f"slurm-{job_id}.out")
    Path(s_dir / "slurm.err").symlink_to(f"slurm-{job_id}.err")
    Path(g_dir / f"slurm-{job_id}.out").symlink_to(f"slurm-{job_id}.out")
    Path(g_dir / f"slurm-{job_id}.err").symlink_to(f"slurm-{job_id}.err")

    print("└ Success!")


if __name__ == "__main__":
    app()
